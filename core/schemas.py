"""Shared schemas for institutional market-data validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar


class Market(str, Enum):
    """Supported market identifiers used by the analysis pipeline."""

    ABSHODEH = "abshodeh"
    ABSHODE_NAGHDI = "abshodeNaghdi"
    HARAT = "harat"
    HARAT_FARDAYI = "haratFardayi"
    XAUUSD = "XAU_USD"


class TimeFrame(str, Enum):
    """Supported candle timeframes."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN1 = "1M"


@dataclass(frozen=True)
class CandleSchema:
    """Canonical OHLCV candle column names used by validators."""

    timestamp: str = "timestamp"
    open: str = "open"
    high: str = "high"
    low: str = "low"
    close: str = "close"
    volume: str = "volume"

    REQUIRED_COLUMNS: ClassVar[tuple[str, ...]] = ("timestamp", "open", "high", "low", "close")
    OPTIONAL_COLUMNS: ClassVar[tuple[str, ...]] = ("volume",)
    OHLCV_COLUMNS: ClassVar[tuple[str, ...]] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
    PRICE_COLUMNS: ClassVar[tuple[str, ...]] = ("open", "high", "low", "close")
    NUMERIC_COLUMNS: ClassVar[tuple[str, ...]] = PRICE_COLUMNS + OPTIONAL_COLUMNS


@dataclass(frozen=True)
class DataQualityReport:
    """Result emitted by the data quality engine for one market/timeframe."""

    timestamp: datetime
    market: Market
    timeframe: TimeFrame
    quality_score: float
    integrity_score: float
    warnings: list[str] = field(default_factory=list)
    missing_candles: int = 0
    duplicate_timestamps: int = 0
    outliers_detected: int = 0
    gaps_detected: int = 0
    corrupted_rows: int = 0
    invalid_ohlc_rows: int = 0
    volume_spikes: int = 0
