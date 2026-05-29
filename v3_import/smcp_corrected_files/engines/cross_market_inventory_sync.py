"""Cross-market synchronization engine for Abshodeh, XAUUSD, and Herat."""
from __future__ import annotations
import numpy as np, pandas as pd
from typing import Dict, Optional
from core.schemas import CrossMarketSyncState, LiquidityMap, Market, TimeFrame

def _clamp(x): return max(0.0, min(1.0, float(x)))
def _safe_corr(a,b):
    c=a.corr(b)
    return 0.0 if pd.isna(c) or np.isinf(c) else float(c)

class CrossMarketInventorySync:
    def __init__(self, correlation_window:int=50): self.correlation_window=max(20,int(correlation_window))
    def evaluate(self, abshodeh_candles:pd.DataFrame, xauusd_candles:pd.DataFrame, herat_candles:pd.DataFrame, abshodeh_liquidity:Optional[LiquidityMap]=None, xauusd_liquidity:Optional[LiquidityMap]=None, herat_liquidity:Optional[LiquidityMap]=None, timeframe:TimeFrame=TimeFrame.H1)->CrossMarketSyncState:
        prepared=[self._prep(df, prefix) for df,prefix in [(abshodeh_candles,"abs"),(xauusd_candles,"xau"),(herat_candles,"herat")]]
        if any(df.empty for df in prepared): return self._state("unknown",0.0,Market.ABSHODEH,"neutral")
        merged=self._align(prepared, timeframe)
        if len(merged)<max(5,self.correlation_window//2): return self._state("insufficient_data",0.0,Market.ABSHODEH,"neutral", self._ts(prepared[0]))
        returns=merged[["close_abs","close_xau","close_herat"]].pct_change().replace([np.inf,-np.inf],np.nan).dropna()
        if len(returns)<5: return self._state("insufficient_data",0.0,Market.ABSHODEH,"neutral", self._ts(merged))
        r=returns.iloc[-self.correlation_window:]
        cax=_safe_corr(r.close_abs,r.close_xau); cah=_safe_corr(r.close_abs,r.close_herat); cxh=_safe_corr(r.close_xau,r.close_herat)
        lead=self._lead_lag_analysis(r.close_abs,r.close_xau,r.close_herat)
        dominant=self._dominant_market(r,lead); transfer=self._transfer_direction(lead,cax,cah)
        smt=self._detect_smt_divergence(merged)
        divergence=self._divergence_score(cax,cah,cxh,smt)
        sync=self._synchronization_state(divergence,lead)
        return CrossMarketSyncState(timestamp=self._ts(merged), dominant_market=dominant, transfer_direction=transfer, divergence_score=round(divergence,4), synchronization_state=sync, smt_divergence_detected=smt)
    def _prep(self, df, prefix):
        req={"timestamp","high","low","close"}
        if df is None or df.empty or not req.issubset(df.columns): return pd.DataFrame()
        out=df[list(req)].copy(); out["timestamp"]=pd.to_datetime(out.timestamp, errors="coerce")
        for c in ["high","low","close"]: out[c]=pd.to_numeric(out[c], errors="coerce")
        out=out.dropna().drop_duplicates("timestamp").sort_values("timestamp")
        return out.rename(columns={"high":f"high_{prefix}","low":f"low_{prefix}","close":f"close_{prefix}"})
    def _align(self, dfs, tf):
        tolerance=pd.Timedelta(minutes={TimeFrame.M1:1,TimeFrame.M5:5,TimeFrame.M15:15,TimeFrame.M30:30,TimeFrame.H1:60,TimeFrame.H4:240,TimeFrame.D1:1440}.get(tf,60))
        merged=pd.merge_asof(dfs[0], dfs[1], on="timestamp", tolerance=tolerance, direction="nearest")
        merged=pd.merge_asof(merged.dropna(), dfs[2], on="timestamp", tolerance=tolerance, direction="nearest").dropna()
        return merged
    def _ts(self, df):
        return (pd.to_datetime(df.timestamp.iloc[-1]).to_pydatetime() if len(df) and "timestamp" in df.columns else pd.Timestamp.utcnow().to_pydatetime())
    def _state(self,sync,div,dom,transfer,ts=None): return CrossMarketSyncState(timestamp=ts or pd.Timestamp.utcnow().to_pydatetime(), dominant_market=dom, transfer_direction=transfer, divergence_score=div, synchronization_state=sync)
    def _lead_lag_analysis(self,a,b,c):
        # positive lag => first market leads second by lag candles
        out={}
        for name,s1,s2 in [("abs_xau",a,b),("abs_herat",a,c),("xau_herat",b,c)]:
            best=(0,0.0)
            for lag in range(-5,6):
                corr=_safe_corr(s1.shift(lag),s2)
                if abs(corr)>abs(best[1]): best=(-lag,corr)
            out[name]=best[0]
        return out
    def _dominant_market(self,r,lead):
        scores={Market.ABSHODEH:r.close_abs.std() or 0, Market.XAUUSD:r.close_xau.std() or 0, Market.HERAT:r.close_herat.std() or 0}
        if lead.get("abs_xau",0)>0: scores[Market.ABSHODEH]+=0.05
        if lead.get("abs_xau",0)<0: scores[Market.XAUUSD]+=0.05
        if lead.get("abs_herat",0)>0: scores[Market.ABSHODEH]+=0.05
        if lead.get("abs_herat",0)<0: scores[Market.HERAT]+=0.05
        if lead.get("xau_herat",0)>0: scores[Market.XAUUSD]+=0.05
        if lead.get("xau_herat",0)<0: scores[Market.HERAT]+=0.05
        return max(scores,key=scores.get)
    def _transfer_direction(self,lead,cax,cah):
        if lead.get("abs_xau",0)>0 and cax>0.45: return "abshodeh_leading_xau"
        if lead.get("abs_xau",0)<0 and cax>0.45: return "xau_leading_abshodeh"
        if lead.get("abs_herat",0)>0 and cah>0.45: return "abshodeh_leading_herat"
        if lead.get("abs_herat",0)<0 and cah>0.45: return "herat_leading_abshodeh"
        return "neutral"
    def _detect_smt_divergence(self,m):
        if len(m)<10: return False
        w=m.iloc[-10:]
        abs_h=w.high_abs.iloc[-1]>w.high_abs.max()-1e-12; xau_h=w.high_xau.iloc[-1]>w.high_xau.max()-1e-12; her_h=w.high_herat.iloc[-1]>w.high_herat.max()-1e-12
        abs_l=w.low_abs.iloc[-1]<w.low_abs.min()+1e-12; xau_l=w.low_xau.iloc[-1]<w.low_xau.min()+1e-12; her_l=w.low_herat.iloc[-1]<w.low_herat.min()+1e-12
        return bool((abs_h != xau_h) or (abs_h != her_h) or (abs_l != xau_l) or (abs_l != her_l))
    def _divergence_score(self,cax,cah,cxh,smt):
        avg=max((cax+cah+cxh)/3,0.0); return _clamp(1-avg+(0.25 if smt else 0))
    def _synchronization_state(self,div,lead):
        maxlag=max(abs(v) for v in lead.values()) if lead else 0
        if div<0.3 and maxlag<=1: return "aligned"
        if div<0.65 or maxlag>1: return "lagging"
        return "divergent"
