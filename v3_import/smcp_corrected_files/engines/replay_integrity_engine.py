"""Deterministic replay integrity hashing."""
from __future__ import annotations
import hashlib, json
from typing import Any
import numpy as np, pandas as pd
class ReplayIntegrityEngine:
    def hash_state(self, df:pd.DataFrame, state:Any)->str: return self.hash_payload({"dataframe":self._canon_df(df),"state":self._canon_obj(state)})
    def hash_payload(self,payload:Any)->str:
        raw=json.dumps(self._canon_obj(payload),sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    def verify(self, original_hash:str, replay_hash:str)->bool: return original_hash==replay_hash
    def _canon_df(self,df):
        if df is None: return []
        d=df.copy();
        if "timestamp" in d.columns: d["timestamp"]=pd.to_datetime(d["timestamp"],errors="coerce").astype(str); d=d.sort_values("timestamp")
        d=d.reindex(sorted(d.columns),axis=1).reset_index(drop=True)
        for c in d.select_dtypes(include=["float","float64","float32"]).columns: d[c]=d[c].round(10)
        return d.replace([np.inf,-np.inf],np.nan).where(pd.notnull(d),None).to_dict("records")
    def _canon_obj(self,obj):
        if hasattr(obj,"model_dump"): return obj.model_dump(mode="json")
        if hasattr(obj,"dict"): return obj.dict()
        if isinstance(obj,dict): return {str(k):self._canon_obj(v) for k,v in sorted(obj.items(), key=lambda kv:str(kv[0]))}
        if isinstance(obj,(list,tuple)): return [self._canon_obj(x) for x in obj]
        if hasattr(obj,"value"): return obj.value
        return obj
