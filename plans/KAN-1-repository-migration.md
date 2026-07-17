# KAN-1 Repository Audit and Migration Plan

## 1. Objective

Complete an evidence-based repository audit before any large-scale refactor. The user-visible outcome is a reviewed audit package that maps the current repository to the governed Institutional Trading Lab target architecture, identifies migration blockers, and converts them into prioritized follow-up work.

This plan intentionally stops at audit deliverables. It does not move modules, delete datasets, rewrite analytical engines, or merge to `main`.

## 2. Jira and Specification Trace

Jira/GitHub key: `KAN-1`, GitHub issue #20, "KAN-1 Repository audit and migration backlog".

Specifications read and applied:

- `AGENTS.md`
- `PLANS.md`
- `PROJECT_SPEC.md`
- `DATA_CONTRACT.md`
- `DOMAIN_RULES.md`
- `ACCEPTANCE_CRITERIA.md`
- `ROADMAP.md`

Issue #20 deliverables:

- `docs/audits/repository-inventory.md`
- `docs/audits/packaging-and-dependencies.md`
- `docs/audits/data-and-git-hygiene.md`
- `docs/audits/characterization-test-matrix.md`
- `docs/architecture/current-to-target-map.md`
- updated `plans/KAN-1-repository-migration.md`
- prioritized migration backlog

Acceptance-criteria trace:

- Requirements and assumptions documented in this plan and audit docs.
- Relevant tests and exact command results recorded.
- Temporal integrity and look-ahead risks identified.
- Data and migration impact documented.
- Evidence limitations disclosed.
- PR must be draft-only for human review.

## 3. Current-State Evidence

Observed from tracked Git state:

- Repository has 6,719 tracked paths.
- Excluding `venv/`, repository-owned tracked paths total 173.
- `venv/` is committed with 6,546 tracked paths and about 138.8 MB in the working tree.
- Project CSVs are committed under `raw_data/`, `data_clean/`, and `data_features/`, not under the target `data/raw`, `data/staged`, and `data/curated` layout.
- `smc_validation/`, `core/`, and `engines/` are package-discovered by `pyproject.toml`.
- `pipelines/legacy/` is a package on disk but excluded from package discovery.
- `src/` and root scripts contain many active analytical modules but are not installable package surfaces.
- `.vs/`, `.vscode/`, generated dashboard/runtime artifacts, and `project_tree.txt` are tracked.
- `P` is a gitlink with no `.gitmodules` mapping; `git submodule status` fails.
- Duplicate or divergent implementations exist for market data, structure, liquidity, displacement, and zone scoring.
- Future-looking logic is present in `pipelinerun_all.py` and `src/structure_engine.py`; `src/layer1_market_data_engine.py` uses ATR backfill.

Detailed evidence is recorded in:

- `docs/audits/repository-inventory.md`
- `docs/audits/packaging-and-dependencies.md`
- `docs/audits/data-and-git-hygiene.md`
- `docs/audits/characterization-test-matrix.md`
- `docs/architecture/current-to-target-map.md`
- `docs/audits/migration-backlog.md`

## 4. Assumptions and Domain Questions

Implementation assumptions:

- `KAN-1` is audit-only; code movement and cleanup are follow-up tasks.
- Committed CSVs should be preserved until a human approves data hygiene work.
- Duplicate engines may encode divergent behavior and must not be collapsed without characterization tests.
- Current hard-coded `data/` paths may refer to an older or local layout; the audit records the mismatch but does not repair it.

Domain questions for future work:

- Which committed datasets are approved fixtures versus local research data?
- What timezone/source semantics apply to each market feed?
- Which structure/liquidity implementation should become canonical after behavior capture?
- What execution-cost evidence is available for spread, slippage, commission, and fill policy?
- Which heuristic scores may remain qualitative versus statistically calibrated?

## 5. Proposed Architecture

Target architecture remains the repository specification:

- `core/`: contracts, configuration, time/calendar, event bus, audit metadata.
- `pipelines/`: ingestion, validation, normalization, resampling, orchestration.
- `engines/`: structure, liquidity, sessions, inventory, cross-market, probability.
- `services/`: workflows, reporting, dashboard/API/live surfaces.
- `smc_validation/`: deterministic backtest, Monte Carlo, robustness, validation reports.
- `tests/`: unit, integration, regression, leakage, reproducibility tests.
- `docs/`: product, domain, architecture, audits, decisions, runbooks.
- `data/`: local raw/staged/curated/manifests/artifacts policy.

Current-to-target mapping is documented in `docs/architecture/current-to-target-map.md`.

Compatibility strategy:

