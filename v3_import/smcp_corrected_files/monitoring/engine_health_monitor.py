"""Monitors engine execution and detects failures/stale engines."""
from __future__ import annotations
from datetime import datetime, timedelta
from core.schemas import EngineHealth
class EngineHealthMonitor:
    def __init__(self): self.health={}
    def report_execution(self, engine_name:str, latency_ms:float, error:str|None=None):
        self.health[engine_name]=EngineHealth(engine_name=engine_name,status="failed" if error else "healthy",last_execution=datetime.utcnow(),latency_ms=max(0.0,float(latency_ms or 0)),error_message=error)
        return self.health[engine_name]
    def mark_stale(self, engine_name:str, reason:str|None=None):
        h=self.health.get(engine_name,EngineHealth(engine_name=engine_name,status="stale")); h.status="stale"; h.error_message=reason; self.health[engine_name]=h; return h
    def check_stale(self,max_age_seconds:float):
        now=datetime.utcnow()
        for k,h in list(self.health.items()):
            if h.last_execution and now-h.last_execution>timedelta(seconds=max_age_seconds): self.mark_stale(k,"stale by age")
        return self.check_all()
    def get_health(self, engine_name:str): return self.health.get(engine_name)
    def check_all(self)->list: return list(self.health.values())
    def clear(self): self.health.clear()
