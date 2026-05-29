"""Pub/sub event bus with sync/async callback support."""
from __future__ import annotations
import inspect, logging
from collections import defaultdict
from typing import Callable, Dict, List
from core.schemas import SystemEvent
logger=logging.getLogger(__name__)
def _event_key(event_type): return getattr(event_type,"value",event_type)
class EventBus:
    def __init__(self): self._subscribers:Dict[str,List[Callable]]=defaultdict(list)
    def subscribe(self,event_type,callback:Callable):
        key=str(_event_key(event_type))
        if callback not in self._subscribers[key]: self._subscribers[key].append(callback)
    async def publish_async(self,event:SystemEvent):
        for cb in list(self._subscribers.get(event.event_type.value,[]))+list(self._subscribers.get("*",[])):
            try:
                result=cb(event)
                if inspect.isawaitable(result): await result
            except Exception: logger.exception("Event callback failed for %s", event.event_type.value)
    def publish(self,event:SystemEvent):
        for cb in list(self._subscribers.get(event.event_type.value,[]))+list(self._subscribers.get("*",[])):
            try:
                result=cb(event)
                if inspect.isawaitable(result): return result
            except Exception: logger.exception("Event callback failed for %s", event.event_type.value)
    def unsubscribe(self,event_type,callback:Callable)->bool:
        key=str(_event_key(event_type)); before=len(self._subscribers.get(key,[])); self._subscribers[key]=[c for c in self._subscribers.get(key,[]) if c!=callback]; return len(self._subscribers[key])<before
    def subscriber_count(self,event_type=None)->int:
        if event_type is None: return sum(len(v) for v in self._subscribers.values())
        return len(self._subscribers.get(str(_event_key(event_type)),[]))
