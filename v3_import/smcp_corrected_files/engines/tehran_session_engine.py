"""Tehran Session Engine — Tehran-local session proxies. Timestamps are expected to be Tehran-local naive datetimes."""
from __future__ import annotations
from datetime import datetime, time
from typing import Optional
import numpy as np, pandas as pd
from core.schemas import Market, TehranSessionInfo

class TehranSessionEngine:
    def __init__(self):
        self.tehran_open_time=time(9,0); self.tehran_close_time=time(16,30); self.pm_start=time(13,0)
    def evaluate(self, candles: pd.DataFrame, market: Market=Market.ABSHODEH, current_time: Optional[datetime]=None)->TehranSessionInfo:
        ts=current_time or pd.Timestamp.utcnow().to_pydatetime()
        df=pd.DataFrame() if candles is None else candles.copy()
        if not df.empty and "timestamp" in df.columns:
            df["timestamp"]=pd.to_datetime(df["timestamp"], errors="coerce")
            if current_time is None and pd.notna(df["timestamp"].iloc[-1]): ts=df["timestamp"].iloc[-1].to_pydatetime()
        return TehranSessionInfo(timestamp=ts, is_tehran_open=self._is_tehran_session(ts), is_friday=ts.weekday()==4, holiday_effect=self._is_holiday_effect(df), pm_manipulation_likely=self._detect_pm_manipulation(df), herat_correlation=None, local_volatility_spike=self._local_volatility_spike(df), spread_distortion_detected=self._detect_spread_distortion(df))
    def _is_tehran_session(self, ts: datetime)->bool:
        return self.tehran_open_time <= ts.time() <= self.tehran_close_time and ts.weekday()!=4
    def _ranges(self, df):
        if not {"high","low"}.issubset(df.columns): return pd.Series(dtype=float)
        return (pd.to_numeric(df.high,errors="coerce")-pd.to_numeric(df.low,errors="coerce")).abs().replace([np.inf,-np.inf],np.nan).dropna()
    def _volume_reliable(self, df):
        if "volume" not in df.columns: return False
        v=pd.to_numeric(df.volume,errors="coerce").fillna(0); return bool(v.sum()>0 and v.std()>0)
    def _is_holiday_effect(self, df)->bool:
        if len(df)<10: return False
        ranges=self._ranges(df); low_range=bool(len(ranges)>=10 and ranges.iloc[-5:].mean()<0.45*ranges.iloc[-min(30,len(ranges)):].mean())
        if self._volume_reliable(df):
            v=pd.to_numeric(df.volume,errors="coerce").fillna(0); return bool(v.iloc[-5:].mean()<0.35*v.iloc[-min(30,len(v)):].mean() or low_range)
        return low_range
    def _detect_pm_manipulation(self, df)->bool:
        if len(df)<10 or "timestamp" not in df.columns or not {"high","low","close"}.issubset(df.columns): return False
        afternoon=df[pd.to_datetime(df.timestamp,errors="coerce").dt.time>=self.pm_start]
        if len(afternoon)<3: return False
        range_pct=((afternoon.high-afternoon.low).abs()/afternoon.close.shift(1).replace(0,np.nan)).replace([np.inf,-np.inf],np.nan).dropna()
        return bool(len(range_pct)>1 and range_pct.iloc[-1] > 2.0*range_pct.mean())
    def _local_volatility_spike(self, df)->bool:
        ranges=self._ranges(df)
        if len(ranges)<30: return False
        return bool(ranges.iloc[-10:].mean() > 1.8*ranges.iloc[-30:].mean())
    def _detect_spread_distortion(self, df)->bool:
        if len(df)<5 or not {"open","close","high","low"}.issubset(df.columns): return False
        gaps=(pd.to_numeric(df.open,errors="coerce")-pd.to_numeric(df.close,errors="coerce").shift(1)).abs().iloc[-5:]
        ranges=self._ranges(df); median_range=float(ranges.median() or 0) if len(ranges) else 0
        avg=float(gaps.mean() or 0); threshold=max(3*avg,0.5*median_range)
        return bool(threshold>0 and (gaps>threshold).any())
