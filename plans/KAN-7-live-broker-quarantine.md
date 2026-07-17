# KAN-7 Live and Broker Quarantine Plan

## 1. Objective
Quarantine the repository's MetaTrader 5 and live-data surfaces so importing them is inert, broker support remains optional, dry-run is the default, and live order submission is impossible without explicit configuration and execution-readiness evidence.

This slice does not connect to a broker, send or alter an order, refactor analytical engines, or modify market datasets.

## 2. Jira and Specification Trace
Jira key: `KAN-7` - Live and broker import-side-effect quarantine.

Specifications read and applied:
- `AGENTS.md`
- `PLANS.md`
- `PROJECT_SPEC.md`
- `DATA_CONTRACT.md`
- `DOMAIN_RULES.md`
- `ACCEPTANCE_CRITERIA.md`

The historical KAN-1 migration backlog lists the same quarantine scope as KAN-10. This implementation follows the approved current Jira key, KAN-7, without rewriting the historical audit.

Acceptance trace:
- Imports initialize no broker and perform no broker API action.
- Imports read no execution-plan or live-data file.
- `MetaTrader5` is an optional dependency loaded only at an explicit live boundary.
- Dry-run is the default and makes no broker calls.
- Live execution requires explicit opt-in and declared spread, slippage, commission, fill-policy, and trade-log evidence.
- Mock-based tests cover import safety and execution gates.

## 3. Current-State Evidence
- `mt5_executor.py` imports `MetaTrader5`, calls `initialize()`, reads an absolute execution-plan CSV path, selects a symbol, submits pending orders, and shuts down at module import time.
- `live_data_server.py` enters an infinite loop at import time, reads local CSV files, and writes `live_prices.json`.
- `MetaTrader5` is not declared in package metadata, while the repository must remain locally usable without broker software.
- `pipelines/legacy/11_execution.py` contains hard-coded absolute input and output paths inside its script entrypoint; its analytical calculation is otherwise import-safe.
- The current Python 3.11 CI installs `.[test]` and runs `python -m pytest -q`.
- The baseline branch is `origin/main` at `aadf27c`.

## 4. Assumptions and Domain Questions
Implementation assumptions:
- Pending-order submission is the only currently supported broker mutation; modification and cancellation remain unsupported rather than being added in this quarantine.
- A live request must satisfy both `dry_run=False` and an explicit live-execution opt-in flag.
- Governance requires declared execution-cost/fill evidence before any broker initialization. Configuration presence is a safety gate, not a claim that the evidence is valid.
- File loading is allowed only after an explicit function or CLI invocation.

Market hypotheses: none. This change does not create analytical labels, probabilities, fills, costs, or readiness claims.

Unresolved domain question for human review:
- A later, separately approved design must define how spread, slippage, commission, fill-policy, and trade-log evidence are validated against broker/account behavior before production use.

## 5. Proposed Architecture
- Keep `mt5_executor.py` importable without `MetaTrader5` by loading the package lazily inside an adapter used only after all live gates pass.
- Represent execution settings with a typed immutable configuration whose default is dry-run.
- Separate plan loading, request construction, gate validation, dry-run preview, and broker submission.
- Accept an injected broker protocol so tests use mocks exclusively.
- Put live data-server polling behind explicit functions and a guarded CLI entrypoint.
- Keep legacy execution calculations unchanged while replacing absolute CLI paths with arguments.

## 6. File-Level Change Map
Create:
- `plans/KAN-7-live-broker-quarantine.md`
- `tests/test_live_broker_quarantine.py`

Modify:
- `mt5_executor.py`
- `live_data_server.py`
- `pipelines/legacy/11_execution.py`
- `pyproject.toml`

Leave untouched:
- analytical engines and signal definitions
- all datasets and generated market artifacts
- credentials and account configuration

## 7. Implementation Steps
1. Record the approved scope, evidence, assumptions, and verification plan here before code changes.
2. Replace import-time MT5 behavior with typed configuration, lazy optional loading, request preparation, and explicit execution functions.
3. Guard live-data polling and remove absolute execution script paths through explicit CLI arguments.
4. Declare a separate live-broker dependency extra.
5. Add mock-based import-safety, optional-dependency, dry-run, and live-gate tests.
6. Run the full local pytest suite and static repository checks.
7. Commit and push the scoped files, open the required draft PR, wait for GitHub Actions, and stop for human review.

## 8. Verification
Planned checks:
- `python --version`
- `python -m pip install -e ".[test]"`
- `python -m pytest -q`
- focused mock tests for import safety and execution gates
- import with `MetaTrader5` unavailable
- `rg` checks for MT5 import-time calls and hard-coded absolute paths in changed live/execution surfaces
- `git diff --check`
- GitHub Actions status for the pushed commit and draft PR

No test may connect to MT5 or invoke a real broker implementation.

