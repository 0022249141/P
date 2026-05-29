"""Config loader for JSON and optional YAML config files."""
from __future__ import annotations
import json, logging
from pathlib import Path
from typing import Any, Dict, Optional
logger=logging.getLogger(__name__)
class Config:
    def __init__(self,config_dir:str="./config"):
        self.config_dir=Path(config_dir); self._cache:Dict[str,Any]={}
    def load(self,name:str, default:Optional[Dict[str,Any]]=None)->Dict[str,Any]:
        if name in self._cache: return self._cache[name]
        data=default or {}
        for ext in [".json",".yaml",".yml"]:
            path=self.config_dir/f"{name}{ext}"
            if path.exists():
                try:
                    if ext==".json": data=json.loads(path.read_text(encoding="utf-8"))
                    else:
                        try:
                            import yaml
                            data=yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                        except ImportError: data=default or {}
                    break
                except Exception as e:
                    logger.warning("Failed to load config %s: %s", path, e); data=default or {}; break
        self._cache[name]=data; return data
    def reload(self,name:str): self._cache.pop(name,None); return self.load(name)
    def clear_cache(self): self._cache.clear()
    def has_config(self,name:str)->bool: return any((self.config_dir/f"{name}{ext}").exists() for ext in [".json",".yaml",".yml"])
    def get_value(self,path:str, default=None):
        parts=path.split("."); data=self.load(parts[0])
        for p in parts[1:]:
            if not isinstance(data,dict) or p not in data: return default
            data=data[p]
        return data
    def get_market_config(self,market:str)->Dict[str,Any]: return self.load(f"markets/{market}")
    def get_thresholds(self)->Dict[str,Any]: return self.load("thresholds")
    def get_sessions(self)->Dict[str,Any]: return self.load("sessions")
