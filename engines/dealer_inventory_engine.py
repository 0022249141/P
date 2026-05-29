"""
engines/dealer_inventory_engine.py
Infers dealer-inventory-like behavior from observable OHLCV/liquidity proxies.
It does not observe real dealer inventory.
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
from core.schemas import Bias, CommitmentState, DealerIntent, DealerInventoryState, LiquidityMap, Market, MarketState, TimeFrame


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


class DealerInventoryEngine:
    def __init__(self, lookback: int = 50, minimum_required: int = 20):
        self.lookback = max(20, int(lookback))
        self.minimum_required = max(10, int(minimum_required))

    def evaluate(self, candles: pd.DataFrame, liquidity: Optional[LiquidityMap] = None, current_market_state: MarketState = MarketState.ACCUMULATION, market: Market = Market.ABSHODEH, timeframe: TimeFrame = TimeFrame.H1) -> DealerInventoryState:
        if candles is None or candles.empty or not {"open", "high", "low", "close"}.issubset(candles.columns):
            return self._neutral(market, current_market_state)
        df = candles.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
        if len(df) < self.minimum_required:
            return self._neutral(market, current_market_state)
        recent = df.iloc[-min(self.lookback, len(df)):].copy()
        high, low, close, open_ = recent["high"], recent["low"], recent["close"], recent["open"]
        rng = (high - low).abs().replace(0, np.nan)
        volume = self._volume(recent)
        volume_reliable = self._volume_reliable(volume)

        close_ret = close.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0)
        if volume_reliable:
            weights = volume / max(float(volume.sum()), 1e-9)
            pressure = float((close_ret * weights).sum())
        else:
            pressure = float(close_ret.mean())
        imbalance_ratio = _clamp(pressure * 100, -1.0, 1.0)
        bias = Bias.BULLISH if imbalance_ratio > 0.03 else Bias.BEARISH if imbalance_ratio < -0.03 else Bias.NEUTRAL

        body = (close - open_).abs()
        body_ratio = (body / rng).replace([np.inf, -np.inf], np.nan).fillna(0)
        if volume_reliable:
            vol_threshold = volume.mean() + 1.5 * volume.std()
            absorption_candles = (volume > vol_threshold) & (body_ratio < body_ratio.median())
        else:
            wick_ratio = 1.0 - body_ratio.clip(0, 1)
            absorption_candles = wick_ratio > wick_ratio.quantile(0.7)
        absorption_score = _clamp(absorption_candles.mean() * 2.5)

        denom = rng.replace(0, np.nan)
        clv = (((close - low) - (high - close)) / denom).replace([np.inf, -np.inf], np.nan).fillna(0)
        ad_line = (clv * (volume if volume_reliable else 1.0)).cumsum()
        ad_slope_norm = float((ad_line.iloc[-1] - ad_line.iloc[0]) / max(float(abs(ad_line).std() or 1.0), 1e-9) / len(ad_line))
        accumulation_score = _clamp(0.5 + ad_slope_norm + (0.15 if bias == Bias.BULLISH else -0.05))
        distribution_score = _clamp(1.0 - accumulation_score)
        dealer_intent = self._infer_dealer_intent(bias, absorption_score, current_market_state, accumulation_score, distribution_score)
        transfer_phase = self._detect_transfer_phase(recent, liquidity)
        commitment_state = self._commitment_state(recent, current_market_state)

        return DealerInventoryState(
            timestamp=self._timestamp(recent), market=market, inventory_state=current_market_state,
            dealer_intent=dealer_intent, inventory_bias=bias, transfer_phase=transfer_phase,
            commitment_state=commitment_state, accumulation_score=accumulation_score,
            distribution_score=distribution_score, imbalance_ratio=imbalance_ratio,
            absorption_detected=absorption_score > 0.35,
        )

    def _neutral(self, market: Market, state: MarketState) -> DealerInventoryState:
        return DealerInventoryState(timestamp=pd.Timestamp.utcnow().to_pydatetime(), market=market, inventory_state=state, dealer_intent=DealerIntent.NEUTRAL, inventory_bias=Bias.NEUTRAL, commitment_state=CommitmentState.UNCOMMITTED)

    def _timestamp(self, df: pd.DataFrame):
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"].iloc[-1], errors="coerce")
            if pd.notna(ts):
                return ts.to_pydatetime()
        return pd.Timestamp.utcnow().to_pydatetime()

    def _volume(self, df: pd.DataFrame) -> pd.Series:
        return pd.to_numeric(df["volume"], errors="coerce").fillna(0) if "volume" in df.columns else pd.Series(1.0, index=df.index)

    def _volume_reliable(self, volume: pd.Series) -> bool:
        return bool(len(volume) > 3 and volume.sum() > 0 and volume.std() > 0 and volume.notna().mean() > 0.8)

    def _infer_dealer_intent(self, bias: Bias, absorption_score: float, market_state: MarketState, acc: float, dist: float) -> DealerIntent:
        if market_state == MarketState.ACCUMULATION and acc > 0.55:
            return DealerIntent.ACCUMULATING
        if market_state == MarketState.DISTRIBUTION and dist > 0.55:
            return DealerIntent.DISTRIBUTING
        if market_state == MarketState.REVERSION:
            return DealerIntent.REBALANCING
        if absorption_score > 0.55:
            return DealerIntent.REBALANCING
        if bias == Bias.BULLISH and market_state in {MarketState.PRE_DELIVERY, MarketState.TRANSFER_BOX}:
            return DealerIntent.LOADING_LONG
        if bias == Bias.BEARISH and market_state in {MarketState.PRE_DELIVERY, MarketState.TRANSFER_BOX}:
            return DealerIntent.LOADING_SHORT
        return DealerIntent.NEUTRAL

    def _detect_transfer_phase(self, candles: pd.DataFrame, liquidity: Optional[LiquidityMap]) -> Optional[str]:
        if not liquidity:
            return None
        current = float(candles["close"].iloc[-1])
        upper = min([l.price for l in liquidity.buy_side_levels if l.price > current], default=None)
        lower = max([l.price for l in liquidity.sell_side_levels if l.price < current], default=None)
        if upper is None or lower is None or upper <= lower:
            return None
        pos = (current - lower) / (upper - lower)
        if 0.2 < pos < 0.8:
            return "transfer_in_progress"
        return "box_accumulation" if pos <= 0.2 else "box_distribution"

    def _commitment_state(self, candles: pd.DataFrame, state: MarketState) -> CommitmentState:
        if state == MarketState.DELIVERY_COMMIT:
            return CommitmentState.COMMITTED
        if state == MarketState.PRE_DELIVERY:
            return CommitmentState.PENDING
        if len(candles) >= 10:
            recent = candles.iloc[-10:]
            net = abs(float(recent["close"].iloc[-1] - recent["open"].iloc[0])) / max(abs(float(recent["open"].iloc[0])), 1e-9)
            avg_range = float(((recent["high"] - recent["low"]).abs() / recent["close"].replace(0, np.nan)).mean() or 0)
            if net > max(0.006, avg_range * 2.0):
                return CommitmentState.COMMITTED
        return CommitmentState.UNCOMMITTED
