"""
validators/data_quality_engine.py
Institutional Data Quality Engine — validates CSV data before any analysis.
Never allows corrupted market data into the pipeline silently.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from core.schemas import CandleSchema, DataQualityReport, Market, TimeFrame


class DataQualityEngine:
    """
    Validates OHLCV data for a specific market and timeframe.
    Generates a DataQualityReport with quality/integrity scores and warnings.
    """

    def __init__(self) -> None:
        # Thresholds can be moved into market-specific config later.
        self.max_spike_std_multiplier = 5.0
        self.max_volume_std_multiplier = 8.0
        self.max_gap_std_multiplier = 4.0
        self.expected_freq_minutes = {
            TimeFrame.M1: 1,
            TimeFrame.M5: 5,
            TimeFrame.M15: 15,
            TimeFrame.M30: 30,
            TimeFrame.H1: 60,
            TimeFrame.H4: 240,
            TimeFrame.D1: 1440,
            TimeFrame.W1: 10080,
        }

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        market: Market,
        timeframe: TimeFrame,
    ) -> DataQualityReport:
        """
        Validate an OHLCV dataframe without mutating the caller's dataframe.

        Args:
            df: DataFrame with timestamp/open/high/low/close and optional volume.
            market: Market enum member.
            timeframe: TimeFrame enum member.

        Returns:
            DataQualityReport with bounded [0, 1] quality and integrity scores.
        """
        warnings: list[str] = []

        if df is None or not isinstance(df, pd.DataFrame):
            return self._make_report(market, timeframe, 0.0, 0.0, ["Input is not a pandas DataFrame"])

        missing_columns = [column for column in CandleSchema.REQUIRED_COLUMNS if column not in df.columns]
        if missing_columns:
            return self._make_report(
                market,
                timeframe,
                0.0,
                0.0,
                [f"Missing required columns: {', '.join(missing_columns)}"],
            )

        if df.empty:
            return self._make_report(market, timeframe, 0.0, 0.0, ["DataFrame is empty"])

        has_volume = CandleSchema.volume in df.columns
        if not has_volume:
            warnings.append("Volume column missing; skipped volume validation")

        selected_columns = list(CandleSchema.REQUIRED_COLUMNS)
        if has_volume:
            selected_columns.append(CandleSchema.volume)
        working = df.loc[:, selected_columns].copy()

        working[CandleSchema.timestamp] = pd.to_datetime(working[CandleSchema.timestamp], errors="coerce")
        invalid_timestamps = int(working[CandleSchema.timestamp].isna().sum())
        if invalid_timestamps:
            warnings.append(f"{invalid_timestamps} rows have invalid timestamps")

        numeric_columns = list(CandleSchema.PRICE_COLUMNS)
        if has_volume:
            numeric_columns.append(CandleSchema.volume)
        working.loc[:, numeric_columns] = working.loc[:, numeric_columns].apply(pd.to_numeric, errors="coerce")

        working = working.sort_values(CandleSchema.timestamp, kind="mergesort").reset_index(drop=True)

        missing, gap_warnings = self._detect_missing_candles(working, timeframe)
        warnings.extend(gap_warnings)

        dups, dup_warnings = self._detect_duplicates(working)
        warnings.extend(dup_warnings)

        numeric = working.loc[:, numeric_columns]
        corrupted_mask = numeric.isna().any(axis=1) | np.isinf(numeric).any(axis=1)
        corrupted_mask = corrupted_mask | working[CandleSchema.timestamp].isna()
        corrupted_count = int(corrupted_mask.sum())
        if corrupted_count:
            warnings.append(f"{corrupted_count} rows contain NaN/inf or unparseable values")

        invalid_ohlc = self._detect_invalid_ohlc(working, has_volume=has_volume) & ~corrupted_mask
        invalid_ohlc_count = int(invalid_ohlc.sum())
        if invalid_ohlc_count:
            warnings.append(f"{invalid_ohlc_count} rows have invalid OHLC logic")

        valid_rows = working.loc[~corrupted_mask & ~invalid_ohlc].copy()

        outliers = self._detect_outlier_spikes(valid_rows)
        if outliers:
            warnings.append(
                f"{outliers} outlier spikes detected "
                f"(robust candle range z-score > {self.max_spike_std_multiplier})"
            )

        gaps = self._detect_extreme_price_gaps(valid_rows)
        if gaps:
            warnings.append(f"{gaps} extreme gaps detected")

        volume_spikes = self._detect_volume_spikes(valid_rows) if has_volume else 0
        if volume_spikes:
            warnings.append(f"{volume_spikes} extreme volume spikes")

        quality_score, integrity_score = self._score_report(
            warning_count=len(warnings),
            missing=missing,
            dups=dups,
            corrupted=corrupted_count,
            invalid_ohlc=invalid_ohlc_count,
            outliers=outliers,
            gaps=gaps,
            volume_spikes=volume_spikes,
        )

        return DataQualityReport(
            timestamp=self._utc_now(),
            market=market,
            timeframe=timeframe,
            quality_score=quality_score,
            integrity_score=integrity_score,
            warnings=warnings,
            missing_candles=missing,
            duplicate_timestamps=dups,
            outliers_detected=outliers,
            gaps_detected=gaps,
            corrupted_rows=corrupted_count,
            invalid_ohlc_rows=invalid_ohlc_count,
            volume_spikes=volume_spikes,
        )

    def _detect_missing_candles(self, df: pd.DataFrame, timeframe: TimeFrame) -> tuple[int, list[str]]:
        freq = self.expected_freq_minutes.get(timeframe)
        timestamps = df[CandleSchema.timestamp].dropna().drop_duplicates().sort_values(kind="mergesort")
        if not freq or timestamps.shape[0] < 2:
            return 0, []

        expected_delta = timedelta(minutes=freq)
        diffs = timestamps.diff().dropna()
        bounded_gaps = diffs[(diffs > expected_delta) & (diffs < expected_delta * 100)]
        missing = int(((bounded_gaps // expected_delta) - 1).clip(lower=1).sum())

        warnings: list[str] = []
        if missing:
            warnings.append(f"Detected {missing} missing candles (time gaps)")
        return missing, warnings

    def _detect_duplicates(self, df: pd.DataFrame) -> tuple[int, list[str]]:
        valid_timestamps = df[CandleSchema.timestamp].dropna()
        dups = int(valid_timestamps.duplicated().sum())
        warnings: list[str] = []
        if dups:
            warnings.append(f"Detected {dups} duplicate timestamps")
        return dups, warnings

    def _detect_invalid_ohlc(self, df: pd.DataFrame, *, has_volume: bool) -> pd.Series:
        invalid_price_order = (
            (df[CandleSchema.high] < df[CandleSchema.low])
            | (df[CandleSchema.high] < df[CandleSchema.open])
            | (df[CandleSchema.high] < df[CandleSchema.close])
            | (df[CandleSchema.low] > df[CandleSchema.open])
            | (df[CandleSchema.low] > df[CandleSchema.close])
        )
        invalid_non_positive_prices = (df.loc[:, list(CandleSchema.PRICE_COLUMNS)] <= 0).any(axis=1)
        invalid = invalid_price_order | invalid_non_positive_prices
        if has_volume:
            invalid = invalid | (df[CandleSchema.volume] < 0)
        return invalid.fillna(False)

    def _detect_outlier_spikes(self, df: pd.DataFrame) -> int:
        candle_range = self._finite_series(df[CandleSchema.high] - df[CandleSchema.low])
        return self._robust_upper_outlier_count(candle_range, self.max_spike_std_multiplier)

    def _detect_extreme_price_gaps(self, df: pd.DataFrame) -> int:
        gap_sizes = self._finite_series((df[CandleSchema.open] - df[CandleSchema.close].shift(1)).abs())
        return self._robust_upper_outlier_count(gap_sizes, self.max_gap_std_multiplier)

    def _detect_volume_spikes(self, df: pd.DataFrame) -> int:
        volume = self._finite_series(df[CandleSchema.volume])
        return self._robust_upper_outlier_count(volume, self.max_volume_std_multiplier)

    def _score_report(
        self,
        *,
        warning_count: int,
        missing: int,
        dups: int,
        corrupted: int,
        invalid_ohlc: int,
        outliers: int,
        gaps: int,
        volume_spikes: int,
    ) -> tuple[float, float]:
        check_values = (missing, dups, corrupted, invalid_ohlc, outliers, gaps, volume_spikes)
        failed_checks = sum(int(value > 0) for value in check_values)
        total_checks = len(check_values)
        warning_penalty = 0.5 if warning_count else 0.0

        quality_score = max(0.0, min(1.0, (total_checks - failed_checks - warning_penalty) / total_checks))
        integrity_penalty = min(0.8, 0.08 * warning_count)
        integrity_score = max(0.0, min(1.0, quality_score * (1.0 - integrity_penalty)))
        return round(quality_score, 4), round(integrity_score, 4)

    def _make_report(
        self,
        market: Market,
        timeframe: TimeFrame,
        quality: float,
        integrity: float,
        warnings: list[str],
    ) -> DataQualityReport:
        return DataQualityReport(
            timestamp=self._utc_now(),
            market=market,
            timeframe=timeframe,
            quality_score=round(max(0.0, min(1.0, quality)), 4),
            integrity_score=round(max(0.0, min(1.0, integrity)), 4),
            warnings=warnings,
            missing_candles=0,
            duplicate_timestamps=0,
            outliers_detected=0,
            gaps_detected=0,
            corrupted_rows=0,
            invalid_ohlc_rows=0,
            volume_spikes=0,
        )

    @staticmethod
    def _finite_series(series: pd.Series) -> pd.Series:
        return series.replace([np.inf, -np.inf], np.nan).dropna()

    @staticmethod
    def _robust_upper_outlier_count(series: pd.Series, multiplier: float) -> int:
        if series.shape[0] < 3:
            return 0

        median = series.median()
        mad = (series - median).abs().median()
        if np.isfinite(mad) and mad > 0:
            robust_z = 0.6745 * (series - median) / mad
            return int((robust_z > multiplier).sum())

        fallback_scale = max(abs(median), 1.0)
        threshold = median + multiplier * fallback_scale
        fallback_count = int((series > threshold).sum())
        if fallback_count:
            return fallback_count

        std = series.std()
        if not np.isfinite(std) or std <= 0:
            return 0
        threshold = series.mean() + multiplier * std
        return int((series > threshold).sum())

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)
