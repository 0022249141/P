"""
engines/liquidity_classifier.py
Classifies liquidity into Consumable, Transfer, or Delivery.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
import numpy as np
import pandas as pd
from core.schemas import LiquidityClass, LiquidityLevel, LiquidityMap, LiquiditySide, Market, TimeFrame


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


class LiquidityClassifier:
    def __init__(self, swing_strength: int = 5, freshness_decay: float = 0.03):
        self.swing_strength = max(2, int(swing_strength))
        self.freshness_decay = max(0.0, float(freshness_decay))

    def build_liquidity_map(self, candles: pd.DataFrame, market: Market = Market.ABSHODEH, timeframe: TimeFrame = TimeFrame.H1, existing_liquidity: Optional[List[LiquidityLevel]] = None) -> LiquidityMap:
        now = pd.Timestamp.utcnow().to_pydatetime()
        if candles is None or candles.empty or not {"high", "low", "close"}.issubset(candles.columns):
            return LiquidityMap(market=market, timeframe=timeframe, timestamp=now)
        df = candles.copy()
        for col in ["high", "low", "close", "open"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["high", "low", "close"]).reset_index(drop=True)
        if len(df) < self.swing_strength * 2 + 1:
            return LiquidityMap(market=market, timeframe=timeframe, timestamp=self._timestamp(df))

        swing_highs = self._find_swing_highs(df)
        swing_lows = self._find_swing_lows(df)
        current_price = float(df["close"].iloc[-1])
        total = len(df)
        buy_side_levels: List[LiquidityLevel] = []
        sell_side_levels: List[LiquidityLevel] = []

        for idx, price in swing_highs:
            buy_side_levels.append(self._classify_level(df, idx, float(price), current_price, total, is_high=True))
        for idx, price in swing_lows:
            sell_side_levels.append(self._classify_level(df, idx, float(price), current_price, total, is_high=False))

        for level in existing_liquidity or []:
            if str(level.type).lower() == "high":
                buy_side_levels.append(level)
            elif str(level.type).lower() == "low":
                sell_side_levels.append(level)

        nearest_buy = min([l.price for l in buy_side_levels if l.price > current_price], default=None, key=lambda p: p - current_price)
        nearest_sell = max([l.price for l in sell_side_levels if l.price < current_price], default=None, key=lambda p: current_price - p)
        engineered = self._detect_engineered_zones(buy_side_levels + sell_side_levels, self._typical_range(df), current_price)

        return LiquidityMap(
            market=market, timeframe=timeframe, timestamp=self._timestamp(df),
            buy_side_levels=buy_side_levels, sell_side_levels=sell_side_levels,
            nearest_consumable_buy=nearest_buy, nearest_consumable_sell=nearest_sell,
            engineered_liquidity_zones=engineered,
        )

    def _timestamp(self, df: pd.DataFrame):
        if "timestamp" in df.columns and len(df):
            ts = pd.to_datetime(df["timestamp"].iloc[-1], errors="coerce")
            if pd.notna(ts):
                return ts.to_pydatetime()
        return pd.Timestamp.utcnow().to_pydatetime()

    def _find_swing_highs(self, candles: pd.DataFrame) -> List[Tuple[int, float]]:
        highs = candles["high"].to_numpy(dtype=float)
        swings: List[Tuple[int, float]] = []
        last_price = None
        for i in range(self.swing_strength, len(highs) - self.swing_strength):
            window = highs[i - self.swing_strength:i + self.swing_strength + 1]
            if highs[i] == np.nanmax(window) and (last_price is None or abs(highs[i] - last_price) > 1e-12):
                swings.append((i, highs[i])); last_price = highs[i]
        return swings

    def _find_swing_lows(self, candles: pd.DataFrame) -> List[Tuple[int, float]]:
        lows = candles["low"].to_numpy(dtype=float)
        swings: List[Tuple[int, float]] = []
        last_price = None
        for i in range(self.swing_strength, len(lows) - self.swing_strength):
            window = lows[i - self.swing_strength:i + self.swing_strength + 1]
            if lows[i] == np.nanmin(window) and (last_price is None or abs(lows[i] - last_price) > 1e-12):
                swings.append((i, lows[i])); last_price = lows[i]
        return swings

    def _classify_level(self, candles: pd.DataFrame, idx: int, price: float, current_price: float, total_candles: int, is_high: bool) -> LiquidityLevel:
        typical_range = max(self._typical_range(candles), current_price * 0.0005, 1e-9)
        candles_since = max(0, total_candles - idx - 1)
        age_freshness = max(0.0, 1.0 - candles_since * self.freshness_decay)
        touched_after = self._touched_after(candles, idx, price, is_high)
        freshness = _clamp(age_freshness * (0.25 if touched_after else 1.0))
        distance = abs(price - current_price) / typical_range
        touches = int(((candles["low"] <= price) & (candles["high"] >= price)).sum())
        engineered = _clamp((touches - 1) * 0.2)
        importance = _clamp(0.45 * freshness + 0.35 * (1.0 / (1.0 + distance)) + 0.20 * engineered)
        sweep_prob = _clamp(0.8 / (1.0 + distance * 0.8) + 0.2 * freshness)
        delivery_prob = _clamp((distance / 4.0) * 0.65 + importance * 0.35)
        if distance < 1.0 and freshness > 0.2:
            cls = LiquidityClass.CONSUMABLE
        elif distance < 3.0 or engineered > 0.3:
            cls = LiquidityClass.TRANSFER
        else:
            cls = LiquidityClass.DELIVERY
        return LiquidityLevel(
            price=price, type="high" if is_high else "low", source="swing", freshness=freshness,
            importance_score=importance, sweep_probability=sweep_prob, delivery_probability=delivery_prob,
            liquidity_class=cls, side=LiquiditySide.BUY_SIDE if is_high else LiquiditySide.SELL_SIDE,
            engineered_likelihood=engineered,
        )

    def _touched_after(self, candles: pd.DataFrame, idx: int, price: float, is_high: bool) -> bool:
        after = candles.iloc[idx + 1:]
        if after.empty:
            return False
        return bool((after["high"] >= price).any() if is_high else (after["low"] <= price).any())

    def _typical_range(self, candles: pd.DataFrame) -> float:
        return float(((candles["high"] - candles["low"]).abs()).median(skipna=True) or 0.0)

    def _detect_engineered_zones(self, levels: List[LiquidityLevel], typical_range: float, current_price: float) -> List[float]:
        if not levels:
            return []
        threshold = max(typical_range * 0.5, current_price * 0.0005)
        prices = sorted(float(l.price) for l in levels)
        clusters: List[List[float]] = [[prices[0]]]
        for p in prices[1:]:
            if abs(p - clusters[-1][-1]) <= threshold:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        return [float(np.mean(c)) for c in clusters if len(c) >= 2]
