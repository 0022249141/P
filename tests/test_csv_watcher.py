from __future__ import annotations

import asyncio

import pandas as pd

from core.schemas import EventType, Market, TimeFrame
from services.csv_watcher import CSVWatcher
from validators.data_quality_engine import DataQualityEngine


class RecordingBus:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


def valid_candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=3, freq="min", tz="UTC"),
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [10.0, 11.0, 12.0],
        }
    )


def test_data_quality_engine_scores_valid_ohlcv_dataframe_high() -> None:
    report = DataQualityEngine().validate_dataframe(valid_candles(), Market.XAUUSD, TimeFrame.M1)

    assert report.quality_score > 0.95
    assert report.integrity_score == 1.0
    assert report.warnings == []


def test_data_quality_engine_rejects_missing_required_columns() -> None:
    report = DataQualityEngine().validate_dataframe(
        valid_candles().drop(columns=["close"]),
        Market.HERAT,
        TimeFrame.M1,
    )

    assert report.quality_score == 0.0
    assert "missing required columns" in report.warnings[0]


def test_csv_watcher_publishes_valid_csv_update(tmp_path) -> None:
    market_dir = tmp_path / "xauusd"
    market_dir.mkdir()
    csv_path = market_dir / "1m.csv"
    valid_candles().to_csv(csv_path, index=False)
    bus = RecordingBus()
    watcher = CSVWatcher(base_data_dir=str(tmp_path), event_bus=bus)

    asyncio.run(watcher._check_all_files())

    assert len(bus.events) == 1
    event = bus.events[0]
    assert event.event_type is EventType.CSV_UPDATED
    assert event.payload["market"] == Market.XAUUSD.value
    assert event.payload["timeframe"] == TimeFrame.M1.value
    assert event.payload["row_count"] == 3


def test_csv_watcher_extracts_legacy_market_and_timeframe_names() -> None:
    watcher = CSVWatcher()
    path = watcher.base_dir / "abshodeNaghdi-60.csv"

    assert watcher._extract_market(path) is Market.ABSHODEH
    assert watcher._extract_timeframe(path) is TimeFrame.H1
