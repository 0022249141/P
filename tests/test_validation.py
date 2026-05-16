from __future__ import annotations

import numpy as np
import pandas as pd

from smc_validation import BacktestConfig, BacktestEngine, MonteCarloConfig, build_validation_report


def _market_frame() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=40, freq="h", tz="UTC")
    close = 100 + np.arange(40) * 0.2
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close + 0.1,
            "volume": 1000,
            "atr": 1.0,
            "regime": ["NORMAL"] * 10 + ["LOW_VOL"] * 10 + ["HIGH_VOL"] * 10 + ["MANIPULATION"] * 10,
        }
    )
    return frame


def test_backtest_replays_tp_sl_and_time_exit() -> None:
    market = _market_frame()
    signals = pd.DataFrame(
        {
            "timestamp": [market.loc[0, "timestamp"], market.loc[5, "timestamp"], market.loc[12, "timestamp"]],
            "market": ["xauusd", "xauusd", "xauusd"],
            "direction": ["LONG", "SHORT", "LONG"],
            "entry_price": [100.0, 101.0, 102.4],
            "tp_price": [100.5, 100.4, 110.0],
            "sl_price": [99.0, 101.7, 101.4],
            "expected_R": [0.4, 0.2, 0.1],
            "decision": ["EXECUTE", "EXECUTE", "EXECUTE"],
        }
    )

    result = BacktestEngine(BacktestConfig(max_holding_candles=2, allow_overlapping_by_market=True)).run(
        {"xauusd": market}, signals
    )

    assert result.backtest_summary["total_trades"] == 3
    assert set(result.trades["exit_reason"]) == {"TP", "SL", "TIME_EXIT"}
    assert {"MFE", "MAE", "holding_time", "regime"}.issubset(result.trades.columns)
    assert result.regime_performance["NORMAL"]["trades"] == 2


def test_monte_carlo_is_reproducible_and_report_matches_contract() -> None:
    market = _market_frame()
    signals = pd.DataFrame(
        {
            "timestamp": market.loc[::2, "timestamp"].to_list(),
            "market": ["harat"] * 20,
            "direction": ["LONG"] * 20,
            "entry_price": market.loc[::2, "open"].to_list(),
            "tp_price": (market.loc[::2, "open"] + 0.6).to_list(),
            "sl_price": (market.loc[::2, "open"] - 1.0).to_list(),
            "expected_R": np.linspace(0.1, 0.8, 20),
            "decision": ["EXECUTE"] * 20,
        }
    )
    backtest = BacktestEngine(BacktestConfig(allow_overlapping_by_market=True)).run({"harat": market}, signals)

    report_a = build_validation_report(backtest, MonteCarloConfig(simulations=100, seed=7))
    report_b = build_validation_report(backtest, MonteCarloConfig(simulations=100, seed=7))

    assert report_a["monte_carlo"] == report_b["monte_carlo"]
    assert report_a["backtest_summary"]["total_trades"] == 20
    assert {"LOW_VOL", "NORMAL", "HIGH_VOL", "MANIPULATION"}.issubset(report_a["regime_performance"])
    assert {"stable", "sensitivity_score", "overfitting_risk"}.issubset(report_a["robustness"])
    assert report_a["final_assessment"]["strategy_grade"] in {"A", "B", "C", "FAIL"}
