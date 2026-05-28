"""
Institutional Data Quality Engine — validates CSV data before analysis.

The engine rejects corrupted market data loudly by returning a structured
DataQualityReport with integrity warnings instead of silently allowing invalid
OHLCV candles into downstream SMC/ICT, RTM, liquidity, or regime logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Tuple

import numpy as np
import pandas as pd

from core.schemas import CandleSchema, DataQualityReport, Market, TimeFrame


class DataQualityEngine:
    """Validate OHLCV data for a specific market and timeframe."""

    def __init__(self) -> None:
        self.schema = CandleSchema()
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
        }

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        market: Market,
        timeframe: TimeFrame,
    ) -> DataQualityReport:
        """
        Validate an OHLCV dataframe and return a structured quality report.

        Args:
            df: DataFrame with timestamp, open, high, low, close, and volume.
            market: Market enum member for report attribution.
            timeframe: TimeFrame enum member used for cadence checks.
        """
        if not isinstance(df, pd.DataFrame):
            return self._make_report(
                market, timeframe, 0.0, 0.0, ["Input is not a pandas DataFrame"]
            )

        warnings: list[str] = []
        missing = dups = outliers = gaps = 0
        required = list(self.schema.required_columns)
        numeric_columns = list(self.schema.price_columns) + [self.schema.volume]

        missing_columns = [column for column in required if column not in df.columns]
        if missing_columns:
            return self._make_report(
                market,
                timeframe,
                0.0,
                0.0,
                [f"Missing required columns: {', '.join(missing_columns)}"],
            )

        data = df.loc[:, required].copy()
        if data.empty:
            return self._make_report(market, timeframe, 0.0, 0.0, ["Input DataFrame is empty"])

        data[self.schema.timestamp] = pd.to_datetime(data[self.schema.timestamp], errors="coerce")
        invalid_timestamps = int(data[self.schema.timestamp].isna().sum())
        if invalid_timestamps:
            warnings.append(f"{invalid_timestamps} rows have invalid timestamps")

        data[numeric_columns] = data[numeric_columns].apply(pd.to_numeric, errors="coerce")
        data = data.sort_values(self.schema.timestamp).reset_index(drop=True)

        missing, gap_warnings = self._detect_missing_candles(data, timeframe)
        warnings.extend(gap_warnings)

        dups, dup_warnings = self._detect_duplicates(data)
        warnings.extend(dup_warnings)

        non_finite_numeric = data[numeric_columns].isna().any(axis=1) | np.isinf(
            data[numeric_columns]
        ).any(axis=1)
        corrupted = data[self.schema.timestamp].isna() | non_finite_numeric
        corrupted_count = int(corrupted.sum())
        if corrupted_count:
            warnings.append(f"{corrupted_count} rows contain NaN/inf values")

        invalid_ohlc = self._detect_invalid_ohlc(data)
        invalid_ohlc_count = int(invalid_ohlc.sum())
        if invalid_ohlc_count:
            warnings.append(f"{invalid_ohlc_count} rows have invalid OHLC logic")

        candle_range = (data[self.schema.high] - data[self.schema.low]).where(~corrupted)
        outliers = self._count_std_outliers(candle_range, self.max_spike_std_multiplier)
        if outliers:
            warnings.append(
                f"{outliers} outlier spikes detected "
                f"(candle range > {self.max_spike_std_multiplier} std)"
            )

        gap_sizes = (data[self.schema.open] - data[self.schema.close].shift(1)).abs().where(~corrupted)
        gaps = self._count_std_outliers(gap_sizes.dropna(), self.max_gap_std_multiplier)
        if gaps:
            warnings.append(f"{gaps} extreme gaps detected")

        volume_spikes = self._count_std_outliers(
            data[self.schema.volume].where(~corrupted), self.max_volume_std_multiplier
        )
        if volume_spikes:
            warnings.append(f"{volume_spikes} extreme volume spikes")

        total_checks = 8
        passed = float(total_checks)
        passed -= float(missing > 0)
        passed -= float(dups > 0)
        passed -= float(corrupted_count > 0)
        passed -= float(invalid_ohlc_count > 0)
        passed -= float(outliers > 0)
        passed -= float(gaps > 0)
        passed -= float(volume_spikes > 0)
        passed -= float(bool(warnings)) * 0.5

        quality_score = max(0.0, min(1.0, passed / total_checks))
        integrity_score = max(0.0, quality_score * (1.0 - (0.1 * len(warnings))))

        return DataQualityReport(
            timestamp=datetime.now(UTC),
            market=market,
            timeframe=timeframe,
            quality_score=round(quality_score, 4),
            integrity_score=round(integrity_score, 4),
            warnings=warnings,
            missing_candles=missing,
            duplicate_timestamps=dups,
            outliers_detected=outliers,
            gaps_detected=gaps,
        )

    def _detect_missing_candles(
        self, df: pd.DataFrame, timeframe: TimeFrame
    ) -> Tuple[int, list[str]]:
        freq = self.expected_freq_minutes.get(timeframe)
        if not freq or self.schema.timestamp not in df:
            return 0, []

        valid_timestamps = df[self.schema.timestamp].dropna()
        if valid_timestamps.empty:
            return 0, []

        expected_delta = timedelta(minutes=freq)
        diffs = valid_timestamps.diff().dropna()
        missing_mask = (diffs > expected_delta) & (diffs < expected_delta * 100)
        missing = int(missing_mask.sum())
        warnings = []
        if missing:
            warnings.append(f"Detected {missing} missing candles (time gaps)")
        return missing, warnings

    def _detect_duplicates(self, df: pd.DataFrame) -> Tuple[int, list[str]]:
        dups = int(df.duplicated(subset=self.schema.timestamp).sum())
        warnings = []
        if dups:
            warnings.append(f"Detected {dups} duplicate timestamps")
        return dups, warnings

    def _detect_invalid_ohlc(self, df: pd.DataFrame) -> pd.Series:
        return (
            (df[self.schema.high] < df[self.schema.low])
            | (df[self.schema.high] < df[self.schema.open])
            | (df[self.schema.high] < df[self.schema.close])
            | (df[self.schema.low] > df[self.schema.open])
            | (df[self.schema.low] > df[self.schema.close])
        )

    @staticmethod
    def _count_std_outliers(series: pd.Series, std_multiplier: float) -> int:
        clean = series.replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) <= 1:
            return 0

        std_value = clean.std()
        if pd.isna(std_value) or std_value <= 0:
            return 0

        threshold = clean.mean() + (std_multiplier * std_value)
        return int((clean > threshold).sum())

    def _make_report(
        self,
        market: Market,
        timeframe: TimeFrame,
        quality: float,
        integrity: float,
        warnings: list[str],
    ) -> DataQualityReport:
        return DataQualityReport(
            timestamp=datetime.now(UTC),
            market=market,
            timeframe=timeframe,
            quality_score=round(max(0.0, min(1.0, quality)), 4),
            integrity_score=round(max(0.0, min(1.0, integrity)), 4),
            warnings=warnings,
            missing_candles=0,
            duplicate_timestamps=0,
            outliers_detected=0,
            gaps_detected=0,
        )
