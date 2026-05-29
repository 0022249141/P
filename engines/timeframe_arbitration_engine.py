"""Resolves conflicts between higher/lower timeframe narratives."""
from __future__ import annotations
from typing import Dict
from core.schemas import MarketState, TimeFrame

def _tf(x): return x if isinstance(x,TimeFrame) else TimeFrame(x)
def _st(x): return x if isinstance(x,MarketState) else MarketState(x)
class TimeframeArbitrationEngine:
    def __init__(self):
        self.timeframe_hierarchy=[TimeFrame.M1,TimeFrame.M5,TimeFrame.M15,TimeFrame.M30,TimeFrame.H1,TimeFrame.H4,TimeFrame.D1,TimeFrame.W1,TimeFrame.MN1]
        self.authority_scores={TimeFrame.MN1:1.2,TimeFrame.W1:1.1,TimeFrame.D1:1.0,TimeFrame.H4:0.9,TimeFrame.H1:0.7,TimeFrame.M30:0.55,TimeFrame.M15:0.4,TimeFrame.M5:0.2,TimeFrame.M1:0.1}
    def arbitrate(self, states: Dict[TimeFrame,MarketState])->dict:
        normalized={}
        for k,v in (states or {}).items():
            try: normalized[_tf(k)]=_st(v)
            except Exception: continue
        if not normalized: return self._empty()
        scores={"bullish":0.0,"bearish":0.0,"neutral":0.0}; total=0.0
        for tf,state in normalized.items():
            w=self.authority_scores.get(tf,0.1); total+=w; scores[self._state_to_bias(state)]+=w
        if total<=0: return self._empty()
        scores={k:v/total for k,v in scores.items()}; bias=max(scores,key=scores.get); align=max(0.0,min(1.0,scores[bias]))
        dominant_tf=max(normalized,key=lambda t:self.authority_scores.get(t,0))
        exec_tf=None
        for tf in self.timeframe_hierarchy:
            if tf in normalized and self._state_to_bias(normalized[tf])==bias: exec_tf=tf
        return {"dominant_bias":bias,"timeframe_alignment_score":align,"execution_authority":exec_tf,"dominant_authority_tf":dominant_tf,"bias_scores":scores,"conflict_detected":align<0.55}
    def _empty(self): return {"dominant_bias":"neutral","timeframe_alignment_score":0.0,"execution_authority":None,"dominant_authority_tf":None,"bias_scores":{"bullish":0.0,"bearish":0.0,"neutral":1.0},"conflict_detected":False}
    def _state_to_bias(self,state):
        if state==MarketState.ACCUMULATION: return "bullish"
        if state==MarketState.DISTRIBUTION: return "bearish"
        return "neutral"
