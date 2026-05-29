"""Proxy microstructure abstraction from OHLCV; real order flow is not observed."""
from __future__ import annotations
import numpy as np, pandas as pd

def _clamp(x,lo=0,hi=1): return max(lo,min(hi,float(x)))
class MicrostructureEngine:
    def evaluate(self,candles:pd.DataFrame)->dict:
        out={"synthetic_imbalance":0.0,"absorption_ratio":0.0,"displacement_efficiency":0.0,"candle_efficiency":0.0,"volume_reliable":False,"warnings":[]}
        if candles is None or len(candles)<10 or not {"open","high","low","close"}.issubset(candles.columns): out["warnings"].append("insufficient_data_or_columns"); return out
        df=candles.copy()
        for c in ["open","high","low","close","volume"]:
            if c in df.columns: df[c]=pd.to_numeric(df[c],errors="coerce")
        df=df.dropna(subset=["open","high","low","close"])
        if len(df)<10: out["warnings"].append("insufficient_clean_rows"); return out
        rng=(df.high-df.low).abs().replace(0,np.nan); body=(df.close-df.open).abs(); norm_delta=((df.close-df.open)/rng).replace([np.inf,-np.inf],np.nan).fillna(0).clip(-1,1)
        vol=pd.to_numeric(df.volume,errors="coerce").fillna(0) if "volume" in df.columns else pd.Series(1.0,index=df.index)
        vol_rel=bool(vol.sum()>0 and vol.std()>0); out["volume_reliable"]=vol_rel
        weights=vol/vol.sum() if vol_rel else pd.Series(1/len(df),index=df.index)
        out["synthetic_imbalance"]=_clamp((norm_delta*weights).sum(),-1,1)
        vol_ratio=(vol/vol.rolling(10).mean()).replace([np.inf,-np.inf],np.nan).fillna(1) if vol_rel else pd.Series(1,index=df.index)
        price_change=df.close.diff().abs().fillna(0); absorption=((price_change<price_change.rolling(10).mean().fillna(price_change.mean())) & ((vol_ratio>1.5) if vol_rel else (body/rng).fillna(0)<0.35)).mean()
        out["absorption_ratio"]=_clamp(absorption)
        out["displacement_efficiency"]=_clamp(abs(df.close.iloc[-1]-df.close.iloc[0])/max(rng.fillna(0).sum(),1e-9))
        out["candle_efficiency"]=_clamp((body/rng).replace([np.inf,-np.inf],np.nan).fillna(0).clip(0,1).mean())
        return out
