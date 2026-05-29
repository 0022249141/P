"""Scenario Engine — multi-path forecasting and invalidation trees."""
from __future__ import annotations
from core.schemas import MarketState

def _v(x): return getattr(x,"value",x)
def _clamp(x): return max(0.0,min(1.0,float(x)))
class ScenarioEngine:
    def build_scenarios(self, probability, current_state: MarketState) -> dict:
        scenarios=[
            {"name":"Delivery","probability":_clamp(probability.delivery_probability),"path":["internal_sweep","displacement","delivery_commit","external_target"],"collapse_condition":"Displacement or reclaim fails."},
            {"name":"Continuation","probability":_clamp(probability.continuation_probability),"path":["confirmation","continuation","target_reached"],"collapse_condition":"Protected structure fails."},
            {"name":"Reversal","probability":_clamp(probability.reversal_probability),"path":["failed_displacement","reclaim_failure","range_return"],"collapse_condition":"Price reclaims broken structure."},
            {"name":"Manipulation Trap","probability":_clamp(probability.manipulation_probability),"path":["inducement","liquidity_sweep","sharp_rejection","wait_for_confirmation"],"collapse_condition":"Sweep converts into confirmed displacement."},
        ]
        if probability.uncertainty_score>0.55 or current_state in {MarketState.COMPRESSION,MarketState.TRANSFER_BOX}:
            scenarios.append({"name":"Unresolved Transfer","probability":_clamp(max(probability.uncertainty_score,0.35)),"path":["compression","internal_rotation","wait_for_break"],"collapse_condition":"Clear delivery or reversal confirmation appears."})
        scenarios=sorted(scenarios,key=lambda x:x["probability"],reverse=True)
        return {"primary_scenario":scenarios[0],"alternative_scenarios":scenarios[1:],"collapse_conditions":[s["collapse_condition"] for s in scenarios],"expected_liquidity_path":scenarios[0]["path"]}
