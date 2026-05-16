"""Vectorized performance, regime, and equity-curve metrics."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .schema import CANONICAL_REGIMES


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert numeric output to a JSON-safe finite float."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def max_drawdown(equity: pd.Series | np.ndarray) -> float:
    """Return the most negative peak-to-trough drawdown in equity units."""

    series = pd.Series(equity, dtype="float64")
    if series.empty:
        return 0.0
    running_peak = series.cummax()
    drawdown = series - running_peak
    return safe_float(drawdown.min())


def sharpe_ratio(returns: pd.Series | np.ndarray, periods_per_year: float | None = None) -> float:
    """Simplified Sharpe ratio for a trade-return series."""

    series = pd.Series(returns, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna()
    if len(series) < 2:
        return 0.0
    std = series.std(ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    ratio = series.mean() / std
    if periods_per_year:
        ratio *= math.sqrt(periods_per_year)
    return safe_float(ratio)


def profit_factor(r_multiples: pd.Series | np.ndarray) -> float:
    """Gross wins divided by absolute gross losses."""

    r = pd.Series(r_multiples, dtype="float64")
    gross_profit = r[r > 0].sum()
    gross_loss = abs(r[r < 0].sum())
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return safe_float(gross_profit / gross_loss)


def ev_realized_correlation(trades: pd.DataFrame) -> float:
    """Pearson correlation between expected value and realized R."""

    if "expected_R" not in trades.columns or len(trades) < 2:
        return 0.0
    data = trades[["expected_R", "R"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) < 2 or data["expected_R"].nunique() < 2 or data["R"].nunique() < 2:
        return 0.0
    return safe_float(data["expected_R"].corr(data["R"]))


def performance_summary(trades: pd.DataFrame) -> dict[str, Any]:
    """Compute top-level metrics required by the final JSON contract."""

    if trades.empty:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_R": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "ev_realized_correlation": 0.0,
        }

    r = trades["R"].astype(float)
    equity = r.cumsum()
    return {
        "total_trades": int(len(trades)),
        "win_rate": safe_float((r > 0).mean()),
        "avg_R": safe_float(r.mean()),
        "profit_factor": safe_float(profit_factor(r), default=999.0),
        "expectancy": safe_float(r.mean()),
        "max_drawdown": max_drawdown(equity),
        "sharpe": sharpe_ratio(r),
        "ev_realized_correlation": ev_realized_correlation(trades),
    }


def regime_performance(trades: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Segment metrics by canonical regime, preserving empty regimes."""

    output: dict[str, dict[str, Any]] = {}
    total_drawdown = abs(max_drawdown(trades["R"].cumsum())) if not trades.empty else 0.0
    for regime in CANONICAL_REGIMES:
        subset = trades[trades.get("regime", pd.Series(dtype=str)).astype(str) == regime] if not trades.empty else trades
        if subset.empty:
            output[regime] = {
                "trades": 0,
                "expectancy": 0.0,
                "win_rate": 0.0,
                "max_drawdown": 0.0,
                "drawdown_contribution": 0.0,
                "trade_frequency": 0.0,
            }
            continue
        r = subset["R"].astype(float)
        dd = abs(max_drawdown(r.cumsum()))
        output[regime] = {
            "trades": int(len(subset)),
            "expectancy": safe_float(r.mean()),
            "win_rate": safe_float((r > 0).mean()),
            "max_drawdown": -safe_float(dd),
            "drawdown_contribution": safe_float(dd / total_drawdown) if total_drawdown else 0.0,
            "trade_frequency": safe_float(len(subset) / len(trades)),
        }
    return output


def equity_curve(trades: pd.DataFrame, rolling_window: int = 50) -> pd.DataFrame:
    """Build cumulative equity, drawdown, and rolling Sharpe curves."""

    if trades.empty:
        return pd.DataFrame(columns=["trade_id", "exit_timestamp", "equity", "drawdown", "rolling_sharpe"])
    r = trades["R"].astype(float).reset_index(drop=True)
    equity = r.cumsum()
    curve = pd.DataFrame(
        {
            "trade_id": trades.get("trade_id", pd.Series(range(len(trades)))).to_numpy(),
            "exit_timestamp": trades.get("exit_timestamp", pd.Series([pd.NaT] * len(trades))).to_numpy(),
            "equity": equity,
            "drawdown": equity - equity.cummax(),
            "rolling_sharpe": r.rolling(rolling_window, min_periods=max(2, min(10, rolling_window))).apply(
                lambda values: sharpe_ratio(values), raw=False
            ),
        }
    )
    curve["rolling_sharpe"] = curve["rolling_sharpe"].fillna(0.0)
    return curve
