"""Fair Value Gap and Order Block detection engine."""
import pandas as pd
import numpy as np


class ZoneEngine:
    """Layer 5 — FVG and Order Block detection.

    Includes mitigation state tracking.
    """

    def __init__(self, market_engine, displacement_engine):
        """Initialize zone engine."""
        self.mkt = market_engine
        self.disp = displacement_engine
        self.df = market_engine.df.copy()
        self.df['fvg_score'] = np.nan
        self.df['ob_score'] = np.nan

    def detect_fvg(self):
        """Detect Fair Value Gaps based on ATR-normalized gap.

        Requires a preceding displacement.
        """
        for i in range(2, len(self.df)):
            atr = self.df['ATR14'].iloc[i]
            if pd.isna(atr) or atr == 0:
                continue

            # Bullish FVG: candle[i].low > candle[i-2].high
            if self.df['low'].iloc[i] > self.df['high'].iloc[i-2]:
                gap = self.df['low'].iloc[i] - self.df['high'].iloc[
                    i-2
                ]
                # Minimum gap = 20th percentile of recent ATR
                recent_atr = self.df['ATR14'].iloc[
                    max(0, i-50):i
                ]
                min_gap = (
                    np.percentile(recent_atr, 20)
                    if len(recent_atr) > 10 else 0.1*atr
                )

                if gap >= min_gap and self.disp.get_score(i) > 0:
                    # Mitigation state (track later)
                    self.df.loc[self.df.index[i], 'fvg_score'] = min(
                        gap / atr, 1.0
                    )

            # Bearish FVG: candle[i].high < candle[i-2].low
            if self.df['high'].iloc[i] < self.df['low'].iloc[i-2]:
                gap = self.df['low'].iloc[i-2] - self.df['high'].iloc[i]
                recent_atr = self.df['ATR14'].iloc[
                    max(0, i-50):i
                ]
                min_gap = (
                    np.percentile(recent_atr, 20)
                    if len(recent_atr) > 10 else 0.1*atr
                )

                if gap >= min_gap and self.disp.get_score(i) > 0:
                    self.df.loc[self.df.index[i], 'fvg_score'] = min(
                        gap / atr, 1.0
                    )

    def detect_ob(self):
        """Detect Order Block candidates.

        Last opposing candle before a displacement.
        """
        for i in range(2, len(self.df)):
            if self.disp.get_score(i) > 0.65:
                # Last candle before this displacement is potential OB
                if self.df['close'].iloc[i] > self.df['open'].iloc[i]:
                    # bullish displacement
                    ob_idx = i - 1
                    if ob_idx >= 0:
                        # Bearish OB (opposing candle)
                        ob_score = (
                            self.df['body'].iloc[ob_idx] /
                            self.df['range'].iloc[ob_idx]
                            if self.df['range'].iloc[ob_idx] > 0
                            else 0.5
                        )
                        if (
                            self.df['close'].iloc[ob_idx] <
                            self.df['open'].iloc[ob_idx]
                        ):  # bearish candle
                            self.df.loc[
                                self.df.index[ob_idx], 'ob_score'
                            ] = ob_score
                else:  # bearish displacement
                    ob_idx = i - 1
                    if ob_idx >= 0:
                        ob_score = (
                            self.df['body'].iloc[ob_idx] /
                            self.df['range'].iloc[ob_idx]
                            if self.df['range'].iloc[ob_idx] > 0
                            else 0.5
                        )
                        if (
                            self.df['close'].iloc[ob_idx] >
                            self.df['open'].iloc[ob_idx]
                        ):  # bullish candle
                            self.df.loc[
                                self.df.index[ob_idx], 'ob_score'
                            ] = ob_score

    def get_fvg_score(self, idx: int) -> float:
        """Get FVG score for a candle."""
        val = self.df['fvg_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0

    def get_ob_score(self, idx: int) -> float:
        """Get order block score for a candle."""
        val = self.df['ob_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0
