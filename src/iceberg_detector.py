"""Iceberg order detection engine."""
import pandas as pd
import numpy as np


class IcebergDetector:
    """Detect iceberg orders in market data."""

    def __init__(self, market_engine):
        """Initialize iceberg detector."""
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.df['iceberg_score'] = np.nan

    def detect_iceberg(self):
        """Detect potential iceberg orders."""
        for i in range(len(self.df)):
            if pd.isna(self.df['ATR14'].iloc[i]):
                continue

            vol = self.df['volume'].iloc[i]
            avg_vol = self.df['avg_volume_20'].iloc[i]
            body = self.df['body'].iloc[i]
            candle_range = self.df['range'].iloc[i]

            if candle_range == 0 or avg_vol == 0:
                continue

            # High volume with small range suggests iceberg
            vol_ratio = vol / avg_vol
            body_ratio = body / candle_range if candle_range > 0 else 0

            if vol_ratio > 1.5 and body_ratio < 0.5:
                self.df.loc[self.df.index[i], 'iceberg_score'] = min(
                    (vol_ratio - 1.0) * 0.5, 1.0
                )

    def get_iceberg(self, idx: int) -> float:
        """Get iceberg score for a candle."""
        val = self.df['iceberg_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0
