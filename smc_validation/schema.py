"""Shared schema constants for the validation framework."""

from __future__ import annotations

from enum import Enum


class Regime(str, Enum):
    """Canonical market regimes used by the report contract."""

    LOW_VOL = "LOW_VOL"
    NORMAL = "NORMAL"
    HIGH_VOL = "HIGH_VOL"
    MANIPULATION = "MANIPULATION"


CANONICAL_REGIMES = tuple(regime.value for regime in Regime)

LONG_ALIASES = {"long", "buy", "bull", "bullish", "1", "up"}
SHORT_ALIASES = {"short", "sell", "bear", "bearish", "-1", "down"}
EXECUTE_ALIASES = {"execute", "executed", "true", "1", "yes", "buy", "sell", "long", "short"}

REQUIRED_OHLCV_COLUMNS = ("timestamp", "open", "high", "low", "close")
REQUIRED_SIGNAL_COLUMNS = ("timestamp", "direction")
