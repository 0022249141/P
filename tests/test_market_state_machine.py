from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from core.schemas import (
    LiquidityClass,
    LiquidityLevel,
    LiquidityMap,
    Market,
    MarketState,
    TimeFrame,
)
from engines.market_state_machine import MarketStateMachine


def candles_from_closes(closes: list[float], *, volume: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": [price + 0.2 for price in closes],
            "low": [price - 0.2 for price in closes],
            "close": closes,
            "volume": [volume] * len(closes),
        }
    )


def test_determine_state_validates_required_ohlcv_columns() -> None:
    machine = MarketStateMachine()

    with pytest.raises(ValueError, match="missing required columns"):
        machine.determine_state(pd.DataFrame({"close": [100.0]}))


def test_detects_manipulation_from_prior_range_sweep_without_future_data() -> None:
    machine = MarketStateMachine()
    candles = candles_from_closes([100.0] * 20)
    candles.loc[20] = {
        "open": 100.1,
        "high": 102.0,
        "low": 99.8,
        "close": 100.1,
        "volume": 150.0,
    }

    assert machine.determine_state(candles) is MarketState.MANIPULATION


def test_detects_transfer_box_with_schema_liquidity_prices() -> None:
    machine = MarketStateMachine()
    candles = candles_from_closes([100.0, 100.2, 100.1, 100.4, 100.3])
    liquidity = LiquidityMap(
        market=Market.XAUUSD,
        timeframe=TimeFrame.M5,
        timestamp=datetime.now(timezone.utc),
        buy_side_levels=[
            LiquidityLevel(
                price=102.0, type="high", liquidity_class=LiquidityClass.TRANSFER
            ),
        ],
        sell_side_levels=[
            LiquidityLevel(
                price=100.0, type="low", liquidity_class=LiquidityClass.TRANSFER
            ),
        ],
    )

    assert machine.determine_state(candles, liquidity) is MarketState.TRANSFER_BOX


def test_transition_probabilities_are_normalized_for_current_state() -> None:
    machine = MarketStateMachine(MarketState.MANIPULATION)

    probabilities = machine.transition_probabilities()

    assert probabilities[MarketState.EXPANSION] == pytest.approx(0.40)
    assert sum(probabilities.values()) == pytest.approx(1.0)


def test_update_option_persists_detected_state() -> None:
    machine = MarketStateMachine()
    candles = candles_from_closes([100.0] * 6)

    state = machine.determine_state(candles, update=True)

    assert state is MarketState.COMPRESSION
    assert machine.current_state is MarketState.COMPRESSION
