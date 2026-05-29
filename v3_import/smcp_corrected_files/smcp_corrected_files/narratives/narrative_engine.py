"""Narrative Engine — bilingual inference-based explanations."""
from __future__ import annotations
from typing import Optional
from core.schemas import DealerInventoryState, DeliveryState, LiquidityMap, Market, MarketDeliveryState, MarketState, Narrative, ProbabilitySnapshot

def _v(x): return getattr(x,"value",x)

class NarrativeEngine:
    def generate_signal_narrative(self, signal_id:str, inventory:DealerInventoryState, delivery:MarketDeliveryState, probability:ProbabilitySnapshot, liquidity_map:Optional[LiquidityMap]=None, market:Market=Market.ABSHODEH)->Narrative:
        consumed=self._consumed(delivery, liquidity_map); remaining=self._remaining(liquidity_map); invalidation=self._invalidation_condition(inventory, delivery)
        return Narrative(id=signal_id, timestamp=inventory.timestamp, market=market, english_text=self._english_narrative(inventory,delivery,probability,liquidity_map), persian_text=self._persian_narrative(inventory,delivery,probability,liquidity_map), consumed_liquidity=consumed, remaining_liquidity=remaining, invalidation_condition=invalidation, commitment_status=str(_v(inventory.commitment_state)) if inventory.commitment_state is not None else None)
    def _english_narrative(self, inv,dely,prob,liq):
        state={MarketState.ACCUMULATION:"Evidence suggests an accumulation-like regime.",MarketState.DISTRIBUTION:"Evidence suggests a distribution-like regime.",MarketState.EXPANSION:"Price is expanding; delivery evidence must be confirmed.",MarketState.MANIPULATION:"A manipulation-like pattern is inferred.",MarketState.DELIVERY_COMMIT:"The market shows inferred delivery commitment.",MarketState.REVERSION:"Reversion evidence is present.",MarketState.COMPRESSION:"Volatility compression suggests expansion risk.",MarketState.TRANSFER_BOX:"Price is rotating inside a transfer box."}.get(inv.inventory_state,"Market state is unresolved.")
        delivery={"pre_delivery":"Delivery preparation remains unconfirmed.","internal_harvest":"Internal liquidity appears to have been harvested.","delivery_commit":"Delivery commitment evidence is active.","expansion":"Expansion is in progress.","false_commitment":"False commitment risk is elevated.","reclaim":"Reclaim behavior is visible.","reversion":"Reversion is active."}.get(_v(dely.delivery_state),"Delivery state is undefined.")
        return " ".join([state, f"Inferred intent: {_v(inv.dealer_intent)}.", delivery, f"Heuristic continuation score is {prob.continuation_probability:.0%} with confidence {prob.confidence_score:.0%}.", f"Invalidation context: {self._invalidation_condition(inv,dely)}"])
    def _persian_narrative(self, inv,dely,prob,liq):
        state={MarketState.ACCUMULATION:"شواهد، رژیم شبیه انباشت را نشان می‌دهد.",MarketState.DISTRIBUTION:"شواهد، رژیم شبیه توزیع را نشان می‌دهد.",MarketState.EXPANSION:"قیمت در فاز انبساط است و نیاز به تأیید تحویل دارد.",MarketState.MANIPULATION:"الگوی شبیه دستکاری استنباط شده است.",MarketState.DELIVERY_COMMIT:"بازار شواهد تعهد تحویلی استنباطی نشان می‌دهد.",MarketState.REVERSION:"شواهد بازگشت در بازار دیده می‌شود.",MarketState.COMPRESSION:"فشردگی نوسان، ریسک انبساط بعدی را بالا می‌برد.",MarketState.TRANSFER_BOX:"قیمت داخل جعبه انتقال در حال گردش است."}.get(inv.inventory_state,"وضعیت بازار هنوز قطعی نیست.")
        delivery={"pre_delivery":"آماده‌سازی تحویل هنوز تأیید نشده است.","internal_harvest":"به نظر می‌رسد بخشی از نقدینگی داخلی مصرف شده است.","delivery_commit":"شواهد تعهد تحویلی فعال است.","expansion":"انبساط در جریان است.","false_commitment":"ریسک تعهد جعلی بالاست.","reclaim":"رفتار بازپس‌گیری سطح دیده می‌شود.","reversion":"بازگشت فعال است."}.get(_v(dely.delivery_state),"وضعیت تحویل تعریف نشده است.")
        return " ".join([state, f"نیت استنباطی: {_v(inv.dealer_intent)}.", delivery, f"امتیاز احتمالی ادامه حرکت {prob.continuation_probability:.0%} با اطمینان {prob.confidence_score:.0%} است.", f"شرط ابطال: {self._invalidation_condition(inv,dely)}"])
    def _consumed(self,dely,liq): return "internal mapped liquidity near recent levels" if liq and dely.internal_liquidity_swept else None
    def _remaining(self,liq):
        if not liq: return None
        parts=[]
        if liq.nearest_consumable_buy is not None: parts.append(f"buy-side at {liq.nearest_consumable_buy}")
        if liq.nearest_consumable_sell is not None: parts.append(f"sell-side at {liq.nearest_consumable_sell}")
        return "; ".join(parts) if parts else None
    def _invalidation_condition(self, inv,dely):
        ds=_v(dely.delivery_state)
        if ds in {DeliveryState.DELIVERY_COMMIT.value,DeliveryState.EXPANSION.value}: return "evaluate against the most recent protected structure level"
        if ds==DeliveryState.INTERNAL_HARVEST.value: return "failure to reclaim the swept internal liquidity zone"
        return "break of the key mapped liquidity or protected structure level"