- Characterize behavior first.
- Move one subsystem per later PR.
- Preserve old entrypoints through adapters until callers migrate.
- Label future-derived signals as post-confirmation or ineligible for real-time backtests.

## 6. File-Level Change Map

Created audit deliverables:

- `docs/audits/repository-inventory.md`
- `docs/audits/packaging-and-dependencies.md`
- `docs/audits/data-and-git-hygiene.md`
- `docs/audits/characterization-test-matrix.md`
- `docs/audits/migration-backlog.md`
- `docs/architecture/current-to-target-map.md`

Modified:

- `plans/KAN-1-repository-migration.md`

Left untouched by design:

- All analytical engines.
- All datasets.
- All package metadata.
- All tests.
- All generated artifacts.
- All git hygiene cleanup targets.

## 7. Implementation Steps

1. Read repository governance and issue requirements.
2. Create isolated worktree on `KAN-1-repository-audit` to avoid disturbing unrelated local work.
3. Inventory tracked files from Git.
4. Audit package discovery, dependencies, CI, installability, and Windows assumptions.
5. Audit committed data and Git hygiene risks.
6. Audit duplicate code, entrypoints, tests, side effects, and temporal-integrity risks.
7. Build characterization-test matrix.
8. Build current-to-target architecture map.
9. Convert findings into a prioritized backlog.
10. Commit audit deliverables and open a draft PR.

## 8. Verification

Exact commands and results:

| Command | Result |
| --- | --- |
| `python --version` | Passed: `Python 3.11.9`. |
| `python -m pip --version` | Passed: `pip 26.1.2`. |
| `python -m pip install . --dry-run --no-deps` | Passed: package metadata builds; `Would install smc-validation-0.1.0`. |
| `python -m compileall -q smc_validation core engines src pipelines` | Passed. |
| `python -m pytest -q` | Failed: active Python has no `pytest`. |
| `.\venv\Scripts\python.exe --version` | Passed: `Python 3.11.9`. |
| `.\venv\Scripts\python.exe -m pytest -q` | Failed: committed `venv/` has no `pytest`. |
| `.\venv\Scripts\python.exe -m pip list --format=freeze` | Failed inside committed pip internals with missing `pip._internal.operations.build`. |
| `git submodule status --recursive` | Failed: no submodule mapping found in `.gitmodules` for path `P`. |

No lint/type suite is currently established as reliable. The existing workflow runs broad `pylint .` on Python 3.10 and should be repaired before enforcement.

## 9. Data and Migration Impact

No data was modified.

Observed migration impact:

- 56 committed project CSVs need manifest coverage before movement.
- Current data layout differs from target `data/` contract.
- Timestamps in sampled CSVs are naive strings and require source/timezone labeling.
- Existing scripts point to both `data/` and current `raw_data/`/`data_clean/` paths.
- Removing tracked environment and IDE artifacts should be separate from data layout work.

Rollback:

- Audit docs can be reverted without affecting runtime behavior.
- No engine, dataset, or package interface changes were made.

## 10. Risks and Limitations

- Look-ahead/repainting: future shifts and ATR backfill are documented but not fixed in KAN-1.
- Survivorship/data provenance: committed CSVs lack source and timezone manifests.
- Timezone/DST: no versioned calendar or UTC-normalization manifest exists yet.
- Missing spread/fill data: live execution and execution-readiness claims remain blocked.
- Proxy-vs-observation: dealer/inventory language must remain labeled as inference unless direct order-flow evidence is added.
- Tests: pytest cannot currently run without environment repair.
- This audit used static analysis and sampled data checks; it did not validate every row of every CSV against G0-G9 gates.

## 11. Progress Log

2026-07-17:

- Read all repository governance/specification files.
- Fetched issue #20 details from GitHub.
- Created clean sibling worktree at `C:\Users\pouria.sl\Documents\GitHub\P-KAN-1-repository-audit`.
- Verified branch `KAN-1-repository-audit` tracks `origin/KAN-1-repository-audit`.
- Built tracked-file inventory from Git.
- Audited package discovery and dependency drift.
- Ran installability and compile checks.
- Recorded pytest and committed-venv failures.
- Created audit deliverables and prioritized backlog.

## 12. Completion Evidence

Completion is defined as:

- All audit deliverables exist.
- This execution plan is updated.
- Changes are committed with a `KAN-1` prefix.
- Branch is pushed.
- Draft PR is opened with scope, design, tests, data impact, risks, limitations, rollback, and acceptance checklist.

Human approval gate:

Stop after the audit deliverables and migration backlog. Do not perform wholesale architecture migration, delete datasets, rewrite engines, or merge to `main` without review.
