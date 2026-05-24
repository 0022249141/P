# 04_liquidity.py — نسخه جدید با آستانه‌های کالیبره‌شده
import pandas as pd
import numpy as np

class LiquidityEngine:
    def __init__(self, market_engine, market_name: str = "XAUUSD"):
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.df['sweep_score'] = np.nan
        self.market_name = market_name

    @property
    def threshold(self) -> float:
        """آستانه EQH/EQL کالیبره‌شده برای هر بازار"""
        from market_params import LIQUIDITY_THRESHOLDS
        return LIQUIDITY_THRESHOLDS.get(self.market_name, 0.0005)

    @property
    def sweep_threshold(self) -> float:
        """آستانه نفوذ جاروب برای هر بازار"""
        from market_params import MARKET_XAUUSD, MARKET_ABSHODE, MARKET_HARAT
        market_map = {
            "XAUUSD": MARKET_XAUUSD,
            "AbshodeNaghdi": MARKET_ABSHODE,
            "HaratUSD": MARKET_HARAT,
        }
        cfg = market_map.get(self.market_name, MARKET_XAUUSD)
        return cfg["liquidity"]["liquidity_sweep_threshold_pct"]

    def detect_equal_highs_lows(self):
        """تشخیص سقف/کف مساوی با آستانه مختص بازار"""
        eqh_eql_threshold = self.threshold

        for i in range(2, len(self.df)):
            if pd.isna(self.df['ATR14'].iloc[i]):
                continue

            price_i = self.df['close'].iloc[i]
            price_prev = self.df['close'].iloc[i - 1]

            if abs(price_i - price_prev) / price_prev < eqh_eql_threshold:
                # ثبت به‌عنوان EQH/EQL بالقوه
                pass

    def detect_sweeps(self):
        """تشخیص جاروب نقدینگی با آستانه اختصاصی هر بازار"""
        highs = self.df['swing_high'] if 'swing_high' in self.df.columns else self.df['high']
        lows = self.df['swing_low'] if 'swing_low' in self.df.columns else self.df['low']
        avg_atr = self.df['ATR14'].mean()
        min_pen_pct = self.sweep_threshold  # آستانه نفوذ کالیبره‌شده

        for i in range(3, len(self.df)):
            if pd.isna(self.df['ATR14'].iloc[i]):
                continue

            atr = self.df['ATR14'].iloc[i]
            high, low = self.df['high'].iloc[i], self.df['low'].iloc[i]
            close = self.df['close'].iloc[i]
            vol = self.df['volume'].iloc[i]
            avg_vol = self.df['avg_volume_20'].iloc[i]

            prev_highs = highs.iloc[:i].dropna()
            prev_lows = lows.iloc[:i].dropna()
            sweep = 0.0

            # حداقل نفوذ: 0.3 * ATR یا درصد بازار (هرکدام بزرگتر)
            min_penetration = max(0.3 * atr, min_pen_pct * close)

            if not prev_highs.empty:
                last_high = prev_highs.iloc[-1]
                if high > last_high and (high - last_high) > min_penetration:
                    penetration = (high - last_high) / atr
                    reclaim = 1.0 if close < last_high else 0.0
                    speed = (high - close) / (high - low) if high > low else 0.0
                    vol_factor = min(vol / avg_vol, 3.0) if avg_vol > 0 else 1.0
                    sweep = (penetration * 0.3 + reclaim * 0.4 + speed * 0.2 + vol_factor * 0.1)
                    sweep = min(sweep, 1.0)

            if not prev_lows.empty:
                last_low = prev_lows.iloc[-1]
                if low < last_low and (last_low - low) > min_penetration:
                    penetration = (last_low - low) / atr
                    reclaim = 1.0 if close > last_low else 0.0
                    speed = (close - low) / (high - low) if high > low else 0.0
                    vol_factor = min(vol / avg_vol, 3.0) if avg_vol > 0 else 1.0
                    sweep_bull = (penetration * 0.3 + reclaim * 0.4 + speed * 0.2 + vol_factor * 0.1)
                    sweep = max(sweep, min(sweep_bull, 1.0))

            if avg_atr > 0:
                dynamic_threshold = 0.5 + 0.3 * (atr / avg_atr)
            else:
                dynamic_threshold = 0.6
            dynamic_threshold = min(dynamic_threshold, 0.85)

            if sweep > dynamic_threshold:
                self.df.loc[self.df.index[i], 'sweep_score'] = sweep

    def get_sweep(self, idx: int) -> float:
        val = self.df['sweep_score'].iloc[idx]
        return val if not pd.isna(val) else 0.0