# KAN-1 Repository Inventory Audit

## Scope

Issue: `KAN-1`, GitHub issue #20.

This inventory was built from tracked Git state, not from `project_tree.txt`.
No source files, datasets, or generated artifacts were moved or deleted.

Primary evidence commands:

```powershell
git ls-files
git ls-files | Measure-Object
git ls-files | Where-Object { $_ -notmatch '^venv/' } | Measure-Object
git ls-files '*.py'
git ls-files '*.csv'
python -m compileall -q smc_validation core engines src pipelines
```

## Tracked Inventory Summary

| Scope | Count | Notes |
| --- | ---: | --- |
| All tracked paths | 6,719 | Includes a committed virtual environment. |
| Tracked paths excluding `venv/` | 173 | Project-owned code, docs, data, IDE artifacts, and scripts. |
| Tracked Python paths | 4,411 | Dominated by `venv/Lib/site-packages`. |
| Project Python paths excluding `venv/` | 79 | Source, tests, root scripts, package modules. |
| Tracked CSV paths | 91 | Includes 56 project CSVs plus dependency test data under `venv/`. |
| Project CSV paths excluding `venv/` | 56 | `raw_data/`, `data_clean/`, and `data_features/`. |
| Tracked environment paths | 6,546 | `venv/`, about 138.8 MB in the working tree. |

Top-level tracked path counts excluding `venv/`:

| Path | Count | Classification |
| --- | ---: | --- |
| `raw_data/` | 27 | Raw market CSVs, committed. |
| `data_clean/` | 27 | Cleaned market CSVs, committed. |
| `src/` | 21 | Primary exploratory/engine modules. |
| `tests/` | 13 | Mixed pytest files and executable analysis scripts. |
| `pipelines/` | 12 | Legacy pipeline package. |
| `.vs/` | 11 | Visual Studio local databases/state, committed. |
| `smc_validation/` | 8 | Installable deterministic validation package. |
| `.vscode/` | 3 | Editor configuration. |
| `core/` | 2 | Pydantic schemas and package init. |
| `engines/` | 2 | Market state machine package. |
| `data_features/` | 2 | Derived feature CSVs, committed. |

## Entrypoints and Runnable Surfaces

### Packaged CLI

| Entrypoint | Evidence | Notes |
| --- | --- | --- |
| `smc-validate` | `pyproject.toml` `[project.scripts]` maps to `smc_validation.cli:main`. | Only declared CLI currently. |

### Root scripts and live surfaces

| Path | Role | Audit note |
| --- | --- | --- |
| `pipelinerun_all.py` | Runs multi-timeframe pipeline over `data_clean/`. | Mutates `sys.path` and uses future shifts in structure logic. |
| `run_all_pipeline.py` | Runs root pipeline flow. | Mutates `sys.path`; assumes local paths. |
| `pipelinefix_data.py` | Headerless CSV cleaner into `data_clean/`. | Creates output directory at import time. |
| `adaptive_sweep.py`, `fvg.py`, `order_blocks.py` | CLI-style analytical helpers. | Have `if __name__ == "__main__"` guards. |
| `live_data_server.py` | Repeatedly writes `live_prices.json`. | Reads from `data/`, which is not the committed data layout. |
| `live_signal_engine.py` | Live signal evaluator over a CSV path. | Reads CSV in object construction. |
| `mt5_executor.py` | MetaTrader5 pending-order sender. | Imports and initializes broker integration at import time; not execution-ready under current acceptance criteria. |
| `test_smc_rtm_live.py` | Large live-style integration script. | Writes report JSON; not a pytest characterization test. |

### Legacy Pipeline Scripts

Tracked legacy scripts:

```text
pipelines/legacy/01_fix_data.py
pipelines/legacy/02_resample_mtf.py
pipelines/legacy/03_structure.py
pipelines/legacy/04_liquidity.py
pipelines/legacy/05_sessions.py
pipelines/legacy/06_quality_check.py
pipelines/legacy/08_displacement.py
pipelines/legacy/09_zone_scoring.py
pipelines/legacy/10_state_machine.py
pipelines/legacy/11_execution.py
```

Gaps in numbering are observable (`07` is absent). These scripts are a behavior source and should be characterized before any relocation.

### `src/` Analysis Layers

| Area | Current files |
| --- | --- |
| Market data | `src/market_engine.py`, `src/layer1_market_data_engine.py` |
| Structure | `src/structure_engine.py`, `src/layer2_structural_engine.py` |
| Liquidity | `src/liquidity_engine.py`, `src/layer3_liquidity_engine.py`, `src/zone_engine.py` |
| Displacement | `src/displacement_engine.py`, `src/layer4_displacement_engine.py` |
| Scoring/execution | `src/scoring_engine.py`, `src/execution_logic.py`, `src/optimizer.py`, `src/simple_backtest.py` |
| Supporting analytics | `src/mtf_analyzer.py`, `src/volume_profile.py`, `src/iceberg_detector.py`, `src/signal_explainer.py`, `src/ml_filter.py` |
| SMC/RTM composite | `src/smc_rtm_liquidity_enhancer.py` |

