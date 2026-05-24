"""Multi-timeframe analyzer."""
import pandas as pd
import numpy as np


class MTFAnalyzer:
    """Multi-timeframe analysis."""

    def __init__(self, market_engine):
        """Initialize MTF analyzer."""
        self.mkt = market_engine
        self.df = market_engine.df.copy()

    def resample_timeframe(self, timeframe_minutes: int):
        """Resample to higher timeframe."""
        resampled = self.df.set_index('timestamp').resample(
            f'{timeframe_minutes}min'
        ).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        return resampled
