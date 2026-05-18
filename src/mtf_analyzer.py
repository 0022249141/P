import pandas as pd
import numpy as np
from market_engine import MarketDataEngine

class MTFAnalyzer:
    def __init__(self, h1_csv, h4_csv, daily_csv):
        self.h1 = MarketDataEngine.from_custom_csv(h1_csv) if h1_csv else None
        self.h4 = MarketDataEngine.from_custom_csv(h4_csv) if h4_csv else None
        self.daily = MarketDataEngine.from_custom_csv(daily_csv) if daily_csv else None

    def get_htf_bias(self, timestamp):
        """
        Returns a bias score: -1 (bearish) to 1 (bullish), 0 neutral.
        Based on EMAs and structure on daily timeframe.
        """
        if self.daily is None:
            return 0.0
        df = self.daily.df
        # پیدا کردن آخرین کندل قبل از timestamp
        mask = df['timestamp'] <= timestamp
        if mask.sum() == 0:
            return 0.0
        idx = df.index[mask][-1]
        ema20 = df['close'].ewm(span=20).mean()
        ema50 = df['close'].ewm(span=50).mean()
        if pd.isna(ema20.iloc[idx]) or pd.isna(ema50.iloc[idx]):
            return 0.0
        # قدرت روند
        diff = (ema20.iloc[idx] - ema50.iloc[idx]) / df['ATR14'].iloc[idx]
        return np.clip(diff, -1.0, 1.0)

    def get_key_levels(self, timestamp):
        """سطوح کلیدی روزانه: high, low, close قبلی"""
        if self.daily is None:
            return {}
        df = self.daily.df
        mask = df['timestamp'] < timestamp
        if mask.sum() == 0:
            return {}
        last_idx = df.index[mask][-1]
        return {
            'daily_high': df['high'].iloc[last_idx],
            'daily_low': df['low'].iloc[last_idx],
            'daily_close': df['close'].iloc[last_idx]
        }
