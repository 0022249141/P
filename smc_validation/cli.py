"""Command line interface for deterministic SMC validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backtest import BacktestConfig, BacktestEngine
from .monte_carlo import MonteCarloConfig
from .report import build_validation_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic SMC backtest and Monte Carlo validation.")
    parser.add_argument("--signals", required=True, help="CSV of generated EV + execution signals.")
    parser.add_argument("--market", action="append", required=True, help="Market CSV mapping as MARKET=path.csv. Repeat for abshodeh/harat/xauusd.")
    parser.add_argument("--higher-timeframe", action="append", default=[], help="Higher timeframe CSV mapping as NAME=path.csv.")
    parser.add_argument("--max-holding-candles", type=int, default=96)
    parser.add_argument("--min-ev", type=float, default=0.0)
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    market_csvs = _parse_mapping(args.market)
    higher = _parse_mapping(args.higher_timeframe)
    backtest = BacktestEngine(
        BacktestConfig(max_holding_candles=args.max_holding_candles, min_ev=args.min_ev, seed=args.seed)
    ).run_from_csv(market_csvs=market_csvs, signals_csv=args.signals, higher_timeframe_csvs=higher)
    report = build_validation_report(backtest, MonteCarloConfig(simulations=args.simulations, seed=args.seed))
    payload = json.dumps(report, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


def _parse_mapping(values: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Expected NAME=path.csv mapping, got: {value}")
        name, path = value.split("=", 1)
        mapping[name] = path
    return mapping


if __name__ == "__main__":
    main()
