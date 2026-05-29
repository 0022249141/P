"""In-memory journal for signal evolution and narrative progression."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4
class InstitutionalJournalEngine:
    def __init__(self): self.entries=[]
    def log(self,timestamp,signal_id:str,narrative:str,state:Any,event_type:str="narrative_updated",metadata:Optional[dict]=None)->dict:
        entry={"entry_id":uuid4().hex,"timestamp":timestamp or datetime.utcnow(),"signal_id":signal_id,"narrative":narrative,"state":state,"event_type":event_type,"metadata":metadata or {}}
        self.entries.append(entry); return entry
    def get_history(self,signal_id:str)->list: return [e for e in self.entries if e["signal_id"]==signal_id]
    def latest(self,signal_id:str):
        h=self.get_history(signal_id); return h[-1] if h else None
    def all_entries(self)->list: return list(self.entries)
    def clear(self): self.entries.clear()
InstitutionalJournal=InstitutionalJournalEngine