## 9. Data and Migration Impact
No schemas, timestamps, market bars, raw datasets, manifests, or analytical outputs are changed. Existing execution-plan CSV columns remain compatible. Script users must now pass plan/input/output paths explicitly instead of relying on a developer-specific absolute path.

Rollback is a normal revert of this commit. No data migration or destructive cleanup is required.

## 10. Risks and Limitations
- This quarantine reduces accidental execution risk but does not establish live-trading readiness.
- No broker, spread, slippage, commission, fill, or trade-log evidence will be observed during verification.
- Mock success cannot establish compatibility with a real terminal or account.
- Look-ahead, repainting, survivorship, timezone/DST, and analytical-engine behavior are unchanged and outside this slice.
- The optional MT5 package is platform-dependent and is intentionally excluded from default and CI installation.

## 11. Progress Log
- 2026-07-17: Confirmed `gh` 2.96.0 is authenticated as `0022249141`.
- 2026-07-17: Created isolated worktree on `KAN-7-live-broker-quarantine`, tracking the remote branch at `aadf27c`.
- 2026-07-17: Read all required governance files and inspected current live/broker surfaces.
- 2026-07-17: Created this plan as the first tracked repository edit.
- 2026-07-17: Replaced import-time MT5 execution with a typed, dry-run-first, lazily loaded broker boundary.
- 2026-07-17: Moved live-data polling behind explicit functions and a guarded CLI entrypoint.
- 2026-07-17: Removed absolute paths from the legacy execution-plan CLI without changing its analytical calculation.
- 2026-07-17: Added the optional `live-broker` dependency extra and seven mock-only quarantine tests.
- 2026-07-17: Completed clean-environment and full-suite local verification.
- 2026-07-17: Committed implementation as `033ee54`, pushed the branch, and opened draft PR #24 with the required title.
- 2026-07-17: Both GitHub Actions `pytest` checks for implementation head `033ee54` passed in 23 and 35 seconds.

## 12. Completion Evidence
Command and result ledger:

| Command | Result |
| --- | --- |
| `gh --version; gh auth status` | Initial failure: the newly installed CLI was not yet on this PowerShell process's `PATH`. No repository state changed. |
| `& 'C:\Program Files\GitHub CLI\gh.exe' --version; & 'C:\Program Files\GitHub CLI\gh.exe' auth status` | Passed: `gh` 2.96.0, authenticated as `0022249141`. |
| `git fetch origin --prune` | Passed. |
| `git worktree add -b KAN-7-live-broker-quarantine ... origin/KAN-7-live-broker-quarantine` | Passed; branch tracks the remote KAN-7 branch. |
| `Get-Content -Raw` for all required governance files | Passed; all specifications were read before implementation. |
| `python --version` | Passed: Python 3.11.9. |
| `python -m compileall -q mt5_executor.py live_data_server.py pipelines\legacy\11_execution.py tests\test_live_broker_quarantine.py` | Passed. |
| `python -m venv .venv` | Passed. |
| `.\.venv\Scripts\python.exe -m pip install --upgrade pip` | Passed: pip upgraded to 26.1.2. |
| `.\.venv\Scripts\python.exe -m pip install -e ".[test]"` | Passed; the default/test environment did not install MetaTrader5. |
| `.\.venv\Scripts\python.exe -m pytest -q tests\test_live_broker_quarantine.py` | Passed: 7 tests. |
| `.\.venv\Scripts\python.exe -m pytest -q` | Passed: 24 tests. |
| `.\.venv\Scripts\python.exe -m pytest -q` after final test tightening | Passed: 24 tests in 1.39 seconds. |
| `.\.venv\Scripts\python.exe -m pip check` | Passed: no broken requirements. |
| `git diff --check` | Passed. |
| `rg` absolute-path scan over changed runtime/test surfaces | Passed: no matches. |
| `git commit -m "KAN-7 quarantine live and broker side effects"` | Passed: implementation commit `033ee54`. |
| `git push -u origin KAN-7-live-broker-quarantine` | Passed. |
| `gh pr create --draft ...` | Passed: draft PR #24, titled `KAN-7 Quarantine live and broker import side effects`. |
| `gh pr checks 24 --watch --interval 10` | Passed for implementation head: both Python 3.11 `pytest` checks succeeded in 23 and 35 seconds. |

Acceptance status:
- Import safety: passed with mocked CSV reads, file writes, polling sleep, MT5 initialization, symbol selection, order submission, modification, cancellation, and shutdown.
- Optional dependency: passed; dry-run does not load MetaTrader5 and an eligible live request reports a clear optional-dependency error when it is unavailable.
- Execution gates: passed; dry-run is default, live mode needs a separate opt-in, and missing execution-readiness evidence blocks access before broker initialization.
- Broker/data safety: no broker connection was attempted, no real broker implementation was loaded, no order was sent/modified/cancelled, and no dataset was changed.
- GitHub publication: implementation commit pushed and draft PR #24 opened; both implementation-head Actions checks passed.
