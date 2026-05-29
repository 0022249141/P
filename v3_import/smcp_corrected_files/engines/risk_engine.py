"""Risk Engine — execution risk, liquidity fragility, adverse-move probability."""
from __future__ import annotations
from typing import Optional
from core.schemas import DeliveryState, LiquidityMap, RiskGrade

def _v(x): return getattr(x,"value",x)
def _clamp(x): return max(0.0,min(1.0,float(x)))
class RiskEngine:
    def evaluate(self, inventory, delivery, probability, regime, liquidity_map: Optional[LiquidityMap]=None) -> dict:
        frag=self._fragility(liquidity_map)
        adverse=_clamp(0.30*probability.reversal_probability+0.25*probability.manipulation_probability+0.25*(1-probability.confidence_score)+0.20*frag)
        if _v(delivery.delivery_state)==DeliveryState.FALSE_COMMITMENT.value: adverse=_clamp(adverse+0.30)
        if _v(regime.regime) in {"manipulation","high_vol"}: adverse=_clamp(adverse+0.15)
        grade=RiskGrade.EXTREME if adverse>=0.75 else RiskGrade.HIGH if adverse>=0.55 else RiskGrade.MEDIUM if adverse>=0.35 else RiskGrade.LOW
        return {"risk_grade":grade,"execution_safety":_clamp(1-adverse),"adverse_move_probability":adverse,"liquidity_fragility_score":frag,"risk_notes":self._notes(grade, delivery, probability, frag)}
    def _fragility(self, liq):
        if not liq: return 0.5
        near=sum(x is not None for x in [liq.nearest_consumable_buy, liq.nearest_consumable_sell])
        density=min(1.0,(len(liq.buy_side_levels)+len(liq.sell_side_levels))/20)
        return _clamp(0.35*near+0.45*density+0.20*(1 if liq.engineered_liquidity_zones else 0))
    def _notes(self,grade,d,p,frag): return [f"risk_grade={_v(grade)}",f"delivery_state={_v(d.delivery_state)}",f"confidence={p.confidence_score:.2f}",f"fragility={frag:.2f}"]
