"""Candle-by-candle replay with state tracking and callback hooks."""
from __future__ import annotations
from typing import Callable, List
import logging, pandas as pd
from engines.market_state_machine import MarketStateMachine
logger=logging.getLogger(__name__)
class ReplayEngine:
    def __init__(self): self.state_machine=MarketStateMachine(); self.callbacks=[]
    def reset(self): self.state_machine=MarketStateMachine()
    def register_callback(self, cb: Callable[[int,pd.Series,dict],None]): self.callbacks.append(cb)
    def replay(self,candles:pd.DataFrame,start_index:int=0,reset:bool=True)->List[dict]:
        if reset: self.reset()
        if candles is None or candles.empty or not {"open","high","low","close"}.issubset(candles.columns): return []
        start=max(0,int(start_index)); history=[]
        for i in range(start,len(candles)):
            window=candles.iloc[:i+1]; state=self.state_machine.step(window)
            payload={"index":i,"timestamp":candles.iloc[i].get("timestamp",None),"window_size":len(window),"state":state.value}
            history.append(payload)
            for cb in list(self.callbacks):
                try: cb(i,candles.iloc[i],payload)
                except Exception: logger.exception("Replay callback failed")
        return history
