from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import (
    CandleSchema,
    DataQualityReport,
    EventType,
    InstitutionalSignal,
    LiquidityClass,
    LiquidityLevel,
    LiquidityMap,
    Market,
    MarketState,
    RegimeType,
    RiskGrade,
    SignalDirection,
    SystemEvent,
    TimeFrame,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_candle_schema_accepts_valid_ohlcv_payload() -> None:
    candle = CandleSchema(
        timestamp=utc_now(),
        open=100.0,
        high=105.0,
        low=98.0,
        close=103.0,
        volume=250.0,
        market=Market.ABSHODEH,
        timeframe=TimeFrame.M5,
    )

    assert candle.high == 105.0
    assert candle.market is Market.ABSHODEH


@pytest.mark.parametrize(
    "payload_update",
    [
        {"high": 99.0, "close": 101.0},
        {"low": 101.0, "close": 99.0},
        {"volume": -1.0},
    ],
)
def test_candle_schema_rejects_invalid_ohlcv_payloads(payload_update: dict[str, float]) -> None:
    payload = {
        "timestamp": utc_now(),
        "open": 100.0,
        "high": 102.0,
        "low": 98.0,
        "close": 101.0,
        "volume": 0.0,
        "market": Market.XAUUSD,
        "timeframe": TimeFrame.M1,
    }
    payload.update(payload_update)

    with pytest.raises(ValidationError):
        CandleSchema(**payload)


def test_liquidity_level_rejects_out_of_range_probabilities() -> None:
    with pytest.raises(ValidationError):
        LiquidityLevel(
            price=2450.0,
            type="high",
            sweep_probability=1.2,
            liquidity_class=LiquidityClass.CONSUMABLE,
        )


def test_collection_defaults_are_not_shared_between_models() -> None:
    first = LiquidityMap(market=Market.HERAT, timeframe=TimeFrame.H1, timestamp=utc_now())
    second = LiquidityMap(market=Market.HERAT, timeframe=TimeFrame.H1, timestamp=utc_now())

    first.engineered_liquidity_zones.append(1.0)

    assert second.engineered_liquidity_zones == []


def test_signal_and_quality_report_validate_probability_and_count_ranges() -> None:
    signal = InstitutionalSignal(
        id="sig-1",
        timestamp=utc_now(),
        market=Market.ABSHODEH,
        direction=SignalDirection.LONG,
        entry_price=100.0,
        invalidation_price=95.0,
        probability=0.7,
        confidence=0.8,
        regime=RegimeType.DELIVERY,
        inventory_state=MarketState.DELIVERY_COMMIT,
        risk_grade=RiskGrade.MEDIUM,
    )

    assert signal.expected_sequence == []

    with pytest.raises(ValidationError):
        DataQualityReport(
            timestamp=utc_now(),
            market=Market.ABSHODEH,
            timeframe=TimeFrame.M15,
            quality_score=1.1,
            duplicate_timestamps=-1,
        )


def test_system_event_uses_timezone_aware_default_timestamp_and_distinct_payloads() -> None:
    first = SystemEvent(
        event_id="evt-1",
        event_type=EventType.CSV_UPDATED,
        source_engine="test",
    )
    second = SystemEvent(
        event_id="evt-2",
        event_type=EventType.REGIME_CHANGED,
        source_engine="test",
    )

    first.payload["market"] = Market.ABSHODEH.value

    assert first.timestamp.tzinfo is not None
    assert second.payload == {}
