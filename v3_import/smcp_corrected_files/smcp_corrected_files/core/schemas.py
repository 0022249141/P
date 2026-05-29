"""
core/schemas.py
Standardized Pydantic schemas for the Institutional Abshodeh Quant Terminal.
All engine and pipeline outputs should conform to these contracts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Market(str, Enum):
    ABSHODEH = "abshodeh"
    XAUUSD = "xauusd"
    HERAT = "herat"


class TimeFrame(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN1 = "1M"


class LiquidityClass(str, Enum):
    CONSUMABLE = "consumable"
    TRANSFER = "transfer"
    DELIVERY = "delivery"


class LiquiditySide(str, Enum):
    BUY_SIDE = "buy_side"
    SELL_SIDE = "sell_side"


class LiquiditySource(str, Enum):
    SWING = "swing"
    SESSION = "session"
    ENGINEERED = "engineered"
    EQUAL_HIGH_LOW = "equal_high_low"
    PREVIOUS_DAY = "previous_day"
    PREVIOUS_WEEK = "previous_week"


class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class CommitmentState(str, Enum):
    COMMITTED = "committed"
    UNCOMMITTED = "uncommitted"
    PENDING = "pending"
    FAILED = "failed"


class ExecutionTiming(str, Enum):
    IMMEDIATE = "immediate"
    WAIT_FOR_RETEST = "wait_for_retest"
    WAIT_FOR_CONFIRMATION = "wait_for_confirmation"
    NO_TRADE = "no_trade"


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


class _BaseModel(BaseModel):
    model_config = ConfigDict(use_enum_values=False, arbitrary_types_allowed=True)


class CandleSchema(_BaseModel):
    """A single OHLCV candle for any market/timeframe."""
    timestamp: datetime
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: float = Field(0.0, ge=0)
    market: Market
    timeframe: TimeFrame

    @model_validator(mode="after")
    def validate_ohlc(self) -> "CandleSchema":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open, close, and high")
        return self


class LiquidityLevel(_BaseModel):
    """A mapped liquidity level. `type` is kept for backward compatibility: high/low."""
    price: float
    type: str  # backward-compatible: "high" or "low"
    source: LiquiditySource | str = LiquiditySource.SWING
    freshness: float = Field(0.0, ge=0.0, le=1.0)
    importance_score: float = Field(0.0, ge=0.0, le=1.0)
    sweep_probability: float = Field(0.0, ge=0.0, le=1.0)
    delivery_probability: float = Field(0.0, ge=0.0, le=1.0)
    liquidity_class: LiquidityClass
    side: Optional[LiquiditySide | str] = None
    engineered_likelihood: float = Field(0.0, ge=0.0, le=1.0)


class LiquidityMap(_BaseModel):
    market: Market
    timeframe: TimeFrame
    timestamp: datetime
    buy_side_levels: List[LiquidityLevel] = Field(default_factory=list)
    sell_side_levels: List[LiquidityLevel] = Field(default_factory=list)
    nearest_consumable_buy: Optional[float] = None
    nearest_consumable_sell: Optional[float] = None
    engineered_liquidity_zones: List[float] = Field(default_factory=list)


class DealerInventoryState(_BaseModel):
    """Inferred dealer-inventory-like state. Real dealer inventory is not directly observed."""
    timestamp: datetime
    market: Market
    inventory_state: MarketState
    dealer_intent: DealerIntent
    inventory_bias: Bias | str = Bias.NEUTRAL
    transfer_phase: Optional[str] = None
    commitment_state: CommitmentState | str | None = CommitmentState.UNCOMMITTED
    accumulation_score: float = Field(0.0, ge=0.0, le=1.0)
    distribution_score: float = Field(0.0, ge=0.0, le=1.0)
    imbalance_ratio: Optional[float] = None
    absorption_detected: bool = False


class MarketDeliveryState(_BaseModel):
    timestamp: datetime
    market: Market
    delivery_state: DeliveryState
    internal_liquidity_swept: bool = False
    external_target_identified: bool = False
    inducement_detected: bool = False
    continuation_probability: float = Field(0.0, ge=0.0, le=1.0)
    displacement_confirmed: bool = False
    reclaim_triggered: bool = False


class ProbabilitySnapshot(_BaseModel):
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
    expected_path: str = "unresolved"


class RegimeSnapshot(_BaseModel):
    timestamp: datetime
    market: Market
    regime: RegimeType
    volatility_percentile: Optional[float] = Field(None, ge=0.0, le=1.0)
    manipulation_index: float = Field(0.0, ge=0.0, le=1.0)


class TehranSessionInfo(_BaseModel):
    timestamp: datetime
    is_tehran_open: bool = False
    is_friday: bool = False
    holiday_effect: bool = False
    pm_manipulation_likely: bool = False
    herat_correlation: Optional[float] = None
    local_volatility_spike: bool = False
    spread_distortion_detected: bool = False


class CrossMarketSyncState(_BaseModel):
    timestamp: datetime
    dominant_market: Market
    transfer_direction: str = "neutral"
    divergence_score: float = Field(0.0, ge=0.0, le=1.0)
    synchronization_state: str
    smt_divergence_detected: bool = False


class InstitutionalSignal(_BaseModel):
    id: str
    timestamp: datetime
    market: Market
    direction: SignalDirection
    entry_price: float = Field(..., ge=0)
    invalidation_price: float = Field(..., ge=0)
    liquidity_target: Optional[float] = None
    delivery_target: Optional[float] = None
    probability: float = Field(0.0, ge=0.0, le=1.0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    regime: RegimeType
    dealer_narrative: Optional[str] = None
    inventory_state: MarketState
    session_context: str = "tehran"
    risk_grade: RiskGrade
    execution_timing: ExecutionTiming | str = ExecutionTiming.NO_TRADE
    expected_sequence: List[str] = Field(default_factory=list)


class Narrative(_BaseModel):
    id: str
    timestamp: datetime
    market: Market
    english_text: str
    persian_text: str
    consumed_liquidity: Optional[str] = None
    remaining_liquidity: Optional[str] = None
    invalidation_condition: Optional[str] = None
    commitment_status: Optional[str] = None


class SystemEvent(_BaseModel):
    event_id: str
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_engine: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class EngineHealth(_BaseModel):
    engine_name: str
    status: str
    last_execution: Optional[datetime] = None
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None


class DataQualityReport(_BaseModel):
    timestamp: datetime
    market: Market
    timeframe: TimeFrame
    quality_score: float = Field(0.0, ge=0.0, le=1.0)
    integrity_score: float = Field(0.0, ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)
    missing_candles: int = 0
    duplicate_timestamps: int = 0
    outliers_detected: int = 0
    gaps_detected: int = 0
