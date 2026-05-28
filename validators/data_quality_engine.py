"""Vectorized market-data quality checks for OHLCV dataframes."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from core.schemas import DataQualityReport, Market, TimeFrame


class DataQualityEngine:
    """Validate candle dataframes before downstream institutional analysis."""

    REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")
    OPTIONAL_COLUMNS = ("volume",)
    TIMEFRAME_SECONDS = {
        TimeFrame.M1: 60,
        TimeFrame.M5: 5 * 60,
        TimeFrame.M15: 15 * 60,
        TimeFrame.H1: 60 * 60,
        TimeFrame.H4: 4 * 60 * 60,
        TimeFrame.D1: 24 * 60 * 60,
    }

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        market: Market,
        timeframe: TimeFrame,
    ) -> DataQualityReport:
        """Return a bounded quality report for an OHLCV dataframe.

        The scoring intentionally uses only data present in the dataframe and
        vectorized checks, preventing future-data leakage or repainting logic.
        """

        warnings: list[str] = []
        if df.empty:
            return self._report(market, timeframe, 0.0, 0.0, warnings=["dataframe is empty"])

        missing_columns = [column for column in self.REQUIRED_COLUMNS if column not in df.columns]
        if missing_columns:
            return self._report(
                market,
                timeframe,
                0.0,
                0.0,
                warnings=[f"missing required columns: {', '.join(missing_columns)}"],
            )

        normalized = df.loc[:, [*self.REQUIRED_COLUMNS, *[c for c in self.OPTIONAL_COLUMNS if c in df.columns]]].copy()
        timestamps = pd.to_datetime(normalized["timestamp"], errors="coerce", utc=True)
        numeric_columns = ["open", "high", "low", "close"]
        if "volume" in normalized.columns:
            numeric_columns.append("volume")
        numeric = normalized.loc[:, numeric_columns].apply(pd.to_numeric, errors="coerce")

        invalid_timestamps = int(timestamps.isna().sum())
        missing_values = int(numeric.isna().sum().sum() + invalid_timestamps)
        duplicate_timestamps = int(timestamps.duplicated(keep=False).sum())

        open_price = numeric["open"]
        high_price = numeric["high"]
        low_price = numeric["low"]
        close_price = numeric["close"]
        invalid_ohlc = (
            high_price.lt(low_price)
            | high_price.lt(open_price)
            | high_price.lt(close_price)
            | low_price.gt(open_price)
            | low_price.gt(close_price)
            | open_price.lt(0)
            | high_price.lt(0)
            | low_price.lt(0)
            | close_price.lt(0)
        )
        if "volume" in numeric:
            invalid_ohlc = invalid_ohlc | numeric["volume"].lt(0)
        invalid_ohlc_count = int(invalid_ohlc.fillna(True).sum())

        gaps_detected = self._count_time_gaps(timestamps, timeframe)
        missing_candles = self._estimate_missing_candles(timestamps, timeframe)
        outliers_detected = self._count_range_outliers(high_price, low_price, close_price)

        total_rows = max(len(normalized), 1)
        completeness_score = max(0.0, 1.0 - missing_values / (total_rows * len(numeric_columns) + total_rows))
        integrity_penalty = (invalid_ohlc_count + duplicate_timestamps) / total_rows
        integrity_score = max(0.0, 1.0 - integrity_penalty)
        continuity_penalty = min(1.0, (gaps_detected + missing_candles) / max(total_rows, 1))
        outlier_penalty = min(1.0, outliers_detected / max(total_rows, 1))
        quality_score = max(
            0.0,
            min(
                1.0,
                (0.50 * integrity_score)
                + (0.25 * completeness_score)
                + (0.15 * (1.0 - continuity_penalty))
                + (0.10 * (1.0 - outlier_penalty)),
            ),
        )

        if missing_values:
            warnings.append(f"missing or non-numeric values detected: {missing_values}")
        if invalid_ohlc_count:
            warnings.append(f"invalid OHLCV rows detected: {invalid_ohlc_count}")
        if duplicate_timestamps:
            warnings.append(f"duplicate timestamps detected: {duplicate_timestamps}")
        if gaps_detected:
            warnings.append(f"time gaps detected: {gaps_detected}")
        if outliers_detected:
            warnings.append(f"range outliers detected: {outliers_detected}")

        return self._report(
            market=market,
            timeframe=timeframe,
            quality_score=quality_score,
            integrity_score=integrity_score,
            warnings=warnings,
            missing_candles=missing_candles,
            duplicate_timestamps=duplicate_timestamps,
            outliers_detected=outliers_detected,
            gaps_detected=gaps_detected,
        )

    def _count_time_gaps(self, timestamps: pd.Series, timeframe: TimeFrame) -> int:
        ordered = timestamps.dropna().sort_values()
        if len(ordered) < 2:
            return 0
        expected_seconds = self.TIMEFRAME_SECONDS[timeframe]
        deltas = ordered.diff().dt.total_seconds().dropna()
        return int(deltas.gt(expected_seconds * 1.5).sum())

    def _estimate_missing_candles(self, timestamps: pd.Series, timeframe: TimeFrame) -> int:
        ordered = timestamps.dropna().sort_values()
        if len(ordered) < 2:
            return 0
        expected_seconds = self.TIMEFRAME_SECONDS[timeframe]
        deltas = ordered.diff().dt.total_seconds().dropna()
        missing = ((deltas / expected_seconds).round().astype("int64") - 1).clip(lower=0)
        return int(missing.sum())

    def _count_range_outliers(self, high: pd.Series, low: pd.Series, close: pd.Series) -> int:
        candle_range = (high - low).abs()
        median_range = candle_range[candle_range.gt(0)].median()
        if pd.isna(median_range) or median_range == 0:
            return 0
        close_change = close.pct_change().abs().replace([float("inf"), -float("inf")], pd.NA)
        range_outliers = candle_range.gt(median_range * 10)
        jump_outliers = close_change.gt(0.50)
        return int((range_outliers | jump_outliers).fillna(False).sum())

    def _report(
        self,
        market: Market,
        timeframe: TimeFrame,
        quality_score: float,
        integrity_score: float,
        warnings: list[str] | None = None,
        missing_candles: int = 0,
        duplicate_timestamps: int = 0,
        outliers_detected: int = 0,
        gaps_detected: int = 0,
    ) -> DataQualityReport:
        return DataQualityReport(
            timestamp=datetime.now(timezone.utc),
            market=market,
            timeframe=timeframe,
            quality_score=round(quality_score, 4),
            integrity_score=round(integrity_score, 4),
            warnings=warnings or [],
            missing_candles=missing_candles,
            duplicate_timestamps=duplicate_timestamps,
            outliers_detected=outliers_detected,
            gaps_detected=gaps_detected,
        )
