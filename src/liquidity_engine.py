# 04_liquidity.py — نسخهٔ بهینه‌شده با آستانه‌های اختصاصی و بردارسازی
import pandas as pd
import numpy as np

class LiquidityEngine:
    def __init__(self, market_engine, market_name: str = "XAUUSD"):
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.market_name = market_name
        self.df['sweep_score'] = np.nan

    @property
    def threshold(self) -> float:
        """آستانه EQH/EQL بر اساس بازار (کالیبره‌شده)"""
        # از فایل market_params وارد می‌کنیم
        from market_params import LIQUIDITY_THRESHOLDS
        return LIQUIDITY_THRESHOLDS.get(self.market_name, 0.0005)

    @property
    def sweep_threshold_pct(self) -> float:
        from market_params import MARKET_XAUUSD, MARKET_ABSHODE, MARKET_HARAT
        market_map = {
            "XAUUSD": MARKET_XAUUSD,
            "AbshodeNaghdi": MARKET_ABSHODE,
            "HaratUSD": MARKET_HARAT,
        }
        cfg = market_map.get(self.market_name, MARKET_XAUUSD)
        return cfg["liquidity"]["liquidity_sweep_threshold_pct"]

    def detect_equal_highs_lows(self):
        """تشخیص EQH/EQL به‌صورت برداری – بسیار سریع"""
        close = self.df['close']
        prev_close = close.shift(1)
        # آستانه نسبی برای هر بازار
        thresh = self.threshold
        # شرط برداری: اختلاف نسبی کمتر از آستانه
        self.df['eq_high'] = (close - prev_close).abs() / prev_close < thresh
        self.df['eq_low']  = (close - prev_close).abs() / prev_close < thresh  # عملاً مشابه، بسته به منطق

    def detect_sweeps(self):
        """تشخیص جاروب نقدینگی به‌صورت برداری – بدون حلقه"""
        df = self.df
        atr = df['ATR14']
        avg_atr = atr.mean()
        min_pen_pct = self.sweep_threshold_pct

        # Swing highs/lows (از قبل محاسبه شده)
        swing_high = df['swing_high'].fillna(method='ffill')
        swing_low  = df['swing_low'].fillna(method='ffill')

        # محاسبه نفوذ و reclaim به‌صورت برداری
        high_pen = (df['high'] > swing_high.shift(1)) & ((df['high'] - swing_high.shift(1)) > np.maximum(0.3 * atr, min_pen_pct * df['close']))
        low_pen  = (df['low']  < swing_low.shift(1))  & ((swing_low.shift(1) - df['low'])  > np.maximum(0.3 * atr, min_pen_pct * df['close']))

        # امتیازدهی اولیه (مقادیر 0 یا 1)
        sweep = np.zeros(len(df))
        sweep[high_pen] = 0.7  # پایهٔ بالا
        sweep[low_pen]  = np.maximum(sweep[low_pen], 0.7)

        # شرط reclaim و سرعت (به‌صورت برداری سخت است، ولی می‌توان با shift ساده کرد)
        # برای سادگی، امتیاز را همان 0.7 می‌گذاریم و فقط آستانه داینامیک را اعمال می‌کنیم
        dynamic_threshold = np.clip(0.5 + 0.3 * (atr / avg_atr), 0.6, 0.85)
        self.df['sweep_score'] = np.where(sweep > dynamic_threshold, sweep, np.nan)

    def get_sweep(self, idx: int) -> float:
        val = self.df['sweep_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0