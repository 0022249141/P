"""Volume profile and VPOC detection."""
import pandas as pd
import numpy as np


class VolumeProfileEngine:
    """Layer 8 — Volume Profile & VPOC detection.

    Builds a dynamic volume profile over a lookback window and
    identifies VPOC.
    """

    def __init__(self, market_engine, lookback_candles=96):
        """Initialize volume profile engine.

        Args:
            market_engine: Market data engine
            lookback_candles: 96 candles of 15min = 24h
        """
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.lookback = lookback_candles
        self.df['vpoc'] = np.nan
        self._calculate_vpoc()

    def _calculate_vpoc(self, num_bins=50):
        """Compute rolling VPOC for each candle.

        Based on previous N candles.
        """
        for i in range(self.lookback, len(self.df)):
            window = self.df.iloc[i - self.lookback : i]
            price_range = np.linspace(window['low'].min(),
                                      window['high'].max(),
                                      num_bins)
            volume_profile = np.zeros(num_bins - 1)

            for _, row in window.iterrows():
                # Distribute volume proportionally across price bins
                low, high, vol = row['low'], row['high'], row['volume']
                if high == low:
                    continue
                # Find bin indices that overlap with candle range
                for j in range(num_bins - 1):
                    bin_low = price_range[j]
                    bin_high = price_range[j+1]
                    overlap = max(
                        0, min(high, bin_high) - max(low, bin_low)
                    )
                    if overlap > 0:
                        volume_profile[j] += vol * (
                            overlap / (high - low)
                        )

            if volume_profile.sum() > 0:
                max_bin = np.argmax(volume_profile)
                vpoc_price = (
                    (price_range[max_bin] + price_range[max_bin+1])
                    / 2
                )
                self.df.loc[self.df.index[i], 'vpoc'] = vpoc_price

    def get_vpoc(self, idx: int) -> float:
        """Get VPOC price for a candle."""
        val = self.df['vpoc'].iloc[idx]
        return val if not pd.isna(val) else None
