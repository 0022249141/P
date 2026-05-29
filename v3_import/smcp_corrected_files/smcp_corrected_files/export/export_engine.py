"""Exports signals and narratives to Excel, CSV, and JSON. PDF is intentionally left for a dedicated RTL/Persian reporting layer."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, List
import pandas as pd
from core.schemas import InstitutionalSignal, Narrative
class ExportEngine:
    @staticmethod
    def _dump(obj:Any):
        if hasattr(obj,"model_dump"): data=obj.model_dump(mode="json")
        elif hasattr(obj,"dict"): data=obj.dict()
        else: data=dict(obj)
        return {k:(json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(list,dict)) else getattr(v,"value",v)) for k,v in data.items()}
    @staticmethod
    def _ensure(path): Path(path).parent.mkdir(parents=True,exist_ok=True)
    @staticmethod
    def to_excel(signals:List[InstitutionalSignal], narratives:List[Narrative], path:str):
        ExportEngine._ensure(path)
        with pd.ExcelWriter(path,engine="openpyxl") as writer:
            pd.DataFrame([ExportEngine._dump(s) for s in signals]).to_excel(writer,sheet_name="Signals",index=False)
            pd.DataFrame([ExportEngine._dump(n) for n in narratives]).to_excel(writer,sheet_name="Narratives",index=False)
    @staticmethod
    def to_csv(signals:List[InstitutionalSignal], path:str): ExportEngine._ensure(path); pd.DataFrame([ExportEngine._dump(s) for s in signals]).to_csv(path,index=False,encoding="utf-8-sig")
    @staticmethod
    def to_json(signals:List[InstitutionalSignal], path:str, narratives:List[Narrative]|None=None):
        ExportEngine._ensure(path); payload={"signals":[ExportEngine._dump(s) for s in signals],"narratives":[ExportEngine._dump(n) for n in (narratives or [])]}
        Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
