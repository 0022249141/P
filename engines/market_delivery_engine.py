"""
engines/market_delivery_engine.py
Sequences the inferred institutional delivery process from price/liquidity evidence.
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
from core.schemas import CommitmentState, DealerInventoryState, DeliveryState, LiquidityMap, Market, MarketDeliveryState, MarketState, TimeFrame


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _value(x):
    return getattr(x, "value", x)


class MarketDeliveryEngine:
    def __init__(self, lookback_candles: int = 50, minimum_required: int = 20):
        self.lookback = max(30, int(lookback_candles))
        self.minimum_required = max(10, int(minimum_required))

    def evaluate(self, candles: pd.DataFrame, inventory_state: DealerInventoryState, liquidity_map: Optional[LiquidityMap] = None, market: Market = Market.ABSHODEH, timeframe: TimeFrame = TimeFrame.H1) -> MarketDeliveryState:
        if candles is None or candles.empty or not {"open", "high", "low", "close"}.issubset(candles.columns):
            return self._state(market, DeliveryState.PRE_DELIVERY)
        df = candles.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
        if len(df) < self.minimum_required:
            return self._state(market, DeliveryState.PRE_DELIVERY)
        recent = df.iloc[-min(self.lookback, len(df)):]
        internal = self._detect_internal_sweep(recent, liquidity_map)
        induce = self._detect_inducement(recent)
        displace = self._detect_displacement(recent)
        reclaim = self._detect_reclaim(recent, displace)
        false_commit = self._detect_false_commitment(recent)
        delivery_state = self._sequence_state(internal, induce, displace, reclaim, false_commit, inventory_state)
        continuation_prob = self._continuation_probability(delivery_state, recent)
        external_target = self._has_external_target(float(recent["close"].iloc[-1]), liquidity_map, delivery_state)
        return MarketDeliveryState(
            timestamp=self._timestamp(recent), market=market, delivery_state=delivery_state,
            internal_liquidity_swept=internal, external_target_identified=external_target,
            inducement_detected=induce, continuation_probability=continuation_prob,
            displacement_confirmed=displace, reclaim_triggered=reclaim,
        )

    def _state(self, market: Market, state: DeliveryState) -> MarketDeliveryState:
        return MarketDeliveryState(timestamp=pd.Timestamp.utcnow().to_pydatetime(), market=market, delivery_state=state)

    def _timestamp(self, df: pd.DataFrame):
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"].iloc[-1], errors="coerce")
            if pd.notna(ts): return ts.to_pydatetime()
        return pd.Timestamp.utcnow().to_pydatetime()

    def _typical_range(self, candles: pd.DataFrame) -> float:
        return float(((candles["high"] - candles["low"]).abs()).median(skipna=True) or 0.0)

    def _detect_internal_sweep(self, candles: pd.DataFrame, liquidity: Optional[LiquidityMap]) -> bool:
        if not liquidity or len(candles) < 3:
            return False
        last = candles.iloc[-1]
        typical = max(self._typical_range(candles), abs(float(last["close"])) * 0.0005, 1e-9)
        for level in liquidity.buy_side_levels + liquidity.sell_side_levels:
            price = float(level.price)
            buffer = typical * 0.10
            if price > candles["close"].iloc[-2] and last["high"] >= price + buffer and last["close"] < price:
                return True
            if price < candles["close"].iloc[-2] and last["low"] <= price - buffer and last["close"] > price:
                return True
        return False

    def _detect_inducement(self, candles: pd.DataFrame) -> bool:
        if len(candles) < 10:
            return False
        prev = candles.iloc[-10:-3]
        last3 = candles.iloc[-3:]
        typical = max(self._typical_range(candles), 1e-9)
        prev_high, prev_low = prev["high"].max(), prev["low"].min()
        return bool((last3["high"].max() > prev_high + 0.15 * typical and last3["close"].iloc[-1] < prev_high) or (last3["low"].min() < prev_low - 0.15 * typical and last3["close"].iloc[-1] > prev_low))

    def _detect_displacement(self, candles: pd.DataFrame) -> bool:
        if len(candles) < 5:
            return False
        window = min(20, len(candles))
        recent = candles.iloc[-window:]
        avg_range = float(((recent["high"] - recent["low"]).abs()).mean() or 0)
        last_range = float(abs(candles["high"].iloc[-1] - candles["low"].iloc[-1]))
        body = float(abs(candles["close"].iloc[-1] - candles["open"].iloc[-1]))
        body_eff = body / max(last_range, 1e-9)
        volume_ok = True
        if "volume" in candles.columns:
            vol = pd.to_numeric(candles["volume"].iloc[-window:], errors="coerce").fillna(0)
            volume_ok = not (vol.std() > 0 and vol.iloc[-1] < vol.mean() * 0.8)
        return bool(last_range > 1.5 * max(avg_range, 1e-9) and body_eff > 0.55 and volume_ok)

    def _detect_reclaim(self, candles: pd.DataFrame, displacement: bool) -> bool:
        if not displacement or len(candles) < 8:
            return False
        prev = candles.iloc[-8:-3]
        last3 = candles.iloc[-3:]
        direction_up = candles["close"].iloc[-1] >= candles["open"].iloc[-1]
        level = float(prev["high"].max() if direction_up else prev["low"].min())
        return bool(last3["low"].min() <= level <= last3["high"].max())

    def _detect_false_commitment(self, candles: pd.DataFrame) -> bool:
        if len(candles) < 8:
            return False
        r = candles.iloc[-8:]
        base = max(abs(float(r["open"].iloc[0])), 1e-9)
        early = float(r["close"].iloc[2] - r["open"].iloc[0]) / base
        late = float(r["close"].iloc[-1] - r["close"].iloc[2]) / max(abs(float(r["close"].iloc[2])), 1e-9)
        threshold = max(float(((r["high"] - r["low"]).abs() / r["close"].replace(0, np.nan)).median() or 0.004), 0.004)
        return bool((early > 1.8 * threshold and late < -1.4 * threshold) or (early < -1.8 * threshold and late > 1.4 * threshold))

    def _sequence_state(self, internal: bool, induce: bool, displace: bool, reclaim: bool, false_commit: bool, inventory_state: DealerInventoryState) -> DeliveryState:
        commitment = _value(inventory_state.commitment_state)
        inv_state = inventory_state.inventory_state
        if false_commit:
            return DeliveryState.FALSE_COMMITMENT
        if commitment == CommitmentState.COMMITTED.value and displace:
            return DeliveryState.DELIVERY_COMMIT
        if reclaim:
            return DeliveryState.RECLAIM
        if internal and induce:
            return DeliveryState.INTERNAL_HARVEST
        if displace:
            return DeliveryState.EXPANSION
        if inv_state in {MarketState.REVERSION, MarketState.COMPRESSION}:
            return DeliveryState.REVERSION
        return DeliveryState.PRE_DELIVERY

    def _continuation_probability(self, state: DeliveryState, candles: pd.DataFrame) -> float:
        base = {DeliveryState.DELIVERY_COMMIT: 0.82, DeliveryState.EXPANSION: 0.68, DeliveryState.RECLAIM: 0.58, DeliveryState.INTERNAL_HARVEST: 0.52, DeliveryState.PRE_DELIVERY: 0.38, DeliveryState.FALSE_COMMITMENT: 0.16, DeliveryState.REVERSION: 0.20}.get(state, 0.4)
        if len(candles) >= 5:
            efficiency = abs(candles["close"].iloc[-1] - candles["close"].iloc[-5]) / max(((candles["high"] - candles["low"]).abs().iloc[-5:].sum()), 1e-9)
            base += (efficiency - 0.35) * 0.25
        return _clamp(base)

    def _has_external_target(self, current_price: float, liquidity: Optional[LiquidityMap], state: DeliveryState) -> bool:
        if not liquidity or state not in {DeliveryState.DELIVERY_COMMIT, DeliveryState.EXPANSION, DeliveryState.RECLAIM}:
            return False
        return bool(any(l.price > current_price for l in liquidity.buy_side_levels) or any(l.price < current_price for l in liquidity.sell_side_levels))
