"""Institutional signal candidate engine. Produces analytical candidates, not execution advice."""
from __future__ import annotations
import uuid
from typing import Optional
import pandas as pd
from core.schemas import Bias, DeliveryState, ExecutionTiming, InstitutionalSignal, LiquidityMap, Market, MarketDeliveryState, ProbabilitySnapshot, RegimeSnapshot, RegimeType, RiskGrade, SignalDirection

def _v(x): return getattr(x,"value",x)
def _clamp(x): return max(0.0,min(1.0,float(x)))

class InstitutionalSignalEngine:
    def evaluate(self, inventory, delivery:MarketDeliveryState, probability:ProbabilitySnapshot, regime:RegimeSnapshot, liquidity_map:Optional[LiquidityMap]=None, market:Market=Market.ABSHODEH, current_price:Optional[float]=None, candles:Optional[pd.DataFrame]=None)->InstitutionalSignal:
        if current_price is None and candles is not None and len(candles) and "close" in candles.columns: current_price=float(candles.close.iloc[-1])
        if current_price is None: current_price=0.0
        direction=self._direction(inventory,delivery,probability,regime)
        timing=self._timing(direction,delivery,probability)
        liq_target, del_target = self._targets(direction, liquidity_map, current_price)
        invalidation=self._invalidation(direction, liquidity_map, current_price)
        signal_prob=_clamp(0.35*probability.commitment_probability+0.35*probability.delivery_probability+0.20*probability.continuation_probability+0.10*probability.confidence_score-0.25*probability.manipulation_probability)
        risk=self._risk_grade(probability,regime,delivery,direction)
        return InstitutionalSignal(id=str(uuid.uuid4())[:8], timestamp=inventory.timestamp, market=market, direction=direction, entry_price=max(0.0,float(current_price)), invalidation_price=max(0.0,float(invalidation)), liquidity_target=liq_target, delivery_target=del_target, probability=signal_prob, confidence=probability.confidence_score, regime=regime.regime, dealer_narrative=f"Inferred dealer-like intent: {_v(inventory.dealer_intent)}", inventory_state=inventory.inventory_state, session_context="tehran", risk_grade=risk, execution_timing=timing, expected_sequence=self._sequence(timing))
    def _direction(self,inv,dely,prob,regime):
        if _v(dely.delivery_state)==DeliveryState.FALSE_COMMITMENT.value or prob.confidence_score<0.35 or prob.manipulation_probability>0.65: return SignalDirection.NEUTRAL
        b=_v(inv.inventory_bias)
        if b==Bias.BULLISH.value and prob.commitment_probability>0.45: return SignalDirection.LONG
        if b==Bias.BEARISH.value and prob.commitment_probability>0.45: return SignalDirection.SHORT
        return SignalDirection.NEUTRAL
    def _targets(self,direction,liq,price):
        if not liq or direction==SignalDirection.NEUTRAL: return None,None
        if direction==SignalDirection.LONG:
            ups=[l.price for l in liq.buy_side_levels if l.price>price]
            return liq.nearest_consumable_buy, (max(ups) if ups else liq.nearest_consumable_buy)
        downs=[l.price for l in liq.sell_side_levels if l.price<price]
        return liq.nearest_consumable_sell, (min(downs) if downs else liq.nearest_consumable_sell)
    def _invalidation(self,direction,liq,price):
        if not liq or direction==SignalDirection.NEUTRAL: return price
        if direction==SignalDirection.LONG: return liq.nearest_consumable_sell or price
        return liq.nearest_consumable_buy or price
    def _risk_grade(self,prob,regime,dely,direction):
        if direction==SignalDirection.NEUTRAL: return RiskGrade.HIGH
        if _v(dely.delivery_state)==DeliveryState.FALSE_COMMITMENT.value or prob.manipulation_probability>0.6: return RiskGrade.EXTREME
        if prob.confidence_score<0.5 or _v(regime.regime) in {"manipulation","high_vol"}: return RiskGrade.HIGH
        if prob.confidence_score<0.7: return RiskGrade.MEDIUM
        return RiskGrade.LOW
    def _timing(self,direction,dely,prob):
        if direction==SignalDirection.NEUTRAL: return ExecutionTiming.NO_TRADE
        if dely.displacement_confirmed and prob.confidence_score>0.65: return ExecutionTiming.IMMEDIATE
        return ExecutionTiming.WAIT_FOR_CONFIRMATION
    def _sequence(self,timing): return ["no_trade"] if timing==ExecutionTiming.NO_TRADE else ["internal_harvest","confirmation","delivery_commit","target_reached"]
