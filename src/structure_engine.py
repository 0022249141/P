"""Structural analysis engine."""
import pandas as pd
import numpy as np


class StructuralEngine:
    """Layer 2 — Structural analysis with swing strength.

    Repaint-free implementation.
    """

    def __init__(self, market_engine):
        """Initialize structural engine."""
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        # Ensure swing columns exist from the start
        self.df['swing_high'] = np.nan
        self.df['swing_low'] = np.nan

    def detect_swings(self, window: int = 5,
                     min_strength: float = 0.8):
        """Detect swing highs and lows using relative strength.

        Uses ATR-based strength calculation. No repaint: uses a
        centered window.
        """
        # Redundant safety check
        if 'swing_high' not in self.df.columns:
            self.df['swing_high'] = np.nan
        if 'swing_low' not in self.df.columns:
            self.df['swing_low'] = np.nan

        for i in range(window, len(self.df) - window):
            high = self.df['high'].iloc[i]
            low = self.df['low'].iloc[i]
            atr = self.df['ATR14'].iloc[i]
            if atr == 0:
                continue

            # Strength relative to preceding range
            power_high = (
                high - np.min(self.df['low'].iloc[i - window : i])
            ) / atr
            power_low = (
                np.max(self.df['high'].iloc[i - window : i]) - low
            ) / atr

            is_high = high == np.max(
                self.df['high'].iloc[i - window : i + window + 1]
            )
            is_low = low == np.min(
                self.df['low'].iloc[i - window : i + window + 1]
            )

            if is_high and power_high >= min_strength:
                self.df.loc[self.df.index[i], 'swing_high'] = high
            if is_low and power_low >= min_strength:
                self.df.loc[self.df.index[i], 'swing_low'] = low

    def is_bos(self, idx: int, direction: str) -> bool:
        """Check Break of Structure with penetration buffer.

        Args:
            idx: Candle index
            direction: 'bullish' (break above last swing high) or
                      'bearish'

        Returns:
            True if BOS detected
        """
        if direction == 'bullish':
            valid_sh = self.df['swing_high'].dropna()
            if valid_sh.empty:
                return False
            last_sh = valid_sh.iloc[-1]
            close = self.df['close'].iloc[idx]
            atr = self.df['ATR14'].iloc[idx]
            return close > last_sh and (close - last_sh) > 0.1 * atr
        # bearish
        valid_sl = self.df['swing_low'].dropna()
        if valid_sl.empty:
            return False
        last_sl = valid_sl.iloc[-1]
        close = self.df['close'].iloc[idx]
        atr = self.df['ATR14'].iloc[idx]
        return close < last_sl and (last_sl - close) > 0.1 * atr
