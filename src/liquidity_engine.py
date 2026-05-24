"""Liquidity analysis engine."""
import pandas as pd
import numpy as np


class LiquidityEngine:
    """Layer 3 — Liquidity sweep detection."""

    def __init__(self, market_engine, threshold=0.0005):
        """Initialize liquidity engine."""
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.threshold = threshold
        self.df['sweep_score'] = np.nan

    def detect_sweeps(self):
        """Detect liquidity sweeps in market data."""
        for i in range(1, len(self.df)):
            h1 = self.df['high'].iloc[i-1]
            h2 = self.df['high'].iloc[i]
            l1 = self.df['low'].iloc[i-1]
            l2 = self.df['low'].iloc[i]

            if h1 == 0 or l1 == 0:
                continue

            high_sweep = abs(h1 - h2) / h1 < self.threshold
            low_sweep = abs(l1 - l2) / l1 < self.threshold

            if high_sweep or low_sweep:
                self.df.loc[self.df.index[i], 'sweep_score'] = 0.5

    def get_sweep(self, idx: int) -> float:
        """Get sweep score for a candle."""
        val = self.df['sweep_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0
