# KAN-1 Prioritized Migration Backlog

## Backlog Policy

These backlog items are Jira-ready follow-ups derived from KAN-1 audit findings. They intentionally avoid mixing cleanup, behavior characterization, and architecture movement in the same PR.

## P0 Items

### KAN-2: Repair Test Environment and CI Baseline

Problem: `pytest` is absent from both the active Python and committed `venv/`; CI uses Python 3.10 and runs broad pylint without project dependencies.

Scope:

- Align Python runtime to `>=3.11`.
- Add documented fresh-environment setup.
- Ensure `python -m pytest -q` can run from a clean checkout.
- Repair `.github/workflows/pylint.yml` or replace with a minimal test workflow.

Acceptance criteria:

- `python -m pip install -e ".[test]"` succeeds in a fresh environment.
- `python -m pytest -q` runs without import-time file reads from missing `data/`.
- CI uses Python 3.11 and installs project/test dependencies.

### KAN-3: Data and Git Hygiene Cleanup

Problem: `venv/`, `.vs/`, generated artifacts, and a broken gitlink are tracked.

Scope:

- Remove tracked `venv/` and `.vs/` from Git history in a normal cleanup commit, not a destructive rewrite.
- Resolve or remove gitlink `P` with human approval.
- Move generated root artifacts to ignored output paths or regenerate them on demand.

Acceptance criteria:

- `git ls-files` contains no virtualenv or Visual Studio database files.
- `.gitignore` covers generated outputs.
- `git submodule status` no longer fails.

### KAN-4: Dataset Manifest and Fixture Policy

Problem: large CSVs are committed without provenance manifests, timezone labels, source declarations, or fixture policy.

Scope:

- Add a manifest generator for committed CSVs.
- Record full SHA-256, byte size, row count, schema, source label, volume meaning, timezone status, and parser decision.
- Define which CSVs are fixtures, local data, or generated outputs.

Acceptance criteria:

- Every committed project CSV has a manifest record.
- Missing timezone/source semantics are labeled `UNKNOWN` or `INFERRED`.
- Tests use small fixtures rather than full research CSVs unless explicitly marked integration.

### KAN-5: Characterize Structure and Liquidity Behavior

Problem: duplicate structure/liquidity engines exist and some logic uses future shifts.

Scope:

- Add fixtures for confirmed swings, BOS/CHoCH/MSS, equal levels, sweeps, reclaims, and acceptance.
- Freeze current outputs from legacy and `src/` implementations.
- Mark future-derived behavior as post-confirmation and ineligible for real-time backtest unless delayed.

Acceptance criteria:

- Tests expose pivot timestamp and confirmation timestamp.
- No event appears before its confirmation point in eligible outputs.
- Duplicate implementations are either proven equivalent or documented as divergent.

### KAN-6: Characterize Execution and Backtest Fill Policy

Problem: execution/backtest behavior needs explicit same-bar ambiguity, spread/slippage/cost, and target/invalidation policy.

Scope:

- Add deterministic fixtures for long/short, stop-first, target-first, no-fill, max-holding, and conflict cases.
- Freeze `smc_validation.BacktestEngine` behavior.
- Document execution-readiness blockers where cost data is absent.

Acceptance criteria:

- Backtest outcomes are deterministic under a fixed seed.
- Same-bar ambiguity is explicit and tested.
- Reports do not claim execution readiness without cost/fill evidence.

## P1 Items

### KAN-7: Align Package Boundaries and Dependencies

Problem: installed packages do not include `pipelines` or `src`, while many scripts depend on path mutation.

Scope:

- Decide which modules become installable packages.
- Split dependencies into runtime, test, research/ML, and live-broker extras.
- Remove `sys.path.insert` from tests after imports are package-safe.

Acceptance criteria:

- `pip install -e .` exposes all supported import surfaces.
- `src` or its replacement package has an intentional namespace.
- `scikit-learn`, `pytest`, and `MetaTrader5` are declared in appropriate extras.

### KAN-8: Resampling and Data Gate Characterization

Problem: G0-G9 gates are specified but not enforced as a pipeline contract.

Scope:

- Add tests for M1-to-M5/M15/M30/H1/H4/D1 reconciliation.
- Define validation gates as data structures.
- Block downstream consumers when required gates fail.

Acceptance criteria:

- Resampling is deterministic and fixture-backed.
- Gate status is emitted and auditable.
- Ineligible datasets are blocked from analytical engines.

### KAN-9: Report and Evidence Label Contract

Problem: reports and dashboards do not yet guarantee evidence labels, failed-gate disclosure, or readiness sections.

Scope:

- Add report schema/contract tests.
- Require `OBSERVED`, `DERIVED`, `INFERRED`, `HYPOTHESIS`, or `UNKNOWN` traceability for material claims.
- Keep Persian RTL output readable while preserving technical terms.

Acceptance criteria:

- Report fixtures include failed gates and limitations.
- No numeric probability is emitted from heuristic-only scores.
- Generated artifacts carry source/config/code-version metadata.

### KAN-10: Live and Broker Surface Quarantine

Problem: `mt5_executor.py` performs broker initialization at import time and live scripts write runtime files.

Scope:

- Move live/broker code behind explicit optional entrypoints after tests exist.
- Add mock broker tests and import-safety tests.
- Add execution-readiness gate requiring spread, slippage, commission, fill policy, and trade logs.

Acceptance criteria:

- Importing live modules performs no network/broker action.
- Broker execution cannot run without explicit opt-in config.
- Missing execution-cost evidence blocks live-readiness claims.

## P2 Items

### KAN-11: Architecture Migration PR Series

Problem: target architecture is defined but code remains split across root scripts, `src/`, `pipelines/legacy/`, and packages.

Scope:

- Move one characterized subsystem at a time.
- Keep compatibility adapters until callers migrate.
- Remove duplicate implementations only after equivalence or replacement is approved.

Acceptance criteria:

- Each move has before/after characterization evidence.
- Public interfaces and data contracts are unchanged or explicitly versioned.
- No wholesale refactor PR combines unrelated subsystems.

### KAN-12: Deterministic Artifact and Run Manifest Layer

Problem: runs do not consistently record code revision, dirty status, config, source hashes, locale/timezone, calendar version, dependency versions, and seeds.

Scope:

- Add run manifest schema.
- Integrate manifest emission into pipeline/report entrypoints.
- Hash deterministic outputs for reproducibility checks.

Acceptance criteria:

- Every generated analytical artifact can be traced to inputs, config, code revision, and seed.
- Dirty working-tree status is recorded.
- Deterministic reruns produce identical registered events and artifact hashes.
