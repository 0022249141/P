"""
engines/market_state_machine.py
Probabilistic institutional market state machine.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from core.schemas import LiquidityClass, LiquidityMap, MarketState


class MarketStateMachine:
    TRANSITION_WEIGHTS: Dict[MarketState, Dict[MarketState, float]] = {
        MarketState.ACCUMULATION: {
            MarketState.ACCUMULATION: 0.4,
            MarketState.MANIPULATION: 0.2,
            MarketState.EXPANSION: 0.15,
            MarketState.TRANSFER_BOX: 0.1,
            MarketState.INVENTORY_LOADING: 0.1,
            MarketState.REVERSION: 0.05,
        },
        MarketState.MANIPULATION: {
            MarketState.EXPANSION: 0.4,
            MarketState.DELIVERY_COMMIT: 0.2,
            MarketState.TRANSFER_BOX: 0.1,
            MarketState.REVERSION: 0.2,
            MarketState.PRE_DELIVERY: 0.1,
        },
        MarketState.EXPANSION: {
            MarketState.DELIVERY_COMMIT: 0.3,
            MarketState.REVERSION: 0.25,
            MarketState.DISTRIBUTION: 0.15,
            MarketState.ACCUMULATION: 0.15,
            MarketState.COMPRESSION: 0.15,
        },
        MarketState.COMPRESSION: {
            MarketState.EXPANSION: 0.45,
            MarketState.MANIPULATION: 0.3,
            MarketState.ACCUMULATION: 0.125,
            MarketState.DISTRIBUTION: 0.125,
        },
    }

    def __init__(self, initial_state: MarketState = MarketState.ACCUMULATION) -> None:
        self.current_state = initial_state
        self.last_volatility = 0.0
        self.last_range_ratio = 0.0

    def determine_state(
        self,
        candles: pd.DataFrame,
        liquidity: Optional[LiquidityMap] = None,
        update: bool = False,
    ) -> MarketState:
        if candles is None or candles.empty:
            return self.current_state

        required = {"open", "high", "low", "close", "volume"}
        missing = required.difference(candles.columns)
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")

        df = candles.copy()
        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=list(required))

        if len(df) < 5:
            return self.current_state

        if df["close"].nunique(dropna=True) == 1:
            state = MarketState.COMPRESSION
            if update:
                self.current_state = state
            return state

        if self._has_two_sided_transfer_liquidity(liquidity):
            state = MarketState.TRANSFER_BOX
            if update:
                self.current_state = state
            return state

        if self._is_manipulation(df):
            state = MarketState.MANIPULATION
            if update:
                self.current_state = state
            return state

        window = min(20, len(df))
        recent = df.iloc[-window:]

        high = recent["high"]
        low = recent["low"]
        close = recent["close"]
        open_ = recent["open"]

        rng = (high - low).abs().replace(0, np.nan)
        range_pct = ((high - low).abs() / close.replace(0, np.nan)).replace(
            [np.inf, -np.inf], np.nan
        )

        vol = float(range_pct.std(skipna=True) or 0.0)
        self.last_volatility = vol

        body_ratio = ((close - open_).abs() / rng).replace(
            [np.inf, -np.inf], np.nan
        ).fillna(0)
        self.last_range_ratio = float(body_ratio.mean())

        x = np.arange(len(close), dtype=float)
        slope = (
            float(np.polyfit(x, close.to_numpy(dtype=float), 1)[0])
            if len(close) > 1
            else 0.0
        )
        normalized_slope = slope / max(abs(float(close.mean())), 1e-9)

        avg_range_pct = float(range_pct.mean(skipna=True) or 0.0)

        if avg_range_pct < 0.003 and self.last_range_ratio < 0.45:
            state = MarketState.COMPRESSION
        elif avg_range_pct > 0.012 or vol > 0.006:
            state = MarketState.EXPANSION
        elif normalized_slope > 0 and self.last_range_ratio < 0.55:
            state = MarketState.ACCUMULATION
        elif normalized_slope < 0 and self.last_range_ratio < 0.55:
            state = MarketState.DISTRIBUTION
        else:
            state = self.current_state

        if update:
            self.current_state = state

        return state

    def transition_probabilities(self) -> Dict[MarketState, float]:
        weights = self.TRANSITION_WEIGHTS.get(
            self.current_state, {self.current_state: 1.0}
        )
        total = sum(max(0.0, float(w)) for w in weights.values())
        if total == 0:
            return {self.current_state: 1.0}
        return {state: max(0.0, float(weight)) / total for state, weight in weights.items()}

    def _is_manipulation(self, df: pd.DataFrame) -> bool:
        if len(df) < 2:
            return False

        prior = df.iloc[:-1]
        last = df.iloc[-1]

        prior_high = float(prior["high"].max())
        prior_low = float(prior["low"].min())

        last_high = float(last["high"])
        last_low = float(last["low"])
        last_close = float(last["close"])

        swept_high_and_reclaimed = last_high > prior_high and last_close <= prior_high
        swept_low_and_reclaimed = last_low < prior_low and last_close >= prior_low

        return swept_high_and_reclaimed or swept_low_and_reclaimed

    def _has_two_sided_transfer_liquidity(
        self, liquidity: Optional[LiquidityMap]
    ) -> bool:
        if liquidity is None:
            return False

        transfer_buy = any(
            level.liquidity_class == LiquidityClass.TRANSFER
            for level in liquidity.buy_side_levels
        )
        transfer_sell = any(
            level.liquidity_class == LiquidityClass.TRANSFER
            for level in liquidity.sell_side_levels
        )

        return transfer_buy and transfer_sell