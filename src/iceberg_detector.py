import pandas as pd
import numpy as np

class IcebergDetector:
    """
    Layer 9 — Iceberg Order footprint simulation.
    Identifies candles with abnormally high volume, small range, and strong rejection.
    """
    def __init__(self, market_engine, vol_threshold=2.0, range_percentile=30):
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.df['iceberg_score'] = np.nan
        self.vol_threshold = vol_threshold  # volume / avg_volume
        self.range_percentile = range_percentile  # candle range vs recent ATR
        self._detect()

    def _detect(self):
        for i in range(50, len(self.df)):
            atr = self.df['ATR14'].iloc[i]
            if pd.isna(atr):
                continue
            vol_ratio = self.df['volume'].iloc[i] / self.df['avg_volume_20'].iloc[i]
            range_atr = self.df['range'].iloc[i] / atr
            recent_ranges = self.df['range'].iloc[max(0, i-20):i] / self.df['ATR14'].iloc[max(0, i-20):i]
            range_threshold = np.percentile(recent_ranges, self.range_percentile) if len(recent_ranges) > 5 else 0.2

            if vol_ratio > self.vol_threshold and range_atr < range_threshold:
                # Bullish iceberg: small candle but closes near high
                if self.df['close'].iloc[i] > self.df['open'].iloc[i] and (self.df['high'].iloc[i] - self.df['close'].iloc[i]) < 0.3 * self.df['range'].iloc[i]:
                    score = min((vol_ratio / self.vol_threshold) * (1 - range_atr / range_threshold), 1.0)
                    self.df.loc[self.df.index[i], 'iceberg_score'] = score
                # Bearish iceberg
                elif self.df['close'].iloc[i] < self.df['open'].iloc[i] and (self.df['close'].iloc[i] - self.df['low'].iloc[i]) < 0.3 * self.df['range'].iloc[i]:
                    score = min((vol_ratio / self.vol_threshold) * (1 - range_atr / range_threshold), 1.0)
                    self.df.loc[self.df.index[i], 'iceberg_score'] = -score

    def get_iceberg(self, idx: int) -> float:
        val = self.df['iceberg_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0
