"""
engines/probability_engine.py
Deterministic heuristic probability-like scoring; not statistically calibrated unless validated externally.
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
from core.schemas import CommitmentState, DealerInventoryState, DeliveryState, LiquidityMap, Market, MarketDeliveryState, MarketState, ProbabilitySnapshot, TimeFrame


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _v(x):
    return getattr(x, "value", x)


class ProbabilityEngine:
    def __init__(self, weights: Optional[dict] = None):
        self.weights = self._normalize_weights(weights or {"inventory": 0.3, "delivery": 0.3, "liquidity": 0.2, "market_state": 0.2})

    def evaluate(self, inventory: DealerInventoryState, delivery: MarketDeliveryState, liquidity_map: Optional[LiquidityMap] = None, current_state: MarketState = MarketState.ACCUMULATION, market: Market = Market.ABSHODEH, timeframe: TimeFrame = TimeFrame.H1, candles: Optional[pd.DataFrame] = None) -> ProbabilitySnapshot:
        p_delivery = self._delivery_prob(inventory, delivery, current_state, liquidity_map)
        p_sweep = self._sweep_prob(inventory, delivery, liquidity_map, current_state)
        p_commit = self._commitment_prob(inventory, delivery, current_state)
        p_manip = self._manipulation_prob(inventory, delivery, current_state, liquidity_map)
        p_cont = _clamp(0.55 * delivery.continuation_probability + 0.30 * p_commit + 0.15 * p_delivery - 0.25 * p_manip)
        p_rev = self._reversal_prob(delivery, current_state, p_cont, p_manip)
        confidence = self._confidence_score(inventory, delivery, current_state, p_delivery, p_cont, p_rev, p_commit, p_manip)
        uncertainty = _clamp(1.0 - confidence + self._conflict_penalty(delivery, current_state, p_cont, p_rev))
        expected_path = self._expected_path(p_delivery, p_cont, p_rev, p_manip, uncertainty)
        return ProbabilitySnapshot(timestamp=inventory.timestamp, market=market, delivery_probability=p_delivery, sweep_probability=p_sweep, continuation_probability=p_cont, reversal_probability=p_rev, manipulation_probability=p_manip, commitment_probability=p_commit, confidence_score=confidence, uncertainty_score=uncertainty, expected_path=expected_path)

    def _normalize_weights(self, weights: dict) -> dict:
        total = sum(max(0.0, float(v)) for v in weights.values()) or 1.0
        return {k: max(0.0, float(v)) / total for k, v in weights.items()}

    def _delivery_prob(self, inv, delv, state, liq) -> float:
        base = 0.35
        ds = _v(delv.delivery_state)
        if ds in {DeliveryState.DELIVERY_COMMIT.value, DeliveryState.EXPANSION.value}: base += 0.28
        if ds == DeliveryState.RECLAIM.value: base += 0.15
        if ds == DeliveryState.FALSE_COMMITMENT.value: base -= 0.28
        if _v(inv.commitment_state) == CommitmentState.COMMITTED.value: base += 0.22
        if state == MarketState.DELIVERY_COMMIT: base += 0.15
        if delv.external_target_identified: base += 0.10
        return _clamp(base)

    def _sweep_prob(self, inv, delv, liq, state) -> float:
        base = 0.25 + (0.35 if delv.internal_liquidity_swept else 0) + (0.15 if state in {MarketState.MANIPULATION, MarketState.PRE_DELIVERY} else 0)
        if liq and (liq.nearest_consumable_buy is not None or liq.nearest_consumable_sell is not None): base += 0.12
        return _clamp(base)

    def _manipulation_prob(self, inv, delv, state, liq) -> float:
        base = 0.10
        if delv.inducement_detected: base += 0.32
        if state == MarketState.MANIPULATION or inv.inventory_state == MarketState.MANIPULATION: base += 0.30
        if _v(delv.delivery_state) == DeliveryState.FALSE_COMMITMENT.value: base += 0.35
        if delv.internal_liquidity_swept and not delv.displacement_confirmed: base += 0.12
        return _clamp(base)

    def _commitment_prob(self, inv, delv, state) -> float:
        base = 0.20
        if _v(inv.commitment_state) == CommitmentState.COMMITTED.value: base += 0.45
        if state == MarketState.DELIVERY_COMMIT: base += 0.20
        if delv.displacement_confirmed: base += 0.18
        if delv.reclaim_triggered: base += 0.08
        if _v(delv.delivery_state) == DeliveryState.FALSE_COMMITMENT.value: base -= 0.35
        return _clamp(base)

    def _reversal_prob(self, delv, state, p_cont, p_manip) -> float:
        base = 0.25 + 0.35 * (1 - p_cont) + 0.20 * p_manip
        if _v(delv.delivery_state) in {DeliveryState.REVERSION.value, DeliveryState.FALSE_COMMITMENT.value}: base += 0.20
        if state == MarketState.REVERSION: base += 0.15
        return _clamp(base)

    def _confidence_score(self, inv, delv, state, p_del, p_cont, p_rev, p_com, p_manip) -> float:
        agreements = 0; total = 0
        if state == MarketState.DELIVERY_COMMIT: total += 1; agreements += int(p_com > 0.55 and p_del > 0.55)
        if delv.displacement_confirmed: total += 1; agreements += int(p_cont > 0.45)
        if _v(delv.delivery_state) == DeliveryState.FALSE_COMMITMENT.value: total += 1; agreements += int(p_manip > 0.45 or p_rev > 0.45)
        if _v(inv.commitment_state) == CommitmentState.COMMITTED.value: total += 1; agreements += int(p_com > 0.55)
        agreement_score = agreements / total if total else 0.5
        decisiveness = float(np.mean([abs(p_del - 0.5), abs(p_cont - 0.5), abs(p_rev - 0.5), abs(p_com - 0.5)])) * 2
        return _clamp(0.6 * agreement_score + 0.4 * decisiveness)

    def _conflict_penalty(self, delv, state, p_cont, p_rev) -> float:
        penalty = 0.0
        if p_cont > 0.55 and p_rev > 0.55: penalty += 0.25
        if state == MarketState.COMPRESSION and _v(delv.delivery_state) == DeliveryState.DELIVERY_COMMIT.value: penalty += 0.15
        return penalty

    def _expected_path(self, p_del, p_cont, p_rev, p_manip, uncertainty) -> str:
        if uncertainty > 0.70: return "unresolved"
        scores = {"delivery": p_del, "continuation": p_cont, "reversal": p_rev, "manipulation": p_manip}
        return max(scores, key=scores.get)
