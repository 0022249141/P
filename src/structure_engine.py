# 03_structure.py — نسخهٔ برداری برای Swing Detection
import pandas as pd
import numpy as np

class StructuralEngine:
    def __init__(self, market_engine, market_name: str = "XAUUSD"):
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.market_name = market_name

        if 'swing_high' not in self.df.columns:
            self.df['swing_high'] = np.nan
        if 'swing_low' not in self.df.columns:
            self.df['swing_low'] = np.nan

    def detect_swings(self, window: int = 5):
        """تشخیص سوئینگ به‌صورت برداری (بدون حلقه)"""
        df = self.df
        high = df['high']
        low  = df['low']
        atr  = df['ATR14']
        avg_atr = atr.mean()

        # قدرت نوسان با rolling (نگاه به گذشته)
        power_high = (high - low.rolling(window=window, min_periods=1).min().shift(1)) / atr
        power_low  = (high.rolling(window=window, min_periods=1).max().shift(1) - low) / atr

        # تشخیص اوج بودن: آیا high در ۲ کندل بعدی هم بالاترین است؟
        # برای جلوگیری از نشت آینده، فقط با دو کندل بعدی چک می‌کنیم
        future_max_high = high.shift(-1).rolling(2).max()  # حداکثر دو کندل آینده
        is_high = (high > high.shift(window).rolling(window).max()) & (high >= future_max_high)
        is_low  = (low < low.shift(window).rolling(window).min()) & (low <= low.shift(-1).rolling(2).min())

        # آستانه تطبیقی
        dynamic_strength = np.clip(0.8 + 0.5 * (atr / avg_atr), 0.8, 1.5)

        # اعمال
        mask_high = is_high & (power_high >= dynamic_strength)
        mask_low  = is_low  & (power_low  >= dynamic_strength)

        df.loc[mask_high, 'swing_high'] = high[mask_high]
        df.loc[mask_low,  'swing_low']  = low[mask_low]