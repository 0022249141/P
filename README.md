# P

## Institutional SMC Strategy Validation

This repository provides a deterministic backtesting engine and Monte Carlo stress-testing framework for a multi-market SMC probabilistic trading system.  It extends an upstream EV + execution engine by replaying generated trade signals over historical OHLCV CSV data, then rejecting strategies that are profitable but statistically unstable.

The implementation is intentionally rule-based:

- **No machine learning**: no fitting, prediction, model training, or adaptive inference.
- **Deterministic replay**: every accepted signal is evaluated candle-by-candle against future historical data.
- **Stochastic stress only**: Monte Carlo uses sequence shuffling, bootstrapping, slippage perturbation, and regime-cluster resampling.
- **Reproducible**: all stochastic components accept a fixed random seed.

## CSV Inputs

Market CSVs must include at least:

```text
timestamp,open,high,low,close
```

Optional market columns:

```text
volume,atr,regime
```

Signal CSVs must include at least:

```text
timestamp,direction
```

Recommended signal columns from the EV + execution engine:

```text
market,entry_price,tp_price,sl_price,expected_R,decision,regime
```

Canonical regimes are `LOW_VOL`, `NORMAL`, `HIGH_VOL`, and `MANIPULATION`.

## Python API

```python
from smc_validation import BacktestConfig, BacktestEngine, MonteCarloConfig, build_validation_report

backtest = BacktestEngine(
    BacktestConfig(max_holding_candles=96, min_ev=0.05, seed=42)
).run_from_csv(
    market_csvs={
        "abshodeh": "data/abshodeh_m15.csv",
        "harat": "data/harat_m15.csv",
        "xauusd": "data/xauusd_m15.csv",
    },
    signals_csv="data/generated_signals.csv",
    higher_timeframe_csvs={"h1": "data/xauusd_h1.csv"},
)

report = build_validation_report(
    backtest,
    MonteCarloConfig(simulations=1000, seed=42, ruin_threshold_R=-20),
)
```

The report follows the requested JSON contract:

```json
{
  "backtest_summary": {"total_trades": 0, "win_rate": 0.0, "avg_R": 0.0, "profit_factor": 0.0, "expectancy": 0.0, "max_drawdown": 0.0, "sharpe": 0.0},
  "regime_performance": {"LOW_VOL": {}, "NORMAL": {}, "HIGH_VOL": {}, "MANIPULATION": {}},
  "monte_carlo": {"simulations": 1000, "equity_distribution": {}, "drawdown_distribution": {}, "ruin_probability": 0.0},
  "robustness": {"stable": false, "sensitivity_score": 0.0, "overfitting_risk": 0.0},
  "final_assessment": {"strategy_grade": "FAIL", "deployable": false},
  "insights": "structured statistical interpretation of performance stability"
}
```

## CLI

```bash
smc-validate \
  --signals data/generated_signals.csv \
  --market abshodeh=data/abshodeh_m15.csv \
  --market harat=data/harat_m15.csv \
  --market xauusd=data/xauusd_m15.csv \
  --higher-timeframe h1=data/xauusd_h1.csv \
  --max-holding-candles 96 \
  --min-ev 0.05 \
  --simulations 1000 \
  --seed 42 \
  --output validation_report.json
```

## Development test environment

Use Python 3.11 or newer. Create a fresh environment instead of relying on the
committed `venv/` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
```

On POSIX shells, replace the executable path with `./.venv/bin/python`.

## Install Codex versions

Run the helper script to install the requested Codex versions globally:

```bash
./scripts/install-codex.sh
```
