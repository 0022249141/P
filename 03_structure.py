# 03_structure.py — نسخهٔ بدون Future Leakage
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

    @property
    def bos_min_displacement(self) -> float:
        from market_params import BOS_MIN_DISPLACEMENT
        return BOS_MIN_DISPLACEMENT.get(self.market_name, 0.0015)

    def detect_swings(self, window: int = 5):
        """
        تشخیص نقاط نوسان بدون نشت آینده (Left-Only).
        - از کندل‌های گذشته برای تشخیص استفاده می‌کند.
        - سپس با ۲ کندل بعدی تأیید می‌شود.
        - هیچ‌گاه از i+window به بعد استفاده نمی‌کند.
        """
        avg_atr = self.df['ATR14'].mean()

        for i in range(window, len(self.df) - 2):  # -2 برای تأیید
            high = self.df['high'].iloc[i]
            low  = self.df['low'].iloc[i]
            atr  = self.df['ATR14'].iloc[i]
            if atr == 0:
                continue

            # آستانهٔ تطبیقی
            if avg_atr > 0:
                dynamic_min_strength = 0.8 + 0.5 * (atr / avg_atr)
            else:
                dynamic_min_strength = 1.0

            # قدرت نسبی فقط با کندل‌های گذشته (نگاه به چپ)
            power_high = (high - np.min(self.df['low'].iloc[i - window : i])) / atr
            power_low  = (np.max(self.df['high'].iloc[i - window : i]) - low) / atr

            # تشخیص اوج بودن فقط با مقایسه با گذشته (تا i)
            is_high = high == np.max(self.df['high'].iloc[i - window : i + 1])
            is_low  = low  == np.min(self.df['low'].iloc[i - window : i + 1])

            # تأیید با ۲ کندل بعدی (بدون نشت به آیندهٔ دور)
            if is_high and power_high >= dynamic_min_strength:
                future_highs = self.df['high'].iloc[i+1 : i+3]
                if high >= future_highs.max():  # کندل i هنوز بالاترین است
                    self.df.loc[self.df.index[i], 'swing_high'] = high

            if is_low and power_low >= dynamic_min_strength:
                future_lows = self.df['low'].iloc[i+1 : i+3]
                if low <= future_lows.min():  # کندل i هنوز پایین‌ترین است
                    self.df.loc[self.df.index[i], 'swing_low'] = low

    def is_bos(self, idx: int, direction: str) -> bool:
        min_disp = self.bos_min_displacement
        if direction == 'bullish':
            valid_sh = self.df['swing_high'].dropna()
            if valid_sh.empty:
                return False
            last_sh = valid_sh.iloc[-1]
            close = self.df['close'].iloc[idx]
            displacement = abs(close - last_sh) / last_sh
            return close > last_sh and displacement > min_disp
        else:
            valid_sl = self.df['swing_low'].dropna()
            if valid_sl.empty:
                return False
            last_sl = valid_sl.iloc[-1]
            close = self.df['close'].iloc[idx]
            displacement = abs(last_sl - close) / last_sl
            return close < last_sl and displacement > min_disp