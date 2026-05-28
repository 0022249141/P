"""
Standardized Pydantic schemas for the Institutional Abshodeh Quant Terminal.

All data flowing through engines, pipelines, and APIs should conform to these
contracts. The schemas intentionally validate basic market-data invariants so
that downstream SMC/ICT, liquidity, regime, and delivery engines do not operate
on malformed snapshots.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# ENUMERATIONS — Institutional Ontology
# ---------------------------------------------------------------------------


class Market(str, Enum):
    ABSHODEH = "abshodeh"
    XAUUSD = "xauusd"
    HERAT = "herat"


class TimeFrame(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class LiquidityClass(str, Enum):
    CONSUMABLE = "consumable"  # نقدینگی مصرفی
    TRANSFER = "transfer"  # نقدینگی انتقالی
    DELIVERY = "delivery"  # نقدینگی تحویلی


class MarketState(str, Enum):
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    REPRICING = "repricing"
    TRANSFER_BOX = "transfer_box"
    INVENTORY_LOADING = "inventory_loading"
    INVENTORY_UNLOADING = "inventory_unloading"
    PRE_DELIVERY = "pre_delivery"
    DELIVERY_COMMIT = "delivery_commit"
    EXPANSION = "expansion"
    COMPRESSION = "compression"
    MANIPULATION = "manipulation"
    REVERSION = "reversion"


class DeliveryState(str, Enum):
    PRE_DELIVERY = "pre_delivery"
    INTERNAL_HARVEST = "internal_harvest"
    FALSE_COMMITMENT = "false_commitment"
    RECLAIM = "reclaim"
    DELIVERY_COMMIT = "delivery_commit"
    EXPANSION = "expansion"
    REVERSION = "reversion"


class DealerIntent(str, Enum):
    LOADING_LONG = "loading_long"
    LOADING_SHORT = "loading_short"
    UNLOADING_LONG = "unloading_long"
    UNLOADING_SHORT = "unloading_short"
    REBALANCING = "rebalancing"
    DISTRIBUTING = "distributing"
    ACCUMULATING = "accumulating"
    NEUTRAL = "neutral"


class RegimeType(str, Enum):
    LOW_VOL = "low_vol"
    HIGH_VOL = "high_vol"
    EXPANSION = "expansion"
    COMPRESSION = "compression"
    MANIPULATION = "manipulation"
    DISTRIBUTION = "distribution"
    ACCUMULATION = "accumulation"
    DELIVERY = "delivery"
    TRANSFER = "transfer"


class RiskGrade(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class EventType(str, Enum):
    CSV_UPDATED = "csv_updated"
    MARKET_STATE_CHANGED = "market_state_changed"
    LIQUIDITY_SWEEP_DETECTED = "liquidity_sweep_detected"
    DELIVERY_COMMIT_CONFIRMED = "delivery_commit_confirmed"
    REGIME_CHANGED = "regime_changed"
    SIGNAL_GENERATED = "signal_generated"
    NARRATIVE_UPDATED = "narrative_updated"


# ---------------------------------------------------------------------------
# BASE SCHEMAS — Core data units
# ---------------------------------------------------------------------------


class StrictSchema(BaseModel):
    """Base model that rejects unexpected payload keys."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CandleSchema(StrictSchema):
    """A single OHLCV candle for any market and timeframe."""

    timestamp: datetime
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: float = Field(0.0, ge=0)
    market: Market
    timeframe: TimeFrame

    @model_validator(mode="after")
    def validate_ohlc_range(self) -> "CandleSchema":
        """Ensure the candle body is contained within its wick range."""

        highest_body_price = max(self.open, self.close)
        lowest_body_price = min(self.open, self.close)
        if self.high < highest_body_price:
            raise ValueError("high must be >= both open and close")
        if self.low > lowest_body_price:
            raise ValueError("low must be <= both open and close")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        return self


class LiquidityLevel(StrictSchema):
    """A specific liquidity level (high/low) on the chart."""

    price: float = Field(..., ge=0)
    type: Literal["high", "low"]
    source: str = "swing"  # swing, session, engineered
    freshness: float = Field(0.0, ge=0.0, le=1.0)  # 1.0 = completely untouched
    importance_score: float = Field(0.0, ge=0.0, le=1.0)
    sweep_probability: float = Field(0.0, ge=0.0, le=1.0)
    delivery_probability: float = Field(0.0, ge=0.0, le=1.0)
    liquidity_class: LiquidityClass


class LiquidityMap(StrictSchema):
    """Complete liquidity analysis for a market snapshot."""

    market: Market
    timeframe: TimeFrame
    timestamp: datetime
    buy_side_levels: list[LiquidityLevel] = Field(default_factory=list)
    sell_side_levels: list[LiquidityLevel] = Field(default_factory=list)
    nearest_consumable_buy: float | None = Field(default=None, ge=0)
    nearest_consumable_sell: float | None = Field(default=None, ge=0)
    engineered_liquidity_zones: list[float] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ENGINE OUTPUT SCHEMAS — Dealer, Delivery, Probability
# ---------------------------------------------------------------------------


