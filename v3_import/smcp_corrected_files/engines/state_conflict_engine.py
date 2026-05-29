"""Resolves conflicting outputs between inventory and delivery engines."""
from __future__ import annotations
from core.schemas import DeliveryState, MarketState

def _v(x): return getattr(x,"value",x)
class StateConflictEngine:
    def resolve(self, inventory, delivery) -> dict:
        inv=inventory.inventory_state; ds=_v(delivery.delivery_state)
        conflict=False; ctype="none"; reason="Inventory context remains primary."
        resolved=inv; priority="inventory"
        if ds==DeliveryState.FALSE_COMMITMENT.value:
            resolved=MarketState.MANIPULATION; conflict=inv!=resolved; ctype="false_commitment"; reason="False commitment overrides broader inventory state."; priority="delivery"
        elif ds==DeliveryState.DELIVERY_COMMIT.value:
            resolved=MarketState.DELIVERY_COMMIT; conflict=inv!=resolved; ctype="delivery_commit"; reason="Confirmed delivery state has precedence."; priority="delivery"
        elif ds==DeliveryState.EXPANSION.value and inv in {MarketState.ACCUMULATION,MarketState.DISTRIBUTION}:
            resolved=MarketState.EXPANSION; conflict=True; ctype="expansion_vs_inventory"; reason="Expansion is preserved but not upgraded to delivery commitment without confirmation."; priority="balanced"
        return {"resolved_state":resolved,"conflict":conflict,"conflict_type":ctype,"resolution_reason":reason,"source_priority":priority}
