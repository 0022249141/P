"""In-memory audit and lineage system. Persistence can be added later."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
import json
class AuditEngine:
    def __init__(self): self.log=[]
    def _preview(self,obj):
        try: text=json.dumps(obj,default=str,ensure_ascii=False)
        except Exception: text=str(obj)
        return text[:1000]
    def record(self, step:str, inputs:Any, outputs:Any, signal_id:Optional[str]=None, event_id:Optional[str]=None, metadata:Optional[dict]=None):
        entry={"timestamp":datetime.utcnow().isoformat(),"step":step,"signal_id":signal_id,"event_id":event_id,"inputs_preview":self._preview(inputs),"outputs_preview":self._preview(outputs),"metadata":metadata or {}}
        self.log.append(entry); return entry
    def trace_signal(self, signal_id:str)->list: return [e for e in self.log if e.get("signal_id")==signal_id]
    def clear(self): self.log.clear()
    def export_jsonl(self,path:str):
        with open(path,"w",encoding="utf-8") as f:
            for e in self.log: f.write(json.dumps(e,ensure_ascii=False,default=str)+"\n")
