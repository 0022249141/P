"""FastAPI backend for Electron frontend via REST and WebSocket."""
from __future__ import annotations
from datetime import datetime
import asyncio
from enum import Enum
from threading import Lock
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
app=FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_lock=Lock(); latest_data={"signals":[],"narratives":[],"market_state":"unresolved","updated_at":None}
def _dump(obj):
    if obj is None: return None
    if hasattr(obj,"model_dump"): return obj.model_dump(mode="json")
    if hasattr(obj,"dict"): return obj.dict()
    if isinstance(obj,Enum): return obj.value
    if hasattr(obj,"isoformat"): return obj.isoformat()
    if isinstance(obj,dict): return {k:_dump(v) for k,v in obj.items()}
    if isinstance(obj,list): return [_dump(x) for x in obj]
    return obj
@app.get("/api/health")
async def health(): return {"status":"ok"}
@app.get("/api/latest")
async def latest():
    with _lock: return dict(latest_data)
@app.get("/api/signals")
async def signals():
    with _lock: return latest_data.get("signals",[])
@app.get("/api/narratives")
async def narratives():
    with _lock: return latest_data.get("narratives",[])
@app.websocket("/ws")
async def websocket_endpoint(websocket:WebSocket):
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(1)
            with _lock: payload=dict(latest_data)
            await websocket.send_json(payload)
    except WebSocketDisconnect: return

def update_dashboard(signal, narrative, state):
    with _lock:
        latest_data["signals"]=[_dump(signal)] if signal is not None else []
        latest_data["narratives"]=[_dump(narrative)] if narrative is not None else []
        latest_data["market_state"]=_dump(state)
        latest_data["updated_at"]=datetime.utcnow().isoformat()
