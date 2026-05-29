"""
services/csv_watcher.py
Polling-based CSV watcher for offline environments.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
import pandas as pd
from core.schemas import EventType, Market, SystemEvent, TimeFrame
from validators.data_quality_engine import DataQualityEngine

logger = logging.getLogger(__name__)


class CSVWatcher:
    def __init__(self, base_data_dir: str = "./data", event_bus: Optional[Any] = None, polling_interval: float = 2.0):
        self.base_dir = Path(base_data_dir)
        self.event_bus = event_bus
        self.polling_interval = float(max(0.25, polling_interval))
        self.quality_engine = DataQualityEngine()
        self._known_files: dict[str, float] = {}
        self._running = False

    async def start(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        logger.info("CSVWatcher polling %s every %.2fs", self.base_dir, self.polling_interval)
        while self._running:
            await self._check_all_files()
            await asyncio.sleep(self.polling_interval)

    def stop(self) -> None:
        self._running = False
        logger.info("CSVWatcher stopped")

    async def _check_all_files(self) -> None:
        for csv_path in self.base_dir.rglob("*.csv"):
            try:
                stat = csv_path.stat()
                key = str(csv_path.resolve())
                if key not in self._known_files or self._known_files[key] < stat.st_mtime:
                    if await self._is_file_stable(csv_path):
                        self._known_files[key] = csv_path.stat().st_mtime
                        await self._process_file(csv_path)
            except FileNotFoundError:
                continue
            except Exception:
                logger.exception("Error checking CSV file %s", csv_path)

    async def _is_file_stable(self, path: Path, delay: float = 0.2) -> bool:
        try:
            size_1 = path.stat().st_size
            await asyncio.sleep(delay)
            size_2 = path.stat().st_size
            return size_1 == size_2
        except FileNotFoundError:
            return False

    async def _process_file(self, file_path: Path) -> None:
        market = self._extract_market(file_path)
        timeframe = self._extract_timeframe(file_path)
        if market is None or timeframe is None:
            logger.warning("Skipping %s: unable to infer market/timeframe", file_path)
            return
        try:
            df = pd.read_csv(file_path)
        except Exception:
            logger.exception("Error reading CSV %s", file_path)
            return

        quality_report = self.quality_engine.validate_dataframe(df, market, timeframe)
        if quality_report.quality_score < 0.5:
            logger.warning("Ignoring %s due to low quality %.2f: %s", file_path, quality_report.quality_score, quality_report.warnings)
            return

        event = SystemEvent(
            event_id=f"csv_update_{uuid4().hex}",
            event_type=EventType.CSV_UPDATED,
            source_engine="csv_watcher",
            payload={
                "market": market.value,
                "timeframe": timeframe.value,
                "file_path": str(file_path),
                "rows": int(len(df)),
                "quality_score": quality_report.quality_score,
                "integrity_score": quality_report.integrity_score,
                "warnings": quality_report.warnings,
            },
        )
        await self._publish(event)

    async def _publish(self, event: SystemEvent) -> None:
        if not self.event_bus:
            logger.info("Event: %s %s", event.event_type.value, event.payload)
            return
        result = self.event_bus.publish(event)
        if inspect.isawaitable(result):
            await result

    def _extract_market(self, file_path: Path) -> Optional[Market]:
        text = "/".join(part.lower() for part in file_path.parts)
        name = file_path.name.lower()
        if any(token in text or token in name for token in ["abshodeh", "abshodenaghdi", "abshode", "abshode-naghdi"]):
            return Market.ABSHODEH
        if any(token in text or token in name for token in ["xauusd", "xau_usd", "xau-usd"]):
            return Market.XAUUSD
        if "herat" in text or "harat" in text or "herat" in name or "harat" in name:
            return Market.HERAT
        return None

    def _extract_timeframe(self, file_path: Path) -> Optional[TimeFrame]:
        stem = file_path.stem.lower()
        match = re.search(r"(?:-|_)?(1m|5m|15m|30m|1h|4h|1d|1w|1month|1mo|1mth|1m)$", stem)
        token = match.group(1) if match else None
        if token is None:
            match = re.search(r"(?:-|_)(1|5|15|30|60|240|1d|1w|1m)$", stem)
            token = match.group(1) if match else stem
        mapping = {
            "1": TimeFrame.M1, "1m": TimeFrame.M1,
            "5": TimeFrame.M5, "5m": TimeFrame.M5,
            "15": TimeFrame.M15, "15m": TimeFrame.M15,
            "30": TimeFrame.M30, "30m": TimeFrame.M30,
            "60": TimeFrame.H1, "1h": TimeFrame.H1,
            "240": TimeFrame.H4, "4h": TimeFrame.H4,
            "1d": TimeFrame.D1,
            "1w": TimeFrame.W1,
            "1month": TimeFrame.MN1, "1mo": TimeFrame.MN1, "1mth": TimeFrame.MN1,
        }
        if file_path.stem.endswith("1M") or file_path.stem.lower().endswith("-1m") and "abshode" in stem and stem.endswith("-1m") is False:
            pass
        # Prefer exact raw suffix handling for files such as abshodeNaghdi-1M.csv.
        if re.search(r"[-_]1M$", file_path.stem):
            return TimeFrame.MN1
        return mapping.get(token)
