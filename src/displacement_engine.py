import pandas as pd
import numpy as np

class DisplacementEngine:
    """
    Layer 4 — Institutional Displacement scoring.
    Uses body/range, volume anomaly, range/ATR, and wick penalty.
    """
    def __init__(self, market_engine):
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.df['displacement_score'] = np.nan

    def score_all(self):
        """
        Compute displacement score for every candle.
        """
        for i in range(len(self.df)):
            if pd.isna(self.df['ATR14'].iloc[i]):
                continue

            body = self.df['body'].iloc[i]
            candle_range = self.df['range'].iloc[i]
            vol = self.df['volume'].iloc[i]
            avg_vol = self.df['avg_volume_20'].iloc[i]
            atr = self.df['ATR14'].iloc[i]
            high, low = self.df['high'].iloc[i], self.df['low'].iloc[i]
            open_, close = self.df['open'].iloc[i], self.df['close'].iloc[i]

            if candle_range == 0 or atr == 0:
                continue

            # Body fraction
            body_ratio = body / candle_range

            # Volume ratio (capped)
            vol_ratio = min(vol / avg_vol, 3.0) if avg_vol > 0 else 1.0

            # Range / ATR
            range_atr = candle_range / atr

            # Wick penalty (average of upper and lower wick fractions)
            if close >= open_:
                upper_wick = (high - close) / candle_range
                lower_wick = (open_ - low) / candle_range
            else:
                upper_wick = (high - open_) / candle_range
                lower_wick = (close - low) / candle_range
            wick_penalty = 1 - (upper_wick + lower_wick) / 2

            # Composite score
            score = (0.35 * body_ratio + 0.30 * vol_ratio + 0.25 * range_atr + 0.10 * wick_penalty)
            score = min(score, 1.0)

            if score > 0.55:  # minimum to be considered
                self.df.loc[self.df.index[i], 'displacement_score'] = score

    def get_score(self, idx: int) -> float:
        val = self.df['displacement_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0