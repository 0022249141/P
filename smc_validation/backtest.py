"""Deterministic historical replay backtester for multi-market SMC signals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .metrics import equity_curve, performance_summary, regime_performance
from .schema import CANONICAL_REGIMES, EXECUTE_ALIASES, LONG_ALIASES, REQUIRED_OHLCV_COLUMNS, REQUIRED_SIGNAL_COLUMNS, SHORT_ALIASES


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration for deterministic replay.

    Risk is measured in R-multiples, so portfolio sizing is intentionally kept out
    of the replay loop.  This makes strategy validation comparable across markets.
    """

    max_holding_candles: int = 96
    min_ev: float = 0.0
    atr_stop_multiple: float = 1.0
    atr_take_profit_multiple: float = 2.0
    conservative_same_candle: bool = True
    allow_overlapping_by_market: bool = False
    entry_price_column: str = "entry_price"
    take_profit_column: str = "tp_price"
    stop_loss_column: str = "sl_price"
    expected_value_column: str = "expected_R"
    decision_column: str = "decision"
    regime_column: str = "regime"
    atr_column: str = "atr"
    market_column: str = "market"
    timestamp_column: str = "timestamp"
    timeframe_tolerance: str | pd.Timedelta | None = None
    random_signal_delay_candles: tuple[int, int] | None = None
    seed: int = 42


@dataclass
class BacktestResult:
    """Container for replay artifacts."""

    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    backtest_summary: dict[str, Any]
    regime_performance: dict[str, dict[str, Any]]

    def to_json_dict(self) -> dict[str, Any]:
        """Return the backtest-only report payload."""

        return {
            "backtest_summary": self.backtest_summary,
            "regime_performance": self.regime_performance,
            "equity_curve": self.equity_curve.to_dict(orient="records"),
        }


