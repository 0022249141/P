import pandas as pd
import numpy as np

class LiquidityEngine:
    def __init__(self, market_engine):
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.df['sweep_score'] = np.nan

    def detect_sweeps(self):
        highs = self.df['swing_high'] if 'swing_high' in self.df.columns else self.df['high']
        lows  = self.df['swing_low']  if 'swing_low'  in self.df.columns else self.df['low']

        for i in range(3, len(self.df)):
            if pd.isna(self.df['ATR14'].iloc[i]):
                continue

            atr = self.df['ATR14'].iloc[i]
            high, low = self.df['high'].iloc[i], self.df['low'].iloc[i]
            close = self.df['close'].iloc[i]
            vol = self.df['volume'].iloc[i]
            avg_vol = self.df['avg_volume_20'].iloc[i]

            prev_highs = highs.iloc[:i].dropna()
            prev_lows  = lows.iloc[:i].dropna()

            sweep = 0.0

            if not prev_highs.empty:
                last_high = prev_highs.iloc[-1]
                if high > last_high:
                    penetration = (high - last_high) / atr
                    reclaim = 1.0 if close < last_high else 0.0
                    speed = (high - close) / (high - low) if high > low else 0.0
                    vol_factor = min(vol / avg_vol, 3.0) if avg_vol > 0 else 1.0
                    sweep = (penetration * 0.3 + reclaim * 0.3 + speed * 0.2 + vol_factor * 0.2)
                    sweep = min(sweep, 1.0)

            if not prev_lows.empty:
                last_low = prev_lows.iloc[-1]
                if low < last_low:
                    penetration = (last_low - low) / atr
                    reclaim = 1.0 if close > last_low else 0.0
                    speed = (close - low) / (high - low) if high > low else 0.0
                    vol_factor = min(vol / avg_vol, 3.0) if avg_vol > 0 else 1.0
                    sweep_bull = (penetration * 0.3 + reclaim * 0.3 + speed * 0.2 + vol_factor * 0.2)
                    sweep = max(sweep, min(sweep_bull, 1.0))

            if sweep > 0.3:
                self.df.loc[self.df.index[i], 'sweep_score'] = sweep

    def get_sweep(self, idx: int) -> float:
        val = self.df['sweep_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0