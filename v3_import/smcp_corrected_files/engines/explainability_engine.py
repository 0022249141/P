"""Explainability Engine — traceable explanations for analytical outputs."""
from __future__ import annotations
from typing import Any, Dict, Optional
from core.schemas import LiquidityMap, SignalDirection

def _v(x): return getattr(x,"value",x)
class ExplainabilityEngine:
    def explain_signal(self, signal, inventory, delivery, probability, liquidity: Optional[LiquidityMap]=None, risk_context: Optional[dict]=None) -> Dict[str,Any]:
        evidence={"direction":_v(signal.direction),"inventory_bias":_v(inventory.inventory_bias),"dealer_intent":_v(inventory.dealer_intent),"delivery_state":_v(delivery.delivery_state),"commitment_probability":probability.commitment_probability,"confidence":probability.confidence_score,"manipulation_probability":probability.manipulation_probability}
        return {"signal_id":signal.id,"evidence":evidence,"direction_reason":self._direction_reason(signal, inventory, delivery),"entry_reason":"Entry is tied to the supplied current price; no direct order-flow observation is assumed.","invalidation_reason":self._invalidation_reason(signal, liquidity),"liquidity_target_reason":self._target_reason(signal, liquidity),"probability_components":{"delivery_probability":probability.delivery_probability,"sweep_probability":probability.sweep_probability,"continuation_probability":probability.continuation_probability,"reversal_probability":probability.reversal_probability,"manipulation_probability":probability.manipulation_probability,"commitment_probability":probability.commitment_probability,"confidence_score":probability.confidence_score,"uncertainty_score":probability.uncertainty_score},"state_transition_explanation":self._state_transition_explanation(inventory,delivery,probability),"risk_grade_explanation":self._risk(signal,risk_context)}
    def _direction_reason(self, signal, inv, d):
        if _v(signal.direction)==SignalDirection.LONG.value: return f"Long candidate because inferred bias is {_v(inv.inventory_bias)} with delivery state {_v(d.delivery_state)}."
        if _v(signal.direction)==SignalDirection.SHORT.value: return f"Short candidate because inferred bias is {_v(inv.inventory_bias)} with delivery state {_v(d.delivery_state)}."
        return "Neutral/no-trade because evidence is conflicting or confidence is insufficient."
    def _invalidation_reason(self, signal, liq):
        if not liq: return "Invalidation is based on protected structure because no liquidity map was supplied."
        if _v(signal.direction)==SignalDirection.LONG.value: return f"Long invalidation uses sell-side/protected-low context: {liq.nearest_consumable_sell}."
        if _v(signal.direction)==SignalDirection.SHORT.value: return f"Short invalidation uses buy-side/protected-high context: {liq.nearest_consumable_buy}."
        return "No active directional invalidation for neutral signal."
    def _target_reason(self,signal,liq): return "Target liquidity not identified." if not liq or signal.liquidity_target is None else f"Mapped liquidity objective selected at {signal.liquidity_target}."
    def _state_transition_explanation(self,inv,d,p): return f"State={_v(inv.inventory_state)}, delivery={_v(d.delivery_state)}, accumulation={inv.accumulation_score:.2f}, distribution={inv.distribution_score:.2f}, confidence={p.confidence_score:.2f}."
    def _risk(self,signal,risk): return f"Risk grade {_v(signal.risk_grade)}" + (f" with context {risk}" if risk else " based on probability/regime inputs.")
