"""Final JSON report assembly for strategy validation."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .backtest import BacktestResult
from .monte_carlo import MonteCarloConfig, MonteCarloEngine
from .robustness import run_robustness_tests, strategy_grade


def build_validation_report(
    backtest: BacktestResult,
    monte_carlo_config: MonteCarloConfig | None = None,
) -> dict[str, Any]:
    """Build the exact final output contract requested by the strategy validator."""

    mc = MonteCarloEngine(monte_carlo_config).run(backtest.trades)
    robustness = run_robustness_tests(backtest.trades, mc)
    grade, deployable = strategy_grade(backtest.backtest_summary, robustness, mc)
    return {
        "backtest_summary": backtest.backtest_summary,
        "regime_performance": backtest.regime_performance,
        "monte_carlo": {
            "simulations": mc["simulations"],
            "equity_distribution": mc["equity_distribution"],
            "drawdown_distribution": {
                "mean": mc["drawdown_distribution"]["mean"],
                "worst_case": mc["drawdown_distribution"]["worst_case"],
            },
            "return_distribution": mc["return_distribution"],
            "sharpe_distribution": mc["sharpe_distribution"],
            "ruin_probability": mc["ruin_probability"],
        },
        "robustness": robustness,
        "final_assessment": {
            "strategy_grade": grade,
            "deployable": deployable,
        },
        "insights": _insights(backtest.trades, backtest.backtest_summary, robustness, mc, grade, deployable),
    }


def _insights(
    trades: pd.DataFrame,
    summary: dict[str, Any],
    robustness: dict[str, Any],
    monte_carlo: dict[str, Any],
    grade: str,
    deployable: bool,
) -> str:
    if trades.empty:
        return "No executable historical trades were produced; the strategy cannot be validated or deployed."
    mc_equity = monte_carlo["equity_distribution"]
    reasons = robustness.get("failure_reasons", [])
    regime_counts = trades.get("regime", pd.Series(dtype=str)).value_counts().to_dict()
    verdict = "deployable" if deployable else "not deployable"
    reason_text = " No instability flags were triggered." if not reasons else f" Instability flags: {', '.join(reasons)}."
    return (
        f"Grade {grade}: strategy is {verdict}. Historical expectancy is {summary['expectancy']:.3f}R/trade "
        f"with profit factor {summary['profit_factor']:.3f}, max drawdown {summary['max_drawdown']:.3f}R, "
        f"and EV/realized correlation {summary.get('ev_realized_correlation', 0.0):.3f}. "
        f"Monte Carlo final-equity p5/median/p95 is {mc_equity['p5']:.3f}/{mc_equity['median']:.3f}/{mc_equity['p95']:.3f}R "
        f"with ruin probability {monte_carlo['ruin_probability']:.3%}. "
        f"Regime sample distribution: {regime_counts}.{reason_text}"
    )
