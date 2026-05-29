# 04_liquidity.py — تشخیص Sweep یکپارچه با Clustering و Fallback
import pandas as pd
import numpy as np
from core_constants import IMMUTABLE

class LiquidityEngine:
    def __init__(self, market_engine, market_name: str = "XAUUSD"):
        self.mkt = market_engine
        self.df = market_engine.df.copy()
        self.df['sweep_score'] = np.nan
        self.market_name = market_name

    @property
    def threshold(self) -> float:
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

    def _cluster_levels(self, prices, atr):
        if len(prices) == 0:
            return []
        sorted_prices = sorted(prices)
        cluster_gap = IMMUTABLE["SWEEP_CLUSTER_GAP_ATR_MULT"] * atr
        clusters = []
        current_cluster = [sorted_prices[0]]
        for p in sorted_prices[1:]:
            if p - current_cluster[-1] <= cluster_gap:
                current_cluster.append(p)
            else:
                clusters.append(current_cluster)
                current_cluster = [p]
        clusters.append(current_cluster)
        return [np.mean(c) for c in clusters]

    def detect_sweeps(self):
        # اگر ستون swing_high/swing_low وجود نداشت، از high/low استفاده کن
        if 'swing_high' in self.df.columns:
            highs_series = self.df['swing_high']
        else:
            highs_series = self.df['high']

        if 'swing_low' in self.df.columns:
            lows_series = self.df['swing_low']
        else:
            lows_series = self.df['low']

        avg_atr = self.df['ATR14'].mean()
        min_pen_pct = self.sweep_threshold_pct

        for i in range(3, len(self.df)):
            if pd.isna(self.df['ATR14'].iloc[i]):
                continue

            atr = self.df['ATR14'].iloc[i]
            high, low = self.df['high'].iloc[i], self.df['low'].iloc[i]
            close = self.df['close'].iloc[i]
            vol = self.df['volume'].iloc[i]
            avg_vol = self.df['avg_volume_20'].iloc[i]

            prev_highs = highs_series.iloc[:i].dropna().tolist()
            prev_lows  = lows_series.iloc[:i].dropna().tolist()
            clustered_highs = self._cluster_levels(prev_highs, atr)
            clustered_lows  = self._cluster_levels(prev_lows, atr)

            sweep = 0.0
            min_penetration = max(0.3 * atr, min_pen_pct * close)

            if len(clustered_highs) > 0:
                last_high = clustered_highs[-1]
                if high > last_high and (high - last_high) > min_penetration:
                    penetration = (high - last_high) / atr
                    reclaim = 1.0 if close < last_high else 0.0
                    speed = (high - close) / (high - low) if high > low else 0.0
                    vol_factor = min(vol / avg_vol, 3.0) if avg_vol > 0 else 1.0
                    sweep = (penetration * 0.3 + reclaim * 0.4 + speed * 0.2 + vol_factor * 0.1)
                    sweep = min(sweep, 1.0)

            if len(clustered_lows) > 0:
                last_low = clustered_lows[-1]
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