class DealerInventoryState(StrictSchema):
    """Output of Dealer Inventory Engine."""

    timestamp: datetime
    market: Market
    inventory_state: MarketState
    dealer_intent: DealerIntent
    inventory_bias: Literal["bullish", "bearish", "neutral"]
    transfer_phase: str | None = None  # e.g., "box_formation", "transfer_in_progress"
    commitment_state: Literal["committed", "uncommitted"] | None = None
    accumulation_score: float = Field(0.0, ge=0.0, le=1.0)
    distribution_score: float = Field(0.0, ge=0.0, le=1.0)
    imbalance_ratio: float | None = None  # positive = long imbalance, negative = short
    absorption_detected: bool = False


class MarketDeliveryState(StrictSchema):
    """Output of Market Delivery Engine."""

    timestamp: datetime
    market: Market
    delivery_state: DeliveryState
    internal_liquidity_swept: bool = False
    external_target_identified: bool = False
    inducement_detected: bool = False
    continuation_probability: float = Field(0.0, ge=0.0, le=1.0)
    displacement_confirmed: bool = False
    reclaim_triggered: bool = False


class ProbabilitySnapshot(StrictSchema):
    """Output of Probability Engine."""

    timestamp: datetime
    market: Market
    delivery_probability: float = Field(0.0, ge=0.0, le=1.0)
    sweep_probability: float = Field(0.0, ge=0.0, le=1.0)
    continuation_probability: float = Field(0.0, ge=0.0, le=1.0)
    reversal_probability: float = Field(0.0, ge=0.0, le=1.0)
    manipulation_probability: float = Field(0.0, ge=0.0, le=1.0)
    commitment_probability: float = Field(0.0, ge=0.0, le=1.0)
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    uncertainty_score: float = Field(0.0, ge=0.0, le=1.0)
    expected_path: str = "continuation"


class RegimeSnapshot(StrictSchema):
    """Output of Regime Engine."""

    timestamp: datetime
    market: Market
    regime: RegimeType
    volatility_percentile: float | None = Field(default=None, ge=0.0, le=1.0)
    manipulation_index: float = Field(0.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# SESSION & CROSS-MARKET SCHEMAS
# ---------------------------------------------------------------------------


class TehranSessionInfo(StrictSchema):
    """Tehran session specific analysis."""

    timestamp: datetime
    is_tehran_open: bool = False
    is_friday: bool = False
    holiday_effect: bool = False
    pm_manipulation_likely: bool = False
    herat_correlation: float | None = Field(default=None, ge=-1.0, le=1.0)
    local_volatility_spike: bool = False
    spread_distortion_detected: bool = False


class CrossMarketSyncState(StrictSchema):
    """Output of Cross-Market Synchronization Engine."""

    timestamp: datetime
    dominant_market: Market
    transfer_direction: str = "neutral"  # "abshodeh_leading", "herat_leading", etc.
    divergence_score: float = Field(0.0, ge=0.0, le=1.0)
    synchronization_state: Literal["aligned", "divergent", "lagging"]
    smt_divergence_detected: bool = False


# ---------------------------------------------------------------------------
# SIGNAL & NARRATIVE
# ---------------------------------------------------------------------------


class InstitutionalSignal(StrictSchema):
    """Complete institutional signal (output of Signal Engine)."""

    id: str
    timestamp: datetime
    market: Market
    direction: SignalDirection
    entry_price: float = Field(..., ge=0)
    invalidation_price: float = Field(..., ge=0)
    liquidity_target: float | None = Field(default=None, ge=0)
    delivery_target: float | None = Field(default=None, ge=0)
    probability: float = Field(0.0, ge=0.0, le=1.0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    regime: RegimeType
    dealer_narrative: str | None = None
    inventory_state: MarketState
    session_context: str = "tehran"
    risk_grade: RiskGrade
    execution_timing: str = "immediate"  # immediate, wait_for_retest, etc.
    expected_sequence: list[str] = Field(default_factory=list)


class Narrative(StrictSchema):
    """Full institutional narrative in two languages."""

    id: str
    timestamp: datetime
    market: Market
    english_text: str
    persian_text: str
    consumed_liquidity: str | None = None
    remaining_liquidity: str | None = None
    invalidation_condition: str | None = None
    commitment_status: str | None = None


# ---------------------------------------------------------------------------
# EVENT BUS & SYSTEM HEALTH
# ---------------------------------------------------------------------------


class SystemEvent(StrictSchema):
    """Event dispatched on the internal event bus."""

    event_id: str
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_engine: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EngineHealth(StrictSchema):
    """Health status of a single engine."""

    engine_name: str
    status: Literal["healthy", "stale", "failed"]
    last_execution: datetime | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    error_message: str | None = None


class DataQualityReport(StrictSchema):
    """Output of Data Quality Engine."""

    timestamp: datetime
    market: Market
    timeframe: TimeFrame
    quality_score: float = Field(0.0, ge=0.0, le=1.0)
    integrity_score: float = Field(0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    missing_candles: int = Field(0, ge=0)
    duplicate_timestamps: int = Field(0, ge=0)
    outliers_detected: int = Field(0, ge=0)
    gaps_detected: int = Field(0, ge=0)
