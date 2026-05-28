"""
Probabilistic institutional market state machine.

Determines the current market state and transition probabilities from already
closed OHLCV candles and optional liquidity context. The implementation keeps
all calculations backward-looking to avoid repainting and future data leakage.
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pandas as pd

from core.schemas import LiquidityMap, MarketState


class MarketStateMachine:
    """
    Identify the current institutional market state from OHLCV candles.

    The detector uses a bounded lookback window, validates required candle data,
    and can optionally incorporate a :class:`core.schemas.LiquidityMap` to
    recognize transfer-box behavior between sell-side support and buy-side
    resistance pools. Transitions are represented as normalized probability
    weights around the latest committed state.
    """

    REQUIRED_COLUMNS: ClassVar[tuple[str, ...]] = (
        "open",
        "high",
        "low",
        "close",
        "volume",
    )
    LOOKBACK: ClassVar[int] = 20

    # Format: {current_state: {next_state: probability_weight}}
    TRANSITION_WEIGHTS: ClassVar[dict[MarketState, dict[MarketState, float]]] = {
        MarketState.ACCUMULATION: {
            MarketState.ACCUMULATION: 0.40,
            MarketState.MANIPULATION: 0.20,
            MarketState.EXPANSION: 0.15,
            MarketState.TRANSFER_BOX: 0.10,
            MarketState.INVENTORY_LOADING: 0.10,
            MarketState.REVERSION: 0.05,
        },
        MarketState.DISTRIBUTION: {
            MarketState.DISTRIBUTION: 0.40,
            MarketState.MANIPULATION: 0.20,
            MarketState.EXPANSION: 0.10,
            MarketState.TRANSFER_BOX: 0.10,
            MarketState.INVENTORY_UNLOADING: 0.10,
            MarketState.REVERSION: 0.10,
        },
        MarketState.MANIPULATION: {
            MarketState.EXPANSION: 0.40,
            MarketState.DELIVERY_COMMIT: 0.20,
            MarketState.TRANSFER_BOX: 0.15,
            MarketState.REVERSION: 0.15,
            MarketState.PRE_DELIVERY: 0.10,
        },
        MarketState.EXPANSION: {
            MarketState.DELIVERY_COMMIT: 0.35,
            MarketState.REVERSION: 0.25,
            MarketState.DISTRIBUTION: 0.20,
            MarketState.ACCUMULATION: 0.10,
            MarketState.COMPRESSION: 0.10,
        },
        MarketState.DELIVERY_COMMIT: {
            MarketState.EXPANSION: 0.50,
            MarketState.REVERSION: 0.30,
            MarketState.DISTRIBUTION: 0.20,
        },
        MarketState.REVERSION: {
            MarketState.ACCUMULATION: 0.35,
            MarketState.DISTRIBUTION: 0.35,
            MarketState.COMPRESSION: 0.15,
            MarketState.TRANSFER_BOX: 0.15,
        },
        MarketState.COMPRESSION: {
            MarketState.EXPANSION: 0.50,
            MarketState.MANIPULATION: 0.30,
            MarketState.ACCUMULATION: 0.10,
            MarketState.DISTRIBUTION: 0.10,
        },
        MarketState.TRANSFER_BOX: {
            MarketState.EXPANSION: 0.30,
            MarketState.MANIPULATION: 0.25,
            MarketState.DELIVERY_COMMIT: 0.20,
            MarketState.ACCUMULATION: 0.15,
            MarketState.DISTRIBUTION: 0.10,
        },
        MarketState.INVENTORY_LOADING: {
            MarketState.PRE_DELIVERY: 0.30,
            MarketState.EXPANSION: 0.25,
            MarketState.ACCUMULATION: 0.25,
            MarketState.MANIPULATION: 0.20,
        },
        MarketState.INVENTORY_UNLOADING: {
            MarketState.PRE_DELIVERY: 0.30,
            MarketState.EXPANSION: 0.25,
            MarketState.DISTRIBUTION: 0.25,
            MarketState.MANIPULATION: 0.20,
        },
        MarketState.PRE_DELIVERY: {
            MarketState.DELIVERY_COMMIT: 0.50,
            MarketState.MANIPULATION: 0.20,
            MarketState.EXPANSION: 0.15,
            MarketState.REVERSION: 0.15,
        },
        MarketState.REPRICING: {
            MarketState.TRANSFER_BOX: 0.30,
            MarketState.ACCUMULATION: 0.25,
            MarketState.DISTRIBUTION: 0.25,
            MarketState.EXPANSION: 0.20,
        },
    }

    def __init__(self, initial_state: MarketState = MarketState.ACCUMULATION) -> None:
        self.current_state = initial_state
        self.last_volatility = 0.0
        self.last_range_ratio = 0.0

    def determine_state(
        self,
        candles: pd.DataFrame,
        liquidity: LiquidityMap | None = None,
        *,
        update: bool = False,
    ) -> MarketState:
        """
        Analyze recent candles and optional liquidity context to assign a state.

        Parameters
        ----------
        candles:
            DataFrame sorted by time with ``open``, ``high``, ``low``, ``close``
            and ``volume`` columns. Only the trailing closed candles are used.
        liquidity:
            Optional validated liquidity map containing buy-side and sell-side
            levels for transfer-box detection.
        update:
            When ``True``, persist the detected state as ``current_state``.
        """

        if candles.empty:
            return self.current_state

        self._validate_candles(candles)

        window = min(self.LOOKBACK, len(candles))
        recent = candles.iloc[-window:].copy()
        prev = candles.iloc[:-window]

        high = recent["high"]
        low = recent["low"]
        close = recent["close"]
        volume = recent["volume"]

        candle_range = high - low
        avg_range = float(candle_range.mean())
        avg_close = float(close.mean())
        body_size = (close - recent["open"]).abs().mean()
        range_ratio = float(body_size / avg_range) if avg_range > 0 else 0.0
        self.last_range_ratio = range_ratio

        normalized_range = candle_range / close.replace(0, np.nan)
        volatility = float(normalized_range.std(ddof=0)) if len(recent) > 1 else 0.0
        self.last_volatility = 0.0 if np.isnan(volatility) else volatility

        slope = self._close_slope(close)
        latest_volume_expanded = bool(volume.iloc[-1] > volume.mean())

        detected_state = self._detect_state(
            recent=recent,
            prev=prev,
            liquidity=liquidity,
            avg_range=avg_range,
            avg_close=avg_close,
            range_ratio=range_ratio,
            slope=slope,
            latest_volume_expanded=latest_volume_expanded,
        )

        if update:
            self.update_state(detected_state)
        return detected_state

    def transition_probabilities(self) -> dict[MarketState, float]:
        """Return a normalized next-state probability distribution."""

        weights = self.TRANSITION_WEIGHTS.get(self.current_state, {})
        total = sum(weights.values())
        if total <= 0:
            return {self.current_state: 1.0}
        return {state: weight / total for state, weight in weights.items()}

    def update_state(self, new_state: MarketState) -> None:
        """Persist the latest detected market state."""

        self.current_state = new_state

    def _detect_state(
        self,
        *,
        recent: pd.DataFrame,
        prev: pd.DataFrame,
        liquidity: LiquidityMap | None,
        avg_range: float,
        avg_close: float,
        range_ratio: float,
        slope: float,
        latest_volume_expanded: bool,
    ) -> MarketState:
        """Apply ordered institutional state-detection rules."""

        if avg_close <= 0:
            return self.current_state

        if self._is_manipulation(recent, prev):
            return MarketState.MANIPULATION

        if self._is_transfer_box(recent, liquidity):
            return MarketState.TRANSFER_BOX

        if self.last_volatility < 0.0005 and avg_range < avg_close * 0.005:
            return MarketState.COMPRESSION

        if self.last_volatility > 0.003 or avg_range > avg_close * 0.015:
            return MarketState.EXPANSION

        if (
            abs(slope) > avg_close * 0.005
            and self.last_volatility > 0.001
            and latest_volume_expanded
        ):
            return MarketState.DELIVERY_COMMIT

        if (
            self.current_state == MarketState.EXPANSION
            and abs(slope) < avg_close * 0.001
            and range_ratio < 0.30
        ):
            return MarketState.REVERSION

        if latest_volume_expanded:
            if slope > 0:
                return MarketState.ACCUMULATION
            if slope < 0:
                return MarketState.DISTRIBUTION

        return self.current_state

    def _is_transfer_box(
        self, recent: pd.DataFrame, liquidity: LiquidityMap | None
    ) -> bool:
        """Detect price rotating between sell-side support and buy-side resistance."""

        if (
            liquidity is None
            or not liquidity.buy_side_levels
            or not liquidity.sell_side_levels
        ):
            return False

        buy_side = min(level.price for level in liquidity.buy_side_levels)
        sell_side = max(level.price for level in liquidity.sell_side_levels)
        if buy_side <= sell_side:
            return False

        close = recent["close"]
        latest_close = float(close.iloc[-1])
        box_range = buy_side - sell_side
        if box_range <= 0 or not sell_side <= latest_close <= buy_side:
            return False

        recent_range = float(close.max() - close.min())
        is_rotating_inside_box = recent_range <= box_range * 0.80
        is_near_liquidity_edge = (
            min(latest_close - sell_side, buy_side - latest_close) <= box_range * 0.20
        )
        return bool(is_rotating_inside_box and is_near_liquidity_edge)

    def _is_manipulation(self, recent: pd.DataFrame, prev: pd.DataFrame) -> bool:
        """Detect a sweep beyond prior range followed by a close back inside."""

        if len(recent) < 2 or prev.empty:
            return False

        prev_high = float(prev["high"].max())
        prev_low = float(prev["low"].min())
        last_candle = recent.iloc[-1]

        swept_buy_side = (
            last_candle["high"] > prev_high and last_candle["close"] < prev_high
        )
        swept_sell_side = (
            last_candle["low"] < prev_low and last_candle["close"] > prev_low
        )
        return bool(swept_buy_side or swept_sell_side)

    def _close_slope(self, close: pd.Series) -> float:
        """Compute backward-looking linear close slope for the recent window."""

        if len(close) <= 1:
            return 0.0
        x_axis = np.arange(len(close), dtype=float)
        return float(np.polyfit(x_axis, close.to_numpy(dtype=float), 1)[0])

    def _validate_candles(self, candles: pd.DataFrame) -> None:
        """Validate required OHLCV columns and basic candle invariants."""

        missing = [
            column for column in self.REQUIRED_COLUMNS if column not in candles.columns
        ]
        if missing:
            raise ValueError(f"candles missing required columns: {missing}")

        values = candles.loc[:, self.REQUIRED_COLUMNS]
        if values.isna().any().any():
            raise ValueError("candles contain NaN values in required OHLCV columns")
        if not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(
                "candles contain non-finite values in required OHLCV columns"
            )
        if (candles["high"] < candles[["open", "close"]].max(axis=1)).any():
            raise ValueError("candle high must be >= open and close")
        if (candles["low"] > candles[["open", "close"]].min(axis=1)).any():
            raise ValueError("candle low must be <= open and close")
        if (candles["high"] < candles["low"]).any():
            raise ValueError("candle high must be >= low")
        if (candles["volume"] < 0).any():
            raise ValueError("candle volume must be non-negative")
