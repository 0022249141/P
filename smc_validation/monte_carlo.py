"""Monte Carlo stress testing without predictive machine learning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .metrics import max_drawdown, safe_float, sharpe_ratio
from .schema import CANONICAL_REGIMES


@dataclass(frozen=True)
class MonteCarloConfig:
    """Configuration for stochastic robustness simulations."""

    simulations: int = 1000
    seed: int = 42
    initial_equity_R: float = 0.0
    ruin_threshold_R: float = -20.0
    slippage_atr_fraction: float = 0.05
    bootstrap_fraction: float = 1.0
    regime_cluster_probability: float = 0.35


class MonteCarloEngine:
    """Generate stochastic stress distributions from realized historical trades."""

    def __init__(self, config: MonteCarloConfig | None = None) -> None:
        self.config = config or MonteCarloConfig()
        self.rng = np.random.default_rng(self.config.seed)

    def run(self, trades: pd.DataFrame) -> dict[str, Any]:
        """Run sequence, bootstrap, slippage, and regime-cluster randomization."""

        if trades.empty:
            return self._empty_output()

        base = trades.reset_index(drop=True).copy()
        n = max(1, int(round(len(base) * self.config.bootstrap_fraction)))
        final_equity = np.empty(self.config.simulations)
        max_drawdowns = np.empty(self.config.simulations)
        total_returns = np.empty(self.config.simulations)
        sharpes = np.empty(self.config.simulations)
        ruined = np.zeros(self.config.simulations, dtype=bool)

        for idx in range(self.config.simulations):
            simulated_r = self._simulate_path(base, n)
            equity = self.config.initial_equity_R + np.cumsum(simulated_r)
            final_equity[idx] = equity[-1]
            total_returns[idx] = equity[-1] - self.config.initial_equity_R
            max_drawdowns[idx] = max_drawdown(equity)
            sharpes[idx] = sharpe_ratio(simulated_r)
            ruined[idx] = bool((equity <= self.config.ruin_threshold_R).any())

        return {
            "simulations": int(self.config.simulations),
            "equity_distribution": self._distribution(final_equity),
            "drawdown_distribution": {
                "mean": safe_float(max_drawdowns.mean()),
                "median": safe_float(np.median(max_drawdowns)),
                "p5": safe_float(np.percentile(max_drawdowns, 5)),
                "p95": safe_float(np.percentile(max_drawdowns, 95)),
                "worst_case": safe_float(max_drawdowns.min()),
            },
            "return_distribution": self._distribution(total_returns),
            "sharpe_distribution": self._distribution(sharpes),
            "ruin_probability": safe_float(ruined.mean()),
        }

    def _simulate_path(self, trades: pd.DataFrame, n: int) -> np.ndarray:
        sampled_idx = self.rng.integers(0, len(trades), size=n)
        sampled = trades.iloc[sampled_idx].copy()

        # Sequence randomization: shuffle the bootstrapped order.
        sampled = sampled.iloc[self.rng.permutation(len(sampled))]
        returns = sampled["R"].astype(float).to_numpy(copy=True)

        # Entry slippage in R terms.  ATR fraction is scaled by trade risk when available.
        if self.config.slippage_atr_fraction > 0:
            atr = sampled.get("atr_at_entry", pd.Series(np.ones(len(sampled)), index=sampled.index)).astype(float).to_numpy()
            risk = (sampled["entry_price"].astype(float) - sampled["sl_price"].astype(float)).abs().replace(0, np.nan).to_numpy()
            risk = np.where(np.isfinite(risk), risk, np.nanmedian(risk[np.isfinite(risk)]) if np.isfinite(risk).any() else 1.0)
            slip_r = self.rng.uniform(-self.config.slippage_atr_fraction, self.config.slippage_atr_fraction, size=len(sampled)) * atr / np.maximum(risk, 1e-12)
            returns -= np.abs(slip_r)

        # Regime-cluster randomization: replace some outcomes with same-regime outcomes.
        if self.config.regime_cluster_probability > 0 and "regime" in trades.columns:
            replace_mask = self.rng.random(len(sampled)) < self.config.regime_cluster_probability
            for regime in CANONICAL_REGIMES:
                positions = np.where(replace_mask & (sampled["regime"].astype(str).to_numpy() == regime))[0]
                pool = trades.loc[trades["regime"].astype(str) == regime, "R"].astype(float).to_numpy()
                if len(positions) and len(pool):
                    returns[positions] = self.rng.choice(pool, size=len(positions), replace=True)

        return returns

    @staticmethod
    def _distribution(values: np.ndarray) -> dict[str, float]:
        return {
            "mean": safe_float(np.mean(values)),
            "median": safe_float(np.median(values)),
            "p5": safe_float(np.percentile(values, 5)),
            "p95": safe_float(np.percentile(values, 95)),
        }

    def _empty_output(self) -> dict[str, Any]:
        zero_dist = {"mean": 0.0, "median": 0.0, "p5": 0.0, "p95": 0.0}
        return {
            "simulations": int(self.config.simulations),
            "equity_distribution": zero_dist,
            "drawdown_distribution": {**zero_dist, "worst_case": 0.0},
            "return_distribution": zero_dist,
            "sharpe_distribution": zero_dist,
            "ruin_probability": 0.0,
        }
