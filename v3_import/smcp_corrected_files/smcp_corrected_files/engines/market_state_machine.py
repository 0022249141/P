"""
engines/market_state_machine.py
Probabilistic institutional market state machine.
"""

from __future__ import annotations

from typing import Dict, Optional
import numpy as np
import pandas as pd
from core.schemas import LiquidityMap, MarketState


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


class MarketStateMachine:
    TRANSITION_WEIGHTS: Dict[MarketState, Dict[MarketState, float]] = {
        MarketState.ACCUMULATION: {MarketState.ACCUMULATION: 0.4, MarketState.MANIPULATION: 0.2, MarketState.EXPANSION: 0.15, MarketState.TRANSFER_BOX: 0.1, MarketState.INVENTORY_LOADING: 0.1, MarketState.REVERSION: 0.05},
        MarketState.DISTRIBUTION: {MarketState.DISTRIBUTION: 0.4, MarketState.MANIPULATION: 0.2, MarketState.EXPANSION: 0.1, MarketState.TRANSFER_BOX: 0.1, MarketState.INVENTORY_UNLOADING: 0.1, MarketState.REVERSION: 0.1},
        MarketState.MANIPULATION: {MarketState.EXPANSION: 0.35, MarketState.DELIVERY_COMMIT: 0.2, MarketState.TRANSFER_BOX: 0.15, MarketState.REVERSION: 0.2, MarketState.PRE_DELIVERY: 0.1},
        MarketState.EXPANSION: {MarketState.DELIVERY_COMMIT: 0.3, MarketState.REVERSION: 0.25, MarketState.DISTRIBUTION: 0.15, MarketState.ACCUMULATION: 0.15, MarketState.COMPRESSION: 0.15},
        MarketState.DELIVERY_COMMIT: {MarketState.EXPANSION: 0.5, MarketState.REVERSION: 0.3, MarketState.DISTRIBUTION: 0.2},
        MarketState.REVERSION: {MarketState.ACCUMULATION: 0.3, MarketState.DISTRIBUTION: 0.3, MarketState.COMPRESSION: 0.2, MarketState.TRANSFER_BOX: 0.2},
        MarketState.COMPRESSION: {MarketState.EXPANSION: 0.45, MarketState.MANIPULATION: 0.3, MarketState.ACCUMULATION: 0.125, MarketState.DISTRIBUTION: 0.125},
        MarketState.TRANSFER_BOX: {MarketState.EXPANSION: 0.3, MarketState.MANIPULATION: 0.25, MarketState.DELIVERY_COMMIT: 0.15, MarketState.ACCUMULATION: 0.15, MarketState.DISTRIBUTION: 0.15},
        MarketState.INVENTORY_LOADING: {MarketState.PRE_DELIVERY: 0.3, MarketState.EXPANSION: 0.25, MarketState.ACCUMULATION: 0.25, MarketState.MANIPULATION: 0.2},
        MarketState.INVENTORY_UNLOADING: {MarketState.PRE_DELIVERY: 0.3, MarketState.EXPANSION: 0.25, MarketState.DISTRIBUTION: 0.25, MarketState.MANIPULATION: 0.2},
        MarketState.PRE_DELIVERY: {MarketState.DELIVERY_COMMIT: 0.45, MarketState.MANIPULATION: 0.2, MarketState.EXPANSION: 0.2, MarketState.REVERSION: 0.15},
        MarketState.REPRICING: {MarketState.TRANSFER_BOX: 0.3, MarketState.ACCUMULATION: 0.25, MarketState.DISTRIBUTION: 0.25, MarketState.EXPANSION: 0.2},
    }

    def __init__(self) -> None:
        self.current_state = MarketState.ACCUMULATION
        self.last_volatility = 0.0
        self.last_range_ratio = 0.0

    def determine_state(self, candles: pd.DataFrame, liquidity: Optional[LiquidityMap] = None) -> MarketState:
        if candles is None or candles.empty:
            return self.current_state
        required = {"open", "high", "low", "close"}
        if not required.issubset(candles.columns):
            return self.current_state
        df = candles.copy()
        for col in required.union({"volume"} & set(df.columns)):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=list(required))
        if len(df) < 5:
            return self.current_state

        window = min(20, len(df))
        recent = df.iloc[-window:]
        prev = df.iloc[:-window]
        high, low, close, open_ = recent["high"], recent["low"], recent["close"], recent["open"]
        rng = (high - low).abs().replace(0, np.nan)
        typical_range = float(rng.median(skipna=True) or 0.0)
        range_pct = ((high - low).abs() / close.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        vol = float(range_pct.std(skipna=True) or 0.0)
        self.last_volatility = vol
        body_ratio = ((close - open_).abs() / rng).replace([np.inf, -np.inf], np.nan).fillna(0)
        self.last_range_ratio = float(body_ratio.mean())

        x = np.arange(len(close), dtype=float)
        slope = float(np.polyfit(x, close.to_numpy(dtype=float), 1)[0]) if len(close) > 1 else 0.0
        normalized_slope = slope / max(abs(float(close.mean())), 1e-9)
        volume_confirmed = False
        if "volume" in recent.columns:
            vol_series = pd.to_numeric(recent["volume"], errors="coerce").fillna(0)
            volume_confirmed = bool(vol_series.std() > 0 and vol_series.iloc[-1] > vol_series.mean())

        manipulation = self._is_manipulation(recent, prev, typical_range)
        if manipulation:
            return MarketState.MANIPULATION
        if self._in_transfer_box(float(close.iloc[-1]), liquidity, typical_range):
            return MarketState.TRANSFER_BOX
        avg_range_pct = float(range_pct.mean(skipna=True) or 0.0)
        if avg_range_pct < 0.003 and self.last_range_ratio < 0.45:
            return MarketState.COMPRESSION
        if avg_range_pct > 0.012 or vol > 0.006:
            return MarketState.EXPANSION
        if abs(normalized_slope) > 0.001 and avg_range_pct > 0.004 and (volume_confirmed or self.last_range_ratio > 0.55):
            return MarketState.DELIVERY_COMMIT
        if self.current_state == MarketState.EXPANSION and abs(normalized_slope) < 0.0004 and self.last_range_ratio < 0.35:
            return MarketState.REVERSION
        if normalized_slope > 0 and self.last_range_ratio < 0.55:
            return MarketState.ACCUMULATION
        if normalized_slope < 0 and self.last_range_ratio < 0.55:
            return MarketState.DISTRIBUTION
        return self.current_state

    def step(self, candles: pd.DataFrame, liquidity: Optional[LiquidityMap] = None) -> MarketState:
        state = self.determine_state(candles, liquidity)
        self.update_state(state)
        return state

    def transition_probabilities(self) -> Dict[MarketState, float]:
        weights = self.TRANSITION_WEIGHTS.get(self.current_state, {self.current_state: 1.0})
        total = sum(max(0.0, float(w)) for w in weights.values())
        return {state: (max(0.0, float(w)) / total if total else 0.0) for state, w in weights.items()} or {self.current_state: 1.0}

    def update_state(self, new_state: MarketState) -> None:
        self.current_state = new_state

    def _is_manipulation(self, recent: pd.DataFrame, prev: pd.DataFrame, typical_range: float) -> bool:
        if len(recent) < 2 or len(prev) < 3:
            return False
        prev_high, prev_low = float(prev["high"].max()), float(prev["low"].min())
        last = recent.iloc[-1]
        break_buffer = max(typical_range * 0.15, abs(float(last["close"])) * 0.0005)
        return bool((last["high"] > prev_high + break_buffer and last["close"] < prev_high) or (last["low"] < prev_low - break_buffer and last["close"] > prev_low))

    def _in_transfer_box(self, current_price: float, liquidity: Optional[LiquidityMap], typical_range: float) -> bool:
        if not liquidity:
            return False
        upper_candidates = [l.price for l in liquidity.buy_side_levels if l.price > current_price]
        lower_candidates = [l.price for l in liquidity.sell_side_levels if l.price < current_price]
        if not upper_candidates or not lower_candidates:
            return False
        upper, lower = min(upper_candidates), max(lower_candidates)
        width = upper - lower
        if width <= 0:
            return False
        position = (current_price - lower) / width
        return bool(0.2 <= position <= 0.8 and width <= max(typical_range * 12, current_price * 0.03))
