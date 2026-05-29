"""File-based Feature Store / Cache Layer with stable hashing and atomic writes."""
from __future__ import annotations
import hashlib, json, os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import numpy as np, pandas as pd
class FeatureCache:
    def __init__(self, cache_dir:str="./cache"):
        self.cache_dir=Path(cache_dir); self.cache_dir.mkdir(parents=True,exist_ok=True)
    def _cache_key(self,market:str,timeframe:str,feature_name:str,data_hash:str)->str:
        return hashlib.sha256(f"{market}_{timeframe}_{feature_name}_{data_hash}".encode()).hexdigest()
    def _canonical_df(self,df:pd.DataFrame)->list:
        d=df.tail(100).copy() if df is not None else pd.DataFrame()
        if "timestamp" in d.columns: d["timestamp"]=pd.to_datetime(d.timestamp,errors="coerce").astype(str); d=d.sort_values("timestamp")
        d=d.reindex(sorted(d.columns),axis=1).reset_index(drop=True)
        for c in d.select_dtypes(include=["float","float64","float32"]).columns: d[c]=d[c].round(10)
        return d.replace([np.inf,-np.inf],np.nan).where(pd.notnull(d),None).to_dict("records")
    def _data_hash(self,df:pd.DataFrame)->str:
        return hashlib.sha256(json.dumps(self._canonical_df(df),sort_keys=True,default=str).encode()).hexdigest()
    def _path(self,market,timeframe,feature,df): return self.cache_dir/f"{self._cache_key(market,timeframe,feature,self._data_hash(df))}.json"
    def get(self,market:str,timeframe:str,feature_name:str,df:pd.DataFrame)->Optional[Any]:
        path=self._path(market,timeframe,feature_name,df)
        if not path.exists(): return None
        try:
            with path.open("r",encoding="utf-8") as f: return json.load(f).get("value")
        except Exception:
            path.unlink(missing_ok=True); return None
    def _serialize(self,value):
        if isinstance(value,pd.DataFrame): return value.to_dict("records")
        if isinstance(value,pd.Series): return value.to_list()
        if hasattr(value,"model_dump"): return value.model_dump(mode="json")
        if hasattr(value,"dict"): return value.dict()
        return value
    def set(self,market:str,timeframe:str,feature_name:str,df:pd.DataFrame,value:Any):
        dh=self._data_hash(df); key=self._cache_key(market,timeframe,feature_name,dh); path=self.cache_dir/f"{key}.json"; tmp=path.with_suffix(".tmp")
        payload={"metadata":{"market":market,"timeframe":timeframe,"feature_name":feature_name,"data_hash":dh,"created_at":datetime.utcnow().isoformat()},"value":self._serialize(value)}
        with tmp.open("w",encoding="utf-8") as f: json.dump(payload,f,ensure_ascii=False,default=str)
        os.replace(tmp,path); return str(path)
    def invalidate(self,market:str,timeframe:str,feature_name:str,df:pd.DataFrame):
        self._path(market,timeframe,feature_name,df).unlink(missing_ok=True)
    def invalidate_feature(self,market:str,timeframe:str,feature_name:str):
        for p in self.cache_dir.glob("*.json"):
            try:
                meta=json.loads(p.read_text(encoding="utf-8")).get("metadata",{})
                if meta.get("market")==market and meta.get("timeframe")==timeframe and meta.get("feature_name")==feature_name: p.unlink(missing_ok=True)
            except Exception: p.unlink(missing_ok=True)
    def exists(self,market,timeframe,feature_name,df): return self._path(market,timeframe,feature_name,df).exists()
    def clear(self):
        for p in self.cache_dir.glob("*.json"): p.unlink(missing_ok=True)
