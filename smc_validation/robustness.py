"""Rule-based stress tests and overfitting diagnostics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .metrics import ev_realized_correlation, max_drawdown, profit_factor, safe_float, sharpe_ratio


def run_robustness_tests(trades: pd.DataFrame, monte_carlo: dict[str, Any]) -> dict[str, Any]:
    """Evaluate deterministic stress scenarios and overfitting risk flags."""

    if trades.empty:
        return {
            "stable": False,
            "sensitivity_score": 1.0,
            "overfitting_risk": 1.0,
            "stress_tests": {},
            "failure_reasons": ["no_trades"],
        }

    base_r = trades["R"].astype(float).to_numpy()
    base_expectancy = float(np.mean(base_r))
    stressed = {
        "increased_volatility_50pct_atr": _stress_volatility(base_r),
        "decreased_liquidity_30pct_volume": _stress_liquidity(base_r),
        "low_to_high_regime_shift": _stress_regime_shift(trades),
        "random_signal_delay_1_3_candles": _stress_signal_delay(base_r),
    }
    stress_summaries = {name: _stress_summary(values, base_expectancy) for name, values in stressed.items()}
    sensitivity_score = safe_float(np.mean([summary["expectancy_decay"] for summary in stress_summaries.values()]))

    reasons: list[str] = []
    regime_collapse = _detect_regime_collapse(trades)
    if regime_collapse:
        reasons.append("performance_collapses_in_single_regime")
    if _profit_factor_unstable(trades):
        reasons.append("profit_factor_unstable_across_windows")
    ev_corr = ev_realized_correlation(trades)
    if ev_corr < 0.05:
        reasons.append("ev_realized_correlation_too_low")
    dispersion = _monte_carlo_dispersion(monte_carlo)
    if dispersion > 1.0:
        reasons.append("monte_carlo_dispersion_too_wide")
    if sensitivity_score > 0.65:
        reasons.append("stress_sensitivity_too_high")

    overfitting_risk = min(1.0, 0.18 * len(reasons) + 0.32 * min(1.0, dispersion) + 0.25 * sensitivity_score + (0.15 if ev_corr < 0.05 else 0.0))
    stable = bool(not reasons and base_expectancy > 0 and monte_carlo.get("ruin_probability", 1.0) < 0.05)
    return {
        "stable": stable,
        "sensitivity_score": safe_float(min(1.0, sensitivity_score)),
        "overfitting_risk": safe_float(overfitting_risk),
        "stress_tests": stress_summaries,
        "failure_reasons": reasons,
    }


def strategy_grade(summary: dict[str, Any], robustness: dict[str, Any], monte_carlo: dict[str, Any]) -> tuple[str, bool]:
    """Translate statistics into a conservative deployment grade."""

    if summary["total_trades"] < 30 or summary["expectancy"] <= 0 or summary["profit_factor"] < 1.05:
        return "FAIL", False
    if not robustness["stable"] or monte_carlo.get("ruin_probability", 1.0) >= 0.1:
        return "FAIL", False
    risk = robustness["overfitting_risk"]
    if summary["profit_factor"] >= 1.7 and summary["sharpe"] >= 0.45 and risk < 0.25:
        return "A", True
    if summary["profit_factor"] >= 1.35 and risk < 0.45:
        return "B", True
    return "C", risk < 0.6


def _stress_volatility(r: np.ndarray) -> np.ndarray:
    stressed = r.copy()
    stressed[stressed < 0] *= 1.5
    stressed[stressed > 0] *= 0.9
    return stressed


def _stress_liquidity(r: np.ndarray) -> np.ndarray:
    return r - 0.06 * np.maximum(1.0, np.abs(r))


def _stress_regime_shift(trades: pd.DataFrame) -> np.ndarray:
    shifted = trades["R"].astype(float).to_numpy(copy=True)
    regimes = trades.get("regime", pd.Series(["NORMAL"] * len(trades))).astype(str).to_numpy()
    high = trades.loc[trades.get("regime", pd.Series(dtype=str)).astype(str) == "HIGH_VOL", "R"].astype(float).to_numpy()
    if len(high):
        low_positions = np.where(regimes == "LOW_VOL")[0]
        shifted[low_positions] = np.resize(high, len(low_positions)) if len(low_positions) else shifted[low_positions]
    shifted[regimes == "MANIPULATION"] -= 0.15
    return shifted


def _stress_signal_delay(r: np.ndarray) -> np.ndarray:
    delayed = np.roll(r, 1)
    delayed[0] = r[0]
    return delayed - 0.03 * np.maximum(1.0, np.abs(delayed))


def _stress_summary(values: np.ndarray, base_expectancy: float) -> dict[str, float]:
    expectancy = safe_float(np.mean(values))
    decay = 0.0 if base_expectancy <= 0 else max(0.0, (base_expectancy - expectancy) / abs(base_expectancy))
    return {
        "expectancy": expectancy,
        "profit_factor": safe_float(profit_factor(values), default=999.0),
        "max_drawdown": max_drawdown(np.cumsum(values)),
        "sharpe": sharpe_ratio(values),
        "expectancy_decay": safe_float(min(1.0, decay)),
    }


def _detect_regime_collapse(trades: pd.DataFrame) -> bool:
    if "regime" not in trades.columns:
        return False
    grouped = trades.groupby("regime")["R"].agg(["count", "mean"])
    enough = grouped[grouped["count"] >= max(5, 0.1 * len(trades))]
    return bool((enough["mean"] < -0.25).any())


def _profit_factor_unstable(trades: pd.DataFrame, windows: int = 4) -> bool:
    if len(trades) < 40:
        return False
    factors = []
    for chunk in np.array_split(trades["R"].astype(float).to_numpy(), windows):
        factors.append(safe_float(profit_factor(chunk), default=999.0))
    finite = np.array([value for value in factors if np.isfinite(value) and value < 999.0])
    if len(finite) < 2:
        return False
    return bool(finite.min() < 1.0 or finite.std() / max(abs(finite.mean()), 1e-12) > 0.65)


def _monte_carlo_dispersion(monte_carlo: dict[str, Any]) -> float:
    dist = monte_carlo.get("equity_distribution", {})
    mean = abs(float(dist.get("mean", 0.0)))
    width = float(dist.get("p95", 0.0)) - float(dist.get("p5", 0.0))
    return safe_float(width / max(mean, 1e-12))
