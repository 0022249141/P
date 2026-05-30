"""
validators/data_quality_engine.py

Institutional Data Quality Engine.
Validates canonical OHLCV data before analysis.

This version is market-aware/session-aware:
- XAUUSD intraday gaps ignore weekends.
- Iranian/Herat local-market intraday gaps ignore overnight non-session hours.
- Monthly data is not penalized for synthetic missing candles.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import numpy as np
import pandas as pd

from core.schemas import DataQualityReport, Market, TimeFrame


class DataQualityEngine:
    def __init__(self) -> None:
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
            TimeFrame.MN1: 43200,
        }

        self.intraday_timeframes = {
            TimeFrame.M1,
            TimeFrame.M5,
            TimeFrame.M15,
            TimeFrame.M30,
            TimeFrame.H1,
            TimeFrame.H4,
        }

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        market: Market,
        timeframe: TimeFrame,
    ) -> DataQualityReport:
        warnings: List[str] = []
        missing = dups = outliers = gaps = 0

        required = ["timestamp", "open", "high", "low", "close", "volume"]
        numeric_cols = ["open", "high", "low", "close", "volume"]

        if df is None or df.empty:
            return self._make_report(market, timeframe, 0.0, 0.0, ["Empty DataFrame"])

        df = df.copy()

        missing_cols = [col for col in required if col not in df.columns]
        if missing_cols:
            return self._make_report(
                market,
                timeframe,
                0.0,
                0.0,
                [f"Missing required columns: {missing_cols}"],
            )

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        invalid_ts = int(df["timestamp"].isna().sum())
        if invalid_ts:
            warnings.append(f"{invalid_ts} rows have invalid timestamps")

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_values("timestamp").reset_index(drop=True)

        missing, missing_warnings = self._detect_missing_candles(
            df.dropna(subset=["timestamp"]),
            market,
            timeframe,
        )
        warnings.extend(missing_warnings)

        dups, dup_warnings = self._detect_duplicates(df)
        warnings.extend(dup_warnings)

        numeric_values = df[numeric_cols].to_numpy(dtype=float, copy=True)
        corrupted = df[required].isnull().any(axis=1) | np.isinf(numeric_values).any(axis=1)
        corrupted_count = int(corrupted.sum())
        if corrupted_count:
            warnings.append(f"{corrupted_count} rows contain NaN/inf values")

        invalid_ohlc = (
            (df["high"] < df[["open", "close", "low"]].max(axis=1))
            | (df["low"] > df[["open", "close", "high"]].min(axis=1))
            | (df["volume"] < 0)
        )
        invalid_ohlc_count = int(invalid_ohlc.sum())
        if invalid_ohlc_count:
            warnings.append(f"{invalid_ohlc_count} rows have invalid OHLCV logic")

        clean = df.loc[~corrupted & ~invalid_ohlc].copy()

        if len(clean) >= 3:
            candle_range = (clean["high"] - clean["low"]).abs()
            mean_range = candle_range.mean()
            std_range = candle_range.std()

            if pd.notna(std_range) and std_range > 0:
                outliers = int(
                    (candle_range > mean_range + self.max_spike_std_multiplier * std_range).sum()
                )
                if outliers:
                    warnings.append(f"{outliers} outlier spikes detected")

            gap_sizes = (clean["open"] - clean["close"].shift(1)).abs().dropna()
            if len(gap_sizes) > 1:
                mean_gap = gap_sizes.mean()
                std_gap = gap_sizes.std()
                if pd.notna(std_gap) and std_gap > 0:
                    gaps = int(
                        (gap_sizes > mean_gap + self.max_gap_std_multiplier * std_gap).sum()
                    )
                    if gaps:
                        warnings.append(f"{gaps} extreme close-to-open gaps detected")

            vol = clean["volume"]
            std_vol = vol.std()
            if pd.notna(std_vol) and std_vol > 0:
                vol_spike = vol > vol.mean() + self.max_volume_std_multiplier * std_vol
                if bool(vol_spike.any()):
                    warnings.append(f"{int(vol_spike.sum())} extreme volume spikes")
        else:
            warnings.append("Insufficient clean rows after validation")

        total_rows = max(len(df), 1)

        structural_errors = invalid_ts + dups + corrupted_count + invalid_ohlc_count
        integrity_score = max(0.0, 1.0 - min(1.0, structural_errors / total_rows))

        missing_rate = missing / max(total_rows + missing, 1)
        outlier_rate = outliers / max(len(clean), 1)
        gap_rate = gaps / max(len(clean), 1)

        penalty = 0.0
        penalty += min(0.35, missing_rate * 1.25)
        penalty += min(0.18, outlier_rate * 4.0)
        penalty += min(0.18, gap_rate * 4.0)

        if dups:
            penalty += 0.10
        if corrupted_count:
            penalty += 0.15
        if invalid_ohlc_count:
            penalty += 0.20
        if invalid_ts:
            penalty += 0.15

        quality_score = max(0.0, min(1.0, integrity_score - penalty))

        return DataQualityReport(
            timestamp=datetime.now(timezone.utc),
            market=market,
            timeframe=timeframe,
            quality_score=round(float(quality_score), 4),
            integrity_score=round(float(integrity_score), 4),
            warnings=warnings,
            missing_candles=int(missing),
            duplicate_timestamps=int(dups),
            outliers_detected=int(outliers),
            gaps_detected=int(gaps),
        )

    def _detect_missing_candles(
        self,
        df: pd.DataFrame,
        market: Market,
        timeframe: TimeFrame,
    ) -> Tuple[int, List[str]]:
        if df.empty:
            return 0, []

        if timeframe in {TimeFrame.MN1, TimeFrame.W1}:
            return 0, []

        freq_minutes = self.expected_freq_minutes.get(timeframe)
        if not freq_minutes:
            return 0, []

        timestamps = (
            pd.to_datetime(df["timestamp"], errors="coerce")
            .dropna()
            .drop_duplicates()
            .sort_values()
            .reset_index(drop=True)
        )

        if len(timestamps) < 2:
            return 0, []

        expected = timedelta(minutes=freq_minutes)
        missing = 0

        for previous_ts, current_ts in zip(timestamps.iloc[:-1], timestamps.iloc[1:]):
            delta = current_ts - previous_ts

            if delta <= expected:
                continue

            # Very large historical jumps are usually dataset boundaries or unavailable history.
            # Count only expected timestamps that are valid for the market calendar/session.
            expected_points = pd.date_range(
                start=previous_ts + expected,
                end=current_ts - expected,
                freq=expected,
            )

            if len(expected_points) == 0:
                continue

            valid_missing = sum(
                1 for ts in expected_points if self._is_expected_timestamp(ts, market, timeframe)
            )
            missing += int(valid_missing)

        if missing:
            return missing, [f"Detected {missing} session-adjusted missing candles"]

        return 0, []

    def _is_expected_timestamp(
        self,
        ts: pd.Timestamp,
        market: Market,
        timeframe: TimeFrame,
    ) -> bool:
        token = self._market_token(market)

        if timeframe == TimeFrame.MN1:
            return False

        if timeframe == TimeFrame.W1:
            return False

        if token == "xauusd":
            # XAUUSD: ignore Saturday/Sunday gaps.
            return ts.weekday() < 5

        if token in {"abshodeh", "herat"}:
            # Local OTC/session-driven markets.
            # User-defined target session: Asia/Tehran 09:00–22:00.
            # Timestamps are treated as local-naive unless upstream normalizes timezone.
            if timeframe in self.intraday_timeframes:
                minute_of_day = ts.hour * 60 + ts.minute
                return (9 * 60) <= minute_of_day <= (22 * 60)

            # Daily data for local OTC markets should not be evaluated as strict 24/7 minute stream.
            return True

        return True

    def _detect_duplicates(self, df: pd.DataFrame) -> Tuple[int, List[str]]:
        dups = int(df.duplicated(subset="timestamp").sum()) if "timestamp" in df.columns else 0
        return dups, ([f"Detected {dups} duplicate timestamps"] if dups else [])

    def _make_report(
        self,
        market: Market,
        timeframe: TimeFrame,
        quality: float,
        integrity: float,
        warnings: List[str],
    ) -> DataQualityReport:
        return DataQualityReport(
            timestamp=datetime.now(timezone.utc),
            market=market,
            timeframe=timeframe,
            quality_score=quality,
            integrity_score=integrity,
            warnings=warnings,
            missing_candles=0,
            duplicate_timestamps=0,
            outliers_detected=0,
            gaps_detected=0,
        )

    @staticmethod
    def _market_token(market: Market) -> str:
        raw = getattr(market, "value", str(market))
        return str(raw).strip().lower().replace("_", "").replace("-", "")