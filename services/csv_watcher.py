"""
Polling-based CSV watcher for offline environments.

Detects manual CSV updates, validates the OHLCV payload, and emits an internal
system event that can trigger the institutional pipeline.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pandas as pd

from core.schemas import EventType, Market, SystemEvent, TimeFrame
from validators.data_quality_engine import DataQualityEngine


class CSVWatcher:
    """Watch a data directory tree for CSV file changes using polling."""

    TIMEFRAME_ALIASES = {
        "1": TimeFrame.M1,
        "1m": TimeFrame.M1,
        "5": TimeFrame.M5,
        "5m": TimeFrame.M5,
        "15": TimeFrame.M15,
        "15m": TimeFrame.M15,
        "60": TimeFrame.H1,
        "1h": TimeFrame.H1,
        "240": TimeFrame.H4,
        "4h": TimeFrame.H4,
        "1d": TimeFrame.D1,
        "d1": TimeFrame.D1,
    }

    MARKET_ALIASES = {
        "abshodeh": Market.ABSHODEH,
        "abshodenaghdi": Market.ABSHODEH,
        "xauusd": Market.XAUUSD,
        "xau_usd": Market.XAUUSD,
        "herat": Market.HERAT,
        "haratfardayi": Market.HERAT,
    }

    def __init__(
        self,
        base_data_dir: str = "./data",
        event_bus: Any | None = None,
        polling_interval: float = 2.0,
        min_quality_score: float = 0.5,
    ) -> None:
        if polling_interval <= 0:
            raise ValueError("polling_interval must be greater than zero")
        if not 0 <= min_quality_score <= 1:
            raise ValueError("min_quality_score must be between 0 and 1")

        self.base_dir = Path(base_data_dir)
        self.event_bus = event_bus
        self.polling_interval = polling_interval
        self.min_quality_score = min_quality_score
        self.quality_engine = DataQualityEngine()
        self._known_files: dict[str, float] = {}
        self._running = False

    async def start(self) -> None:
        """Start polling for CSV file changes until :meth:`stop` is called."""

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        print(
            f"[CSVWatcher] Polling {self.base_dir} every "
            f"{self.polling_interval}s for CSV changes..."
        )
        while self._running:
            await self._check_all_files()
            await asyncio.sleep(self.polling_interval)

    def stop(self) -> None:
        """Stop polling after the current iteration completes."""

        self._running = False
        print("[CSVWatcher] Stopped.")

    async def _check_all_files(self) -> None:
        """Check all CSV files in the data directory for modifications."""

        for csv_path in self.base_dir.rglob("*.csv"):
            try:
                mod_time = csv_path.stat().st_mtime
                key = str(csv_path.resolve())
                if key not in self._known_files or self._known_files[key] < mod_time:
                    self._known_files[key] = mod_time
                    await self._process_file(csv_path)
            except FileNotFoundError:
                continue
            except Exception as exc:  # pragma: no cover - defensive watcher logging
                print(f"[CSVWatcher] Error checking {csv_path}: {exc}")

    async def _process_file(self, file_path: Path) -> None:
        """Validate and emit an event for an added or modified CSV file."""

        market = self._extract_market(file_path)
        if market is None:
            print(f"[CSVWatcher] Unknown market in path: {file_path}")
            return

        timeframe = self._extract_timeframe(file_path)
        if timeframe is None:
            print(f"[CSVWatcher] Unknown timeframe in filename: {file_path.name}")
            return

        try:
            df = pd.read_csv(file_path)
        except Exception as exc:
            print(f"[CSVWatcher] Error reading {file_path}: {exc}")
            return

        quality_report = self.quality_engine.validate_dataframe(df, market, timeframe)
        if quality_report.quality_score < self.min_quality_score:
            print(
                f"[CSVWatcher] Data quality too low "
                f"({quality_report.quality_score:.2f}), ignoring."
            )
            return

        print(
            f"[CSVWatcher] Valid CSV update: {file_path} "
            f"(Quality: {quality_report.quality_score:.2f})"
        )
        event = self._build_event(file_path, df, market, timeframe, quality_report.quality_score)
        await self._publish_event(event)

    def _build_event(
        self,
        file_path: Path,
        df: pd.DataFrame,
        market: Market,
        timeframe: TimeFrame,
        quality_score: float,
    ) -> SystemEvent:
        return SystemEvent(
            event_id=f"csv_update_{time.time_ns()}",
            event_type=EventType.CSV_UPDATED,
            source_engine="csv_watcher",
            payload={
                "market": market.value,
                "timeframe": timeframe.value,
                "file_path": str(file_path),
                "quality_score": quality_score,
                "row_count": int(len(df)),
                "data": df.to_dict(orient="records"),
            },
        )

    async def _publish_event(self, event: SystemEvent) -> None:
        if self.event_bus is None:
            print(f"[CSVWatcher] Event: {event.event_type.value} {event.payload}")
            return

        publish = getattr(self.event_bus, "publish", None)
        if publish is None:
            raise AttributeError("event_bus must expose a publish(event) method")
        result = publish(event)
        if hasattr(result, "__await__"):
            await result

    def _extract_market(self, file_path: Path) -> Market | None:
        tokens = self._path_tokens(file_path)
        for token in tokens:
            if token in self.MARKET_ALIASES:
                return self.MARKET_ALIASES[token]
        return None

    def _extract_timeframe(self, file_path: Path) -> TimeFrame | None:
        stem_tokens = self._normalize_token(file_path.stem).split("-")
        candidates = [stem_tokens[-1], *stem_tokens]
        for candidate in candidates:
            if candidate in self.TIMEFRAME_ALIASES:
                return self.TIMEFRAME_ALIASES[candidate]
            try:
                return TimeFrame(candidate)
            except ValueError:
                continue
        return None

    def _path_tokens(self, file_path: Path) -> list[str]:
        tokens: list[str] = []
        for part in file_path.parts:
            tokens.extend(self._normalize_token(part).split("-"))
        return tokens

    def _normalize_token(self, value: str) -> str:
        return value.strip().lower().replace(" ", "_")
