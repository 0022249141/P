"""Generate Electron Builder config for Windows installer."""
from __future__ import annotations
import json
from pathlib import Path

def generate_builder_config(output_path:str="electron-builder.json", icon_path:str="assets/icon.ico", include_data:bool=False):
    resources=[{"from":"backend","to":"backend"},{"from":"config","to":"config"},{"from":"assets","to":"assets"}]
    if include_data: resources.append({"from":"data/sample","to":"data/sample"})
    config={"appId":"com.abshodeh.quant.terminal","productName":"Abshodeh Quant Terminal","directories":{"output":"dist"},"win":{"target":"nsis","icon":icon_path},"nsis":{"oneClick":False,"allowToChangeInstallationDirectory":True,"language":"1033"},"extraResources":resources}
    path=Path(output_path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(config,indent=2,ensure_ascii=False),encoding="utf-8"); return config
