"""Core schema objects shared by market data validation components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Market(str, Enum):
    """Supported market identifiers for validation reports."""

    ABSHODEH = "abshodeh"
    ABSHODE_NAGHDI = "abshodeNaghdi"
    HARAT = "harat"
    HARAT_FARDAYI = "haratFardayi"
    XAU_USD = "XAU_USD"
    XAUUSD = "xauusd"


class TimeFrame(str, Enum):
    """Canonical candle timeframes used by the data quality engine."""

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
    """Column contract for OHLCV candle data."""

    timestamp: str = "timestamp"
    open: str = "open"
    high: str = "high"
    low: str = "low"
    close: str = "close"
    volume: str = "volume"

    @property
    def required_columns(self) -> tuple[str, ...]:
        """Return required OHLCV columns in canonical order."""
        return (self.timestamp, self.open, self.high, self.low, self.close, self.volume)

    @property
    def price_columns(self) -> tuple[str, ...]:
        """Return numeric price columns in canonical order."""
        return (self.open, self.high, self.low, self.close)


@dataclass(frozen=True)
class DataQualityReport:
    """Summary produced by the institutional data quality engine."""

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

    def as_dict(self) -> dict[str, Any]:
        """Serialize the report to plain Python types."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "market": self.market.value,
            "timeframe": self.timeframe.value,
            "quality_score": self.quality_score,
            "integrity_score": self.integrity_score,
            "warnings": list(self.warnings),
            "missing_candles": self.missing_candles,
            "duplicate_timestamps": self.duplicate_timestamps,
            "outliers_detected": self.outliers_detected,
            "gaps_detected": self.gaps_detected,
        }
