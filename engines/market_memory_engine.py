"""Market Memory Engine — in-memory historical pattern similarity matching."""
from __future__ import annotations
from typing import Any, Dict, List
import numpy as np, pandas as pd
class MarketMemoryEngine:
    def __init__(self, memory_window:int=100): self.memory_window=max(20,int(memory_window)); self.pattern_memory:List[Dict[str,Any]]=[]
    def store_pattern(self,candles:pd.DataFrame,label:str,metadata:dict|None=None):
        if candles is None or len(candles)<10 or "close" not in candles.columns: return None
        pat={"label":label,"candles":candles.iloc[-self.memory_window:].to_dict("records"),"metadata":metadata or {},"timestamp":candles.timestamp.iloc[-1] if "timestamp" in candles.columns else pd.Timestamp.utcnow()}
        self.pattern_memory.append(pat); return pat
    def find_similar(self,recent_candles:pd.DataFrame,top_n:int=3)->List[Dict]:
        if top_n<=0 or recent_candles is None or len(recent_candles)<10 or "close" not in recent_candles.columns or not self.pattern_memory: return []
        recent=self._path(recent_candles.close.tail(20))
        sims=[]
        for mem in self.pattern_memory:
            df=pd.DataFrame(mem["candles"])
            if "close" not in df.columns or len(df)<len(recent): continue
            corr=self._corr(recent,self._path(df.close.tail(len(recent))))
            sims.append((corr,mem))
        sims.sort(key=lambda x:x[0],reverse=True)
        return [{"similarity":s,"label":m["label"],"metadata":m["metadata"]} for s,m in sims[:top_n]]
    def _path(self,s):
        arr=pd.to_numeric(s,errors="coerce").dropna().to_numpy(float)
        if len(arr)<2: return np.zeros(1)
        return arr/arr[0]-1 if arr[0]!=0 else np.diff(arr,prepend=arr[0])
    def _corr(self,a,b):
        if len(a)!=len(b) or np.std(a)==0 or np.std(b)==0: return 0.0
        c=float(np.corrcoef(a,b)[0,1]); return 0.0 if np.isnan(c) else max(0.0,min(1.0,c))
    def memory_size(self): return len(self.pattern_memory)
    def clear_memory(self): self.pattern_memory.clear()