`src/New Python Source File.py` is tracked and empty.

## Tests and Characterization Status

Pytest-shaped files:

```text
tests/test_all_layers.py
tests/test_core_schemas.py
tests/test_layer1_2.py
tests/test_market_state_machine.py
tests/test_validation.py
```

Executable analysis scripts under `tests/`:

```text
tests/generate_dashboard_data.py
tests/optimize_weights.py
tests/quick_test.py
tests/run_all_markets.py
tests/run_all_markets_complete.py
tests/run_analysis_final.py
tests/run_full_pipeline.py
tests/run_with_ml_filter.py
```

Coverage observations:

- `tests/test_core_schemas.py` has real schema assertions.
- `tests/test_market_state_machine.py` has real state-machine assertions.
- `tests/test_all_layers.py` and `tests/test_validation.py` mostly print placeholder output.
- `tests/test_layer1_2.py` performs data loading and prints at import time, so pytest collection can execute behavior before a test function is called.
- Several `tests/run_*.py` files mutate `sys.path` and write outputs under `data/`.

## Duplicate or Divergent Implementations

Static AST scan found repeated class/function names that require characterization before consolidation:

| Symbol | Locations | Audit interpretation |
| --- | --- | --- |
| `MarketDataEngine` | `src/market_engine.py`, `src/layer1_market_data_engine.py` | Two market-data engines with different responsibilities and APIs. |
| `StructuralEngine` | `pipelines/legacy/03_structure.py`, `src/structure_engine.py`, `src/layer2_structural_engine.py` | Legacy, compact, and layer-2 variants coexist. |
| `LiquidityEngine` | `pipelines/legacy/04_liquidity.py`, `src/liquidity_engine.py`, `src/layer3_liquidity_engine.py` | Legacy/root and layer-3 variants coexist. |
| `DisplacementEngine` | `src/displacement_engine.py`, `src/layer4_displacement_engine.py` | Compact scoring and layer-4 variants coexist. |
| `score_order_blocks` | `pipelines/legacy/09_zone_scoring.py`, `python 09_zone_scoring.py` | Duplicate scoring implementation with a path name that contains spaces. |
| `compute_setup_score` | `pipelines/legacy/09_zone_scoring.py`, `python 09_zone_scoring.py` | Duplicate setup-score implementation. |

## Temporal Integrity and Side-Effect Findings

These are audit findings only; no behavior was changed in this branch.

| Finding | Evidence | Risk |
| --- | --- | --- |
| Future shifts in structure logic | `pipelinerun_all.py:50-51`, `src/structure_engine.py:30-32` use `shift(-1)` or `shift(-2)`. | Potential look-ahead/repainting unless outputs expose confirmation time and are excluded from real-time backtests. |
| Backfill in layer-1 ATR | `src/layer1_market_data_engine.py:230` uses `fillna(method='bfill')`. | Future information can seed early ATR values. |
| Import-time side effects | `mt5_executor.py` initializes MetaTrader5 and reads a plan CSV at top level; multiple `tests/*` scripts print, read files, or call engines at import time. | Test collection and imports can execute non-deterministic or broker-dependent behavior. |
| Path mutation | 16 occurrences of `sys.path.insert`, mostly in runner/test scripts. | Installability and import behavior differ by current working directory. |
| Non-deterministic timestamps | `core/schemas.py:321`, `dashboard_generator.py:88`, tests use `datetime.now(...)`. | Fine for event metadata, but deterministic artifacts need explicit run-manifest timestamps. |

## Generated and Local Artifacts

Tracked artifacts requiring a separate hygiene PR:

| Path family | Evidence |
| --- | --- |
| `venv/` | 6,546 tracked paths, about 138.8 MB; includes dependency binaries and vendored test data. |
| `.vs/` | Visual Studio databases and local state such as `CodeChunks.db`, `SemanticSymbols.db`, `slnx.sqlite`, `.wsuo`. |
| `.vscode/` | Editor settings, launch config, and MCP config. |
| `project_tree.txt` | Contains absolute local paths under `C:\Users\pouria.sl\Documents\GitHub\P`. |
| `dashboard.html`, `dashboard_enhanced.html`, `live_prices.json` | Generated or runtime artifacts committed at root. |
| `P` | Gitlink mode `160000` points to commit `2fdb0ef...`, but `.gitmodules` is missing. `git submodule status` fails with `no submodule mapping found`. |

## Inventory Conclusion

The current repository contains a usable seed for schemas, state machine logic, validation/backtest code, and exploratory SMC/RTM engines, but it is not yet migration-ready. The blocker is not a single broken file; it is the absence of characterization coverage around multiple competing implementations, plus committed environment/data artifacts and ambiguous package boundaries.

Recommended next action: approve the KAN-1 backlog, then execute the cleanup and characterization tasks as small PRs before any module relocation.
