"""SQLite storage for candles, signals, and narratives."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Optional
import pandas as pd

def _v(x): return getattr(x,"value",x)
def _ser(x):
    if hasattr(x,"isoformat"): return x.isoformat()
    if isinstance(x,(list,dict)): return json.dumps(x,ensure_ascii=False,default=str)
    return _v(x)
class Database:
    def __init__(self, db_path:str="./data/terminal.db"):
        self.db_path=Path(db_path); self.db_path.parent.mkdir(parents=True,exist_ok=True); self.conn=sqlite3.connect(self.db_path,check_same_thread=False); self._init_tables()
    def _init_tables(self):
        self.conn.executescript("""CREATE TABLE IF NOT EXISTS signals (id TEXT PRIMARY KEY,timestamp TEXT,market TEXT,direction TEXT,entry_price REAL,invalidation_price REAL,liquidity_target REAL,delivery_target REAL,probability REAL,confidence REAL,regime TEXT,dealer_narrative TEXT,inventory_state TEXT,session_context TEXT,risk_grade TEXT,execution_timing TEXT,expected_sequence TEXT);
CREATE TABLE IF NOT EXISTS narratives (id TEXT PRIMARY KEY,timestamp TEXT,market TEXT,english_text TEXT,persian_text TEXT,consumed_liquidity TEXT,remaining_liquidity TEXT,invalidation_condition TEXT,commitment_status TEXT);
CREATE TABLE IF NOT EXISTS candles (timestamp TEXT,market TEXT,timeframe TEXT,open REAL,high REAL,low REAL,close REAL,volume REAL,PRIMARY KEY(timestamp,market,timeframe));"""); self.conn.commit()
    def _model_dict(self,obj):
        if hasattr(obj,"model_dump"): return obj.model_dump()
        if hasattr(obj,"dict"): return obj.dict()
        return dict(obj)
    def insert_signal(self, signal_data:dict):
        d=self._model_dict(signal_data); row={k:_ser(d.get(k)) for k in ["id","timestamp","market","direction","entry_price","invalidation_price","liquidity_target","delivery_target","probability","confidence","regime","dealer_narrative","inventory_state","session_context","risk_grade","execution_timing","expected_sequence"]}
        self.conn.execute("INSERT OR REPLACE INTO signals VALUES (:id,:timestamp,:market,:direction,:entry_price,:invalidation_price,:liquidity_target,:delivery_target,:probability,:confidence,:regime,:dealer_narrative,:inventory_state,:session_context,:risk_grade,:execution_timing,:expected_sequence)",row); self.conn.commit()
    def insert_narrative(self,narrative_data:dict):
        d=self._model_dict(narrative_data); row={k:_ser(d.get(k)) for k in ["id","timestamp","market","english_text","persian_text","consumed_liquidity","remaining_liquidity","invalidation_condition","commitment_status"]}
        self.conn.execute("INSERT OR REPLACE INTO narratives VALUES (:id,:timestamp,:market,:english_text,:persian_text,:consumed_liquidity,:remaining_liquidity,:invalidation_condition,:commitment_status)",row); self.conn.commit()
    def store_candles(self,df:pd.DataFrame,market:str,timeframe:str):
        if df is None or df.empty: return 0
        d=df.copy(); d["timestamp"]=pd.to_datetime(d.timestamp,errors="coerce").astype(str); d["market"]=market; d["timeframe"]=timeframe
        cols=["timestamp","market","timeframe","open","high","low","close","volume"]; rows=d[cols].where(pd.notnull(d[cols]),None).to_dict("records")
        self.conn.executemany("INSERT OR REPLACE INTO candles VALUES (:timestamp,:market,:timeframe,:open,:high,:low,:close,:volume)",rows); self.conn.commit(); return len(rows)
    def load_candles(self,market:str,timeframe:str,start:Optional[str]=None,end:Optional[str]=None)->pd.DataFrame:
        q="SELECT * FROM candles WHERE market=? AND timeframe=?"; params=[market,timeframe]
        if start: q+=" AND timestamp >= ?"; params.append(start)
        if end: q+=" AND timestamp <= ?"; params.append(end)
        q+=" ORDER BY timestamp ASC"; return pd.read_sql_query(q,self.conn,params=params,parse_dates=["timestamp"])
    def load_signals(self): return pd.read_sql_query("SELECT * FROM signals ORDER BY timestamp ASC", self.conn)
    def load_narratives(self): return pd.read_sql_query("SELECT * FROM narratives ORDER BY timestamp ASC", self.conn)
    def close(self):
        if getattr(self,"conn",None): self.conn.close(); self.conn=None
    def __enter__(self): return self
    def __exit__(self,*exc): self.close()