class BacktestEngine:
    """Replay historical candles against EV-filtered execution signals.

    The engine does not fit parameters, predict outcomes, or use machine learning.
    Signals are replayed in timestamp order and exits are decided only from future
    OHLC candles available after each signal timestamp.
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()
        self._rng = np.random.default_rng(self.config.seed)

    def run_from_csv(
        self,
        market_csvs: Mapping[str, str | Path],
        signals_csv: str | Path,
        higher_timeframe_csvs: Mapping[str, str | Path] | None = None,
    ) -> BacktestResult:
        """Load historical market data and generated signals from CSV files."""

        market_data = {market: pd.read_csv(path) for market, path in market_csvs.items()}
        signals = pd.read_csv(signals_csv)
        higher_timeframes = {name: pd.read_csv(path) for name, path in (higher_timeframe_csvs or {}).items()}
        return self.run(market_data=market_data, signals=signals, higher_timeframes=higher_timeframes)

    def run(
        self,
        market_data: Mapping[str, pd.DataFrame] | pd.DataFrame,
        signals: pd.DataFrame,
        higher_timeframes: Mapping[str, pd.DataFrame] | None = None,
    ) -> BacktestResult:
        """Run deterministic replay on prepared data frames."""

        markets = self._prepare_market_data(market_data)
        prepared_signals = self._prepare_signals(signals)
        if higher_timeframes:
            prepared_signals = self.align_higher_timeframes(prepared_signals, higher_timeframes)

        trades: list[dict[str, Any]] = []
        blocked_until: dict[str, pd.Timestamp] = {}
        for signal in prepared_signals.sort_values("timestamp").itertuples(index=False):
            market = signal.market
            if market not in markets:
                continue
            if not self.config.allow_overlapping_by_market and market in blocked_until and signal.timestamp <= blocked_until[market]:
                continue
            trade = self._replay_signal(markets[market], signal._asdict(), len(trades))
            if trade is None:
                continue
            trades.append(trade)
            blocked_until[market] = trade["exit_timestamp"]

        trades_df = pd.DataFrame(trades)
        if not trades_df.empty:
            trades_df = trades_df.sort_values(["exit_timestamp", "entry_timestamp", "trade_id"]).reset_index(drop=True)
        return BacktestResult(
            trades=trades_df,
            equity_curve=equity_curve(trades_df),
            backtest_summary=performance_summary(trades_df),
            regime_performance=regime_performance(trades_df),
        )

    def align_higher_timeframes(self, signals: pd.DataFrame, higher_timeframes: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
        """As-of align multi-timeframe context onto signal timestamps without lookahead."""

        aligned = signals.sort_values("timestamp").copy()
        tolerance = pd.Timedelta(self.config.timeframe_tolerance) if self.config.timeframe_tolerance else None
        for name, frame in higher_timeframes.items():
            context = self._normalise_columns(frame).sort_values("timestamp")
            if self.config.market_column in context.columns:
                pieces = []
                for market, subset in aligned.groupby("market", sort=False):
                    right = context[context[self.config.market_column].astype(str) == market]
                    if right.empty:
                        pieces.append(subset)
                        continue
                    pieces.append(pd.merge_asof(subset.sort_values("timestamp"), right, on="timestamp", direction="backward", tolerance=tolerance, suffixes=("", f"_{name}")))
                aligned = pd.concat(pieces, ignore_index=True).sort_values("timestamp")
            else:
                aligned = pd.merge_asof(aligned, context, on="timestamp", direction="backward", tolerance=tolerance, suffixes=("", f"_{name}"))
        return aligned

    def _prepare_market_data(self, market_data: Mapping[str, pd.DataFrame] | pd.DataFrame) -> dict[str, pd.DataFrame]:
        if isinstance(market_data, pd.DataFrame):
            frame = self._normalise_columns(market_data)
            if self.config.market_column not in frame.columns:
                frame[self.config.market_column] = "DEFAULT"
            inputs = {market: subset for market, subset in frame.groupby(self.config.market_column)}
        else:
            inputs = market_data
        output: dict[str, pd.DataFrame] = {}
        for market, frame in inputs.items():
            prepared = self._normalise_columns(frame)
            self._require_columns(prepared, REQUIRED_OHLCV_COLUMNS, f"market data for {market}")
            prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], utc=True)
            prepared = prepared.sort_values("timestamp").reset_index(drop=True)
            prepared["market"] = str(market)
            if "atr" not in prepared.columns:
                prepared["atr"] = self._estimate_atr(prepared)
            if "volume" not in prepared.columns:
                prepared["volume"] = np.nan
            if "regime" not in prepared.columns:
                prepared["regime"] = "NORMAL"
            prepared["regime"] = prepared["regime"].fillna("NORMAL").astype(str).str.upper().where(lambda s: s.isin(CANONICAL_REGIMES), "NORMAL")
            output[str(market)] = prepared
        return output

    def _prepare_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        prepared = self._normalise_columns(signals)
        self._require_columns(prepared, REQUIRED_SIGNAL_COLUMNS, "signals")
        prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], utc=True)
        if "market" not in prepared.columns:
            prepared["market"] = "DEFAULT"
        prepared["market"] = prepared["market"].astype(str)
        prepared["direction"] = prepared["direction"].map(self._normalise_direction)
        prepared = prepared[prepared["direction"].isin([1, -1])]
        ev_col = self.config.expected_value_column.lower()
        if ev_col not in prepared.columns:
            prepared["expected_R"] = 0.0
        elif ev_col != "expected_r":
            prepared["expected_R"] = pd.to_numeric(prepared[ev_col], errors="coerce").fillna(0.0)
        else:
            prepared["expected_R"] = pd.to_numeric(prepared["expected_r"], errors="coerce").fillna(0.0)
        prepared = prepared[prepared["expected_R"] >= self.config.min_ev]
        decision_col = self.config.decision_column.lower()
        if decision_col in prepared.columns:
            prepared = prepared[prepared[decision_col].astype(str).str.lower().isin(EXECUTE_ALIASES)]
        return prepared.sort_values("timestamp").reset_index(drop=True)

    def _replay_signal(self, candles: pd.DataFrame, signal: dict[str, Any], trade_id: int) -> dict[str, Any] | None:
        start_idx = candles["timestamp"].searchsorted(signal["timestamp"], side="left")
        if self.config.random_signal_delay_candles:
            lo, hi = self.config.random_signal_delay_candles
            start_idx += int(self._rng.integers(lo, hi + 1))
        if start_idx >= len(candles):
            return None
        entry_row = candles.iloc[start_idx]
        direction = int(signal["direction"])
        entry = self._value_or_default(signal, self.config.entry_price_column.lower(), entry_row["open"])
        atr = float(entry_row.get("atr", np.nan))
        if not np.isfinite(atr) or atr <= 0:
            atr = max(abs(entry_row["high"] - entry_row["low"]), 1e-12)
        default_sl = entry - direction * self.config.atr_stop_multiple * atr
        default_tp = entry + direction * self.config.atr_take_profit_multiple * atr
        sl = self._value_or_default(signal, self.config.stop_loss_column.lower(), default_sl)
        tp = self._value_or_default(signal, self.config.take_profit_column.lower(), default_tp)
        risk = abs(entry - sl)
        if risk <= 0 or not np.isfinite(risk):
            return None

        horizon_end = min(len(candles), start_idx + self.config.max_holding_candles + 1)
        path = candles.iloc[start_idx:horizon_end]
        mfe = 0.0
        mae = 0.0
        exit_price = float(path.iloc[-1]["close"])
        exit_ts = path.iloc[-1]["timestamp"]
        exit_reason = "TIME_EXIT"
        holding = len(path) - 1

        for offset, row in enumerate(path.itertuples(index=False)):
            high = float(row.high)
            low = float(row.low)
            if direction == 1:
                mfe = max(mfe, (high - entry) / risk)
                mae = min(mae, (low - entry) / risk)
                tp_hit = high >= tp
                sl_hit = low <= sl
            else:
                mfe = max(mfe, (entry - low) / risk)
                mae = min(mae, (entry - high) / risk)
                tp_hit = low <= tp
                sl_hit = high >= sl
            if tp_hit or sl_hit:
                if tp_hit and sl_hit and self.config.conservative_same_candle:
                    exit_price, exit_reason = float(sl), "SL"
                elif tp_hit:
                    exit_price, exit_reason = float(tp), "TP"
                else:
                    exit_price, exit_reason = float(sl), "SL"
                exit_ts = row.timestamp
                holding = offset
                break

        r_multiple = direction * (exit_price - entry) / risk
        return {
            "trade_id": trade_id,
            "market": signal["market"],
            "entry_timestamp": entry_row["timestamp"],
            "exit_timestamp": exit_ts,
            "direction": "LONG" if direction == 1 else "SHORT",
            "entry_price": float(entry),
            "exit_price": float(exit_price),
            "tp_price": float(tp),
            "sl_price": float(sl),
            "R": float(r_multiple),
            "win": bool(r_multiple > 0),
            "MFE": float(mfe),
            "MAE": float(mae),
            "holding_time": int(holding),
            "regime": str(signal.get("regime") or entry_row.get("regime", "NORMAL")).upper() if str(signal.get("regime") or "").upper() in CANONICAL_REGIMES else str(entry_row.get("regime", "NORMAL")).upper(),
            "expected_R": float(signal.get("expected_R", 0.0)),
            "exit_reason": exit_reason,
            "atr_at_entry": float(atr),
            "volume_at_entry": float(entry_row.get("volume", np.nan)) if pd.notna(entry_row.get("volume", np.nan)) else np.nan,
        }

    @staticmethod
    def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        result.columns = [str(col).strip().lower() for col in result.columns]
        return result

    @staticmethod
    def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
        missing = [column for column in columns if column not in frame.columns]
        if missing:
            raise ValueError(f"Missing required columns in {label}: {missing}")

    @staticmethod
    def _normalise_direction(value: Any) -> int | None:
        text = str(value).strip().lower()
        if text in LONG_ALIASES:
            return 1
        if text in SHORT_ALIASES:
            return -1
        return None

    @staticmethod
    def _estimate_atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
        high_low = frame["high"].astype(float) - frame["low"].astype(float)
        high_close = (frame["high"].astype(float) - frame["close"].astype(float).shift()).abs()
        low_close = (frame["low"].astype(float) - frame["close"].astype(float).shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window, min_periods=1).mean()

    @staticmethod
    def _value_or_default(values: Mapping[str, Any], column: str, default: float) -> float:
        value = values.get(column, np.nan)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = np.nan
        return float(default if not np.isfinite(numeric) else numeric)
