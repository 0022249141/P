"""
validators/data_quality_engine.py
Institutional Data Quality Engine — validates CSV data before analysis.
"""

from __future__ import annotations

from datetime import datetime, timedelta
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
        }

    def validate_dataframe(self, df: pd.DataFrame, market: Market, timeframe: TimeFrame) -> DataQualityReport:
        warnings: List[str] = []
        missing = dups = outliers = gaps = 0
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        numeric_cols = ["open", "high", "low", "close", "volume"]

        if df is None or df.empty:
            return self._make_report(market, timeframe, 0.0, 0.0, ["Empty DataFrame"])

        df = df.copy()
        missing_cols = [col for col in required if col not in df.columns]
        if missing_cols:
            return self._make_report(market, timeframe, 0.0, 0.0, [f"Missing required columns: {missing_cols}"])

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        invalid_ts = int(df["timestamp"].isna().sum())
        if invalid_ts:
            warnings.append(f"{invalid_ts} rows have invalid timestamps")

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_values("timestamp").reset_index(drop=True)
        missing, gap_warnings = self._detect_missing_candles(df.dropna(subset=["timestamp"]), timeframe)
        warnings.extend(gap_warnings)

        dups, dup_warnings = self._detect_duplicates(df)
        warnings.extend(dup_warnings)

        numeric_values = df[numeric_cols].to_numpy(dtype=float, copy=True)
        corrupted = df[required].isnull().any(axis=1) | np.isinf(numeric_values).any(axis=1)
        corrupted_count = int(corrupted.sum())
        if corrupted_count:
            warnings.append(f"{corrupted_count} rows contain NaN/inf values")

        invalid_ohlc = (
            (df["high"] < df[["open", "close", "low"]].max(axis=1)) |
            (df["low"] > df[["open", "close", "high"]].min(axis=1)) |
            (df["volume"] < 0)
        )
        invalid_ohlc_count = int(invalid_ohlc.sum())
        if invalid_ohlc_count:
            warnings.append(f"{invalid_ohlc_count} rows have invalid OHLCV logic")

        clean = df.loc[~corrupted & ~invalid_ohlc].copy()
        if len(clean) >= 3:
            candle_range = (clean["high"] - clean["low"]).abs()
            mean_range, std_range = candle_range.mean(), candle_range.std()
            if pd.notna(std_range) and std_range > 0:
                outliers = int((candle_range > mean_range + self.max_spike_std_multiplier * std_range).sum())
                if outliers:
                    warnings.append(f"{outliers} outlier spikes detected")

            gap_sizes = (clean["open"] - clean["close"].shift(1)).abs().dropna()
            if len(gap_sizes) > 1:
                mean_gap, std_gap = gap_sizes.mean(), gap_sizes.std()
                if pd.notna(std_gap) and std_gap > 0:
                    gaps = int((gap_sizes > mean_gap + self.max_gap_std_multiplier * std_gap).sum())
                    if gaps:
                        warnings.append(f"{gaps} extreme close-to-open gaps detected")

            vol_spike = pd.Series(False, index=clean.index)
            vol = clean["volume"]
            std_vol = vol.std()
            if pd.notna(std_vol) and std_vol > 0:
                vol_spike = vol > vol.mean() + self.max_volume_std_multiplier * std_vol
                if bool(vol_spike.any()):
                    warnings.append(f"{int(vol_spike.sum())} extreme volume spikes")
        else:
            warnings.append("Insufficient clean rows after validation")

        severe = invalid_ts + missing + dups + corrupted_count + invalid_ohlc_count
        total_rows = max(len(df), 1)
        integrity_score = max(0.0, 1.0 - min(1.0, severe / total_rows))
        penalty = 0.0
        for condition in [missing > 0, dups > 0, corrupted_count > 0, invalid_ohlc_count > 0, outliers > 0, gaps > 0, invalid_ts > 0]:
            penalty += 0.12 if condition else 0.0
        quality_score = max(0.0, min(1.0, integrity_score - penalty + 0.05))

        return DataQualityReport(
            timestamp=datetime.utcnow(),
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

    def _detect_missing_candles(self, df: pd.DataFrame, timeframe: TimeFrame) -> Tuple[int, List[str]]:
        if timeframe == TimeFrame.MN1:
            return 0, []
        freq = self.expected_freq_minutes.get(timeframe)
        if not freq or df.empty:
            return 0, []
        expected = timedelta(minutes=freq)
        diffs = df["timestamp"].diff().dropna()
        missing = 0
        for delta in diffs:
            if expected < delta < expected * 100:
                missing += max(1, int(delta / expected) - 1)
        return missing, ([f"Detected {missing} missing candles"] if missing else [])

    def _detect_duplicates(self, df: pd.DataFrame) -> Tuple[int, List[str]]:
        dups = int(df.duplicated(subset="timestamp").sum()) if "timestamp" in df.columns else 0
        return dups, ([f"Detected {dups} duplicate timestamps"] if dups else [])

    def _make_report(self, market: Market, timeframe: TimeFrame, quality: float, integrity: float, warnings: List[str]) -> DataQualityReport:
        return DataQualityReport(
            timestamp=datetime.utcnow(), market=market, timeframe=timeframe,
            quality_score=quality, integrity_score=integrity, warnings=warnings,
            missing_candles=0, duplicate_timestamps=0, outliers_detected=0, gaps_detected=0,
        )
