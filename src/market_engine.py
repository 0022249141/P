"""Market data engine for data processing and calculations."""
import pandas as pd
import numpy as np


class MarketDataEngine:
    """Layer 1 — Adaptive Market Data Engine.

    Computes ATR, volatility regime, and normalized metrics.
    """

    def __init__(self, df: pd.DataFrame, atr_period: int = 14,
                 regime_lookback: int = 100):
        """Initialize market data engine."""
        self.df = df.copy()
        self.atr_period = atr_period
        self.regime_lookback = regime_lookback

        # True Range & ATR
        self._calculate_tr()
        self.df['ATR14'] = self._calculate_atr(atr_period)
        self.df['avg_volume_20'] = self.df['volume'].rolling(20).mean()

        # Adaptive regime thresholds (percentiles)
        self.df['atr_low_percentile'] = self.df['ATR14'].rolling(
            regime_lookback
        ).apply(
            lambda x: np.percentile(x, 25) if len(
                x) == regime_lookback else np.nan, raw=True
        )
        self.df['atr_high_percentile'] = self.df['ATR14'].rolling(
            regime_lookback
        ).apply(
            lambda x: np.percentile(x, 75) if len(
                x) == regime_lookback else np.nan, raw=True
        )

        # Auxiliary columns
        self.df['range'] = self.df['high'] - self.df['low']
        self.df['body'] = np.abs(self.df['close'] - self.df['open'])
        if 'spread' not in self.df.columns:
            self.df['spread'] = 0.0

    @classmethod
    def from_custom_csv(cls, filepath: str, atr_period=14,
                        regime_lookback=100):
        """Load a cleaned CSV (comma-separated, with header).

        Expected columns: timestamp,open,high,low,close,volume
        """
        df = pd.read_csv(filepath, sep=',')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)

        return cls(df, atr_period=atr_period,
                   regime_lookback=regime_lookback)

    def _calculate_tr(self):
        """Calculate true range."""
        high = self.df['high']
        low = self.df['low']
        close_prev = self.df['close'].shift(1)
        tr1 = high - low
        tr2 = np.abs(high - close_prev)
        tr3 = np.abs(low - close_prev)
        self.df['tr'] = np.maximum(tr1, np.maximum(tr2, tr3))

    def _calculate_atr(self, period: int) -> pd.Series:
        """Calculate Average True Range."""
        return self.df['tr'].ewm(span=period, adjust=False).mean()

    def get_regime(self, idx: int) -> str:
        """Get volatility regime at index."""
        if idx < self.regime_lookback:
            return "NORMAL"
        atr_now = self.df['ATR14'].iloc[idx]
        low_p = self.df['atr_low_percentile'].iloc[idx]
        high_p = self.df['atr_high_percentile'].iloc[idx]
        if pd.isna(low_p) or pd.isna(high_p):
            return "NORMAL"
        if atr_now < low_p:
            return "LOW_VOL"
        if atr_now > high_p:
            return "HIGH_VOL"
        return "NORMAL"
