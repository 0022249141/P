# KAN-1 Characterization Test Matrix

## Objective

Create a pre-migration test map for existing behavior before modules are moved, renamed, or consolidated. This matrix is not an implementation of the tests; it defines the coverage required to make future refactors safe.

## Current Verification Evidence

Commands run on 2026-07-17:

| Command | Result |
| --- | --- |
| `python --version` | Passed: `Python 3.11.9`. |
| `python -m pip install . --dry-run --no-deps` | Passed: package metadata builds; pip reports `Would install smc-validation-0.1.0`. |
| `python -m compileall -q smc_validation core engines src pipelines` | Passed. |
| `python -m pytest -q` | Failed because `pytest` is not installed. |
| `.\venv\Scripts\python.exe -m pytest -q` | Failed because `pytest` is not installed in the committed `venv/`. |
| `.\venv\Scripts\python.exe -m pip list --format=freeze` | Failed inside committed pip internals. |

## Existing Test Classification

| File | Current behavior | Keep as characterization? |
| --- | --- | --- |
| `tests/test_core_schemas.py` | Real Pydantic schema tests. | Yes; expand around data contract. |
| `tests/test_market_state_machine.py` | Real market state machine tests. | Yes; add deterministic fixtures and edge cases. |
| `tests/test_all_layers.py` | Print-only placeholder tests. | Replace with assertions after fixture capture. |
| `tests/test_validation.py` | Print-only placeholder test. | Replace with assertions around `smc_validation`. |
| `tests/test_layer1_2.py` | Loads `data/XAU_USD-15.csv` at import time and prints results. | Convert to isolated test using fixture CSV under controlled path. |
| `tests/run_*.py`, `tests/quick_test.py`, `tests/optimize_weights.py` | Executable analysis scripts. | Treat as candidate behavior captures, not pytest tests. |

## Characterization Matrix

| Area | Existing surfaces | Minimum behavior to freeze | Fixture/data need | Temporal checks | Priority |
| --- | --- | --- | --- | --- | --- |
| Data ingestion and cleaning | `pipelinefix_data.py`, `pipelines/legacy/01_fix_data.py`, `src/market_engine.py`, `src/layer1_market_data_engine.py` | Canonical columns, numeric OHLCV validation, duplicate handling, ATR output, session labeling. | Small CSVs for each supported format, including headerless sample. | No `bfill` or future-derived initial values in downstream-eligible outputs. | P0 |
| Multi-timeframe resampling | `pipelines/legacy/02_resample_mtf.py`, `src/mtf_analyzer.py` | M1 to M5/M15/M30/H1/H4/D1 aggregation rules, timestamp boundary semantics, volume aggregation. | One deterministic M1 fixture with known expected bars. | Resampled bar must not close before source bars are available. | P0 |
| Structure | `pipelines/legacy/03_structure.py`, `src/structure_engine.py`, `src/layer2_structural_engine.py` | Swing highs/lows, BOS/CHoCH/MSS labels, pivot timestamp and confirmation timestamp. | Synthetic candles with known pivot confirmation points. | Future-looking pivots must be delayed to confirmation time. | P0 |
| Liquidity | `pipelines/legacy/04_liquidity.py`, `src/liquidity_engine.py`, `src/layer3_liquidity_engine.py`, `src/zone_engine.py` | BSL/SSL registration, equal level clustering, sweep/reclaim/acceptance state transitions, destination ranking. | Synthetic liquidity-pool fixture plus one market sample. | Pools must be registered before testing outcomes. | P0 |
| Session intelligence | `pipelines/legacy/05_sessions.py`, `src/layer1_market_data_engine.py`, `market_params.py` | Session partition labels for XAUUSD, Herat, Abshodeh; Tehran presentation separation. | Timestamp fixtures around boundaries and DST changes. | Session labels must depend only on timestamp/calendar. | P1 |
| Displacement and delivery | `pipelines/legacy/08_displacement.py`, `src/displacement_engine.py`, `src/layer4_displacement_engine.py`, `delivery_quality.py` | Impulse candle detection, displacement score, inefficiency/FVG behavior, delivery quality score components. | Synthetic continuation/retracement sequences. | Scores cannot inspect future candles unless marked post-confirmation. | P1 |
| Zone and setup scoring | `pipelines/legacy/09_zone_scoring.py`, `python 09_zone_scoring.py`, `src/scoring_engine.py` | Order-block, breaker, FVG, setup-score calculation and weight behavior. | Small fixture with expected scores and missing-column cases. | Rolling maxima must use past-only windows. | P1 |
| Market state/regime | `engines/market_state_machine.py`, `regime.py`, `pipelines/legacy/10_state_machine.py` | State transitions, transition probabilities, compression/expansion/manipulation rules. | Existing unit fixtures plus regime edge cases. | State at `t` must use candles available by `t`. | P0 |
| Execution map | `pipelines/legacy/11_execution.py`, `src/execution_logic.py`, `src/optimizer.py`, `src/simple_backtest.py` | Entry/stop/target generation, invalidation, same-bar ambiguity policy, no target without liquidity destination. | Signal fixture with long/short/conflict cases. | No execution decision from future outcome candles. | P0 |
| Backtest | `smc_validation/backtest.py` | Candle-by-candle replay, max holding, EV filter, fill order, higher-timeframe alignment. | Market and signal fixtures with known trade outcomes. | Higher-timeframe data must be as-of joined only. | P0 |
| Monte Carlo and robustness | `smc_validation/monte_carlo.py`, `smc_validation/robustness.py`, `smc_validation/metrics.py` | Seed determinism, regime-cluster sampling, drawdown distribution, robustness grades. | Trades fixture with regimes and R multiples. | Simulations must not reorder temporal validation inputs unless labeled stress. | P1 |
| Reports and dashboards | `smc_validation/report.py`, `dashboard_generator.py`, `dashboard.html`, `dashboard_enhanced.html` | JSON contract, evidence labels, readiness gates, Persian/RTL report sections. | Frozen report input fixture. | Reports must include failed gates and limitations. | P1 |
| Broker/live surfaces | `mt5_executor.py`, `live_data_server.py`, `live_signal_engine.py` | Import safety, disabled-by-default broker actions, explicit execution-readiness blocks. | Mock broker and file fixtures. | No live execution without spread/fill/slippage evidence. | P2 |

## Acceptance Criteria for Future Characterization PRs

Each characterization PR should:

1. Add small fixtures rather than relying on committed full research CSVs.
2. Assert exact outputs for current behavior before refactoring.
3. Label any current behavior that uses future data as post-confirmation or ineligible for real-time backtests.
4. Record command, seed, fixture hash, and expected artifact hash where deterministic outputs are involved.
5. Keep code movement out of the same PR unless the tests already prove equivalence.

## Blockers Before Migration

- `pytest` is not installed in the active or committed environments.
- Several pytest-discoverable files execute work at import time.
- Structure logic includes future shifts without a confirmation-time contract.
- Data paths are split between committed `raw_data/`/`data_clean/` and hard-coded `data/` examples.
- Duplicate engines cannot be consolidated until fixture-backed equivalence or intentional divergence is documented.
