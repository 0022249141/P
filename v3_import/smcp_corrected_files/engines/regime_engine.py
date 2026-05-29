"""Regime Engine — classifies regime from volatility, trend, and manipulation evidence."""
from __future__ import annotations
import numpy as np, pandas as pd
from typing import Optional
from core.schemas import Market, MarketState, RegimeSnapshot, RegimeType, TimeFrame

def _clamp(x): return max(0.0, min(1.0, float(x)))

class RegimeEngine:
    def __init__(self, volatility_lookback: int = 50, manipulation_window: int = 20):
        self.vol_lookback=max(20, int(volatility_lookback)); self.manipulation_window=max(5, int(manipulation_window))
    def evaluate(self, candles: pd.DataFrame, current_market_state: Optional[MarketState]=None, market: Market=Market.ABSHODEH, timeframe: TimeFrame=TimeFrame.H1) -> RegimeSnapshot:
        if candles is None or candles.empty or not {"open","high","low","close"}.issubset(candles.columns):
            return self._snap(market, RegimeType.LOW_VOL, 0.0, 0.0)
        df=candles.copy()
        for c in ["open","high","low","close"]: df[c]=pd.to_numeric(df[c], errors="coerce")
        df=df.dropna(subset=["open","high","low","close"]).reset_index(drop=True)
        if len(df)<10: return self._snap(market, RegimeType.LOW_VOL, 0.0, 0.0, df)
        recent=df.iloc[-min(self.vol_lookback,len(df)):]
        range_pct=((recent.high-recent.low).abs()/recent.close.shift(1).replace(0,np.nan)).replace([np.inf,-np.inf],np.nan).dropna()
        if range_pct.empty: return self._snap(market, RegimeType.LOW_VOL, 0.0, 0.0, recent)
        vol_current=float(range_pct.iloc[-1]); vol_pct=self._percentile_of(vol_current, range_pct)
        slope_norm, r2 = self._trend(recent.close)
        manip=self._manipulation_index(recent)
        regime=self._classify(vol_pct, slope_norm, r2, manip, current_market_state)
        return self._snap(market, regime, vol_pct, manip, recent)
    def _snap(self, market, regime, vol, manip, df=None):
        ts=pd.Timestamp.utcnow().to_pydatetime()
        if df is not None and len(df) and "timestamp" in df.columns:
            t=pd.to_datetime(df.timestamp.iloc[-1], errors="coerce"); ts=t.to_pydatetime() if pd.notna(t) else ts
        return RegimeSnapshot(timestamp=ts, market=market, regime=regime, volatility_percentile=_clamp(vol), manipulation_index=_clamp(manip))
    def _percentile_of(self, value, series):
        s=series.dropna(); return 0.0 if s.empty else _clamp((s<value).mean())
    def _trend(self, close):
        c=pd.to_numeric(close, errors="coerce").dropna().to_numpy(float)
        if len(c)<3 or np.nanstd(c)==0: return 0.0,0.0
        x=np.arange(len(c)); a,b=np.polyfit(x,c,1); line=a*x+b
        ss_res=float(np.sum((c-line)**2)); ss_tot=float(np.sum((c-c.mean())**2)) or 1e-9
        return float((line[-1]-line[0])/max(abs(c.mean()),1e-9)), _clamp(1-ss_res/ss_tot)
    def _manipulation_index(self, candles):
        if len(candles)<3: return 0.0
        rng=(candles.high-candles.low).abs(); med=float(rng.median() or 0); count=0
        for i in range(2,len(candles)):
            ph,pl=candles.high.iloc[i-1],candles.low.iloc[i-1]; h,l,cl=candles.high.iloc[i],candles.low.iloc[i],candles.close.iloc[i]
            if h>ph+0.25*med and cl<ph: count+=1
            if l<pl-0.25*med and cl>pl: count+=1
        return _clamp(count/max(len(candles),1)*4)
    def _classify(self, vol_pct, slope, r2, manip, state):
        if manip>0.35 or state==MarketState.MANIPULATION: return RegimeType.MANIPULATION
        if vol_pct<0.25 and abs(slope)<0.003: return RegimeType.COMPRESSION
        if vol_pct>0.80: return RegimeType.EXPANSION
        if state==MarketState.DELIVERY_COMMIT and r2>0.55 and abs(slope)>0.003: return RegimeType.DELIVERY
        if r2>0.65 and abs(slope)>0.006: return RegimeType.DELIVERY
        if abs(slope)<0.002 and 0.25<=vol_pct<=0.75: return RegimeType.TRANSFER
        if vol_pct>0.60: return RegimeType.HIGH_VOL
        if vol_pct<0.35: return RegimeType.LOW_VOL
        if state==MarketState.ACCUMULATION: return RegimeType.ACCUMULATION
        if state==MarketState.DISTRIBUTION: return RegimeType.DISTRIBUTION
        return RegimeType.LOW_VOL
