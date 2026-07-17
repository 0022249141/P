# KAN-10 Canonical Data Quality Gates Plan

## 1. Objective
Build the first governed, installable canonical market-data pipeline with typed, serializable contracts; operational G0-G5 validation; deterministic normalization, resampling, and reconciliation; and an auditable eligibility guard that blocks downstream callbacks unless every required gate passes.

## 2. Jira and Specification Trace
Jira key: `KAN-10` - Canonical data quality gates.

Specifications and prior controls read before implementation:
- `AGENTS.md`
- `PLANS.md`
- `PROJECT_SPEC.md`
- `DATA_CONTRACT.md`
- `DOMAIN_RULES.md`
- `ACCEPTANCE_CRITERIA.md`
- `docs/architecture/current-to-target-map.md`
- `docs/audits/migration-backlog.md`
- `docs/data/fixture-policy.md`
- `plans/KAN-9-dataset-manifest-fixture-policy.md`

The historical KAN-1 migration backlog describes governed resampling and data gates as KAN-8. This implementation follows the currently approved Jira key KAN-10 without rewriting historical audit records.

Acceptance trace:
- Typed, versioned G0-G9 contracts serialize deterministically.
- G0-G5 have real evaluators when their required evidence is supplied.
- G6-G9 remain explicitly `NOT_EVALUATED`; no absence of checks becomes `PASS`.
- Unknown timezone or timestamp-period semantics blocks canonical UTC output.
- Normalization reports invalid input without silently dropping rows or resolving duplicates.
- Resampling and reconciliation are explicit, deterministic, and fixture-backed.
- Eligibility requires every requested gate to be uniquely present and `PASS` before a callback runs.
- Ordinary tests use synthetic/in-memory data and remain independent of protected research CSVs.
- Protected datasets and the committed KAN-9 manifest remain byte-identical.

## 3. Current-State Evidence
Baseline ref: `origin/main` / `origin/KAN-10-canonical-data-quality-gates` at `3eded49f5ba9d91a87da8a8af2efb37cdaf7806e`.

Worktree evidence:
- Isolated sibling: `P-KAN-10-canonical-data-quality-gates`.
- Existing branch tracks the existing remote branch and is clean.
- The dirty primary checkout and every prior Jira worktree remain untouched.
- No existing PR targets the KAN-10 branch.

Protected dataset baseline, independently recomputed from sorted tracked paths and full SHA-256 values:
- CSV paths: 56.
- Bytes: 90,960,790.
- Aggregate SHA-256: `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`.
- Committed manifest SHA-256: `4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`.

Fresh Python baseline:
- Python: 3.11.9.
- Editable install `.[test]`: passed in a new ignored `.venv`.
- Ordinary pytest: 55 passed, 1 research test deselected in 13.93 seconds.
- Explicit research pytest: 1 passed in 0.02 seconds.

Current implementation evidence:
- `pipelines/` exists but is not included by the current setuptools package discovery.
- There is no governed canonical package or G0-G9 gate contract.
- `core/dataset_manifest.py` is the versioned KAN-9 manifest contract and must be reused for G0 constants and record semantics.
- KAN-9 CI already prevents duplicate corpus reads: hygiene uses skip mode, manifest verification reads the corpus once, and ordinary pytest excludes research tests.

## 4. Assumptions and Domain Questions
Implementation assumptions:
- The core API consumes a `pandas.DataFrame` or an explicit in-memory wrapper carrying parser diagnostics; repository paths are not the normalization interface.
- Source row numbers are deterministic zero-based input positions and are preserved separately from the six-column canonical output.
- Canonical output requires timezone evidence and explicit period-start/period-end semantics. Naive timestamps with unknown timezone are blocked.
- Explicit IANA timezone localization uses configured ambiguous and nonexistent DST policies; default `RAISE` reports the condition without repair.
- Validation-only is the default. No invalid row is dropped, no duplicate is resolved, and no ordering is silently changed.
- Duplicate policies are versioned. `REJECT` is default; non-reject behavior is only permitted in explicit repair mode and must emit repair records preserving all source row identities.
- Unknown price units and volume meaning remain `UNKNOWN`; they are not promoted from filename, market, or numeric shape.
- A strictly-positive-price rule is optional and disabled unless explicitly declared by dataset policy.
- G4 interval diagnostics can run with an explicit expected interval. Session/calendar claims require a supplied versioned calendar policy; otherwise calendar-specific eligibility is blocked or limited.
- Canonical resampling accepts validated UTC bars and a fully explicit policy. Continuous-calendar behavior is distinct from a versioned session calendar.
- Decimal conversion from string plus explicit absolute/relative tolerances is sufficient for deterministic reconciliation comparisons.

Unresolved domain questions intentionally left blocked:
- The repository does not declare broker/source timezone, trading sessions, DST interpretation, period label semantics, price units, or volume meaning for committed datasets.
- No market-specific positivity rule, holiday calendar, session boundary, or incomplete-bar oracle is available.
- No G6 feature reproducer, G7 analytical evaluator, G8 statistical evaluator, or G9 execution/backtest evaluator is approved in KAN-10.
- These unknowns are emitted as `UNKNOWN`, `BLOCKED`, or `NOT_EVALUATED`, never inferred from market or filename.

## 5. Proposed Architecture
Create the installable `pipelines.canonical` package:

```text
pipelines/canonical/
  __init__.py
  contracts.py
  normalization.py
  quality.py
  resampling.py
  reconciliation.py
  eligibility.py
```

Dependency direction:
- `contracts.py` depends only on Python/Pydantic and owns immutable versioned payloads and canonical JSON serialization.
- `normalization.py` depends on contracts plus pandas and evaluates G1-G3 from in-memory tables.
- `quality.py` composes G0, G4, placeholder G5-G9 records, and normalization results into one deterministic report. G0 imports KAN-9 manifest constants rather than cloning its schema.
- `resampling.py` consumes eligible canonical UTC tables plus explicit resampling policy.
- `reconciliation.py` compares supplied HTF bars with deterministic Decimal-based tolerances and emits G5 evidence.
- `eligibility.py` is the only downstream guard surface and has no analytical-engine dependency.
- `__init__.py` exports typed public interfaces without reading files or creating output.

Deterministic outputs contain no wall-clock timestamp, hostname, username, absolute path, random identifier, or implicit pandas option. Findings and examples are stably sorted and bounded.

## 6. File-Level Change Map
Create:
- `plans/KAN-10-canonical-data-quality-gates.md`
- `pipelines/canonical/__init__.py`
- `pipelines/canonical/contracts.py`
- `pipelines/canonical/normalization.py`
- `pipelines/canonical/quality.py`
- `pipelines/canonical/resampling.py`
- `pipelines/canonical/reconciliation.py`
- `pipelines/canonical/eligibility.py`
- focused canonical contract, normalization, quality, resampling, reconciliation, eligibility, import-safety, and determinism tests
- concise canonical pipeline documentation if behavior needs detail beyond this living plan

Modify:
- `pyproject.toml` to include the intentional `pipelines*` package surface
- CI only if a lightweight import/verification command adds coverage beyond ordinary pytest

Leave untouched:
- `pipelines/legacy/01_fix_data.py`
- `pipelines/legacy/02_resample_mtf.py`
- `pipelines/legacy/06_quality_check.py`
- analytical, backtest, reporting, and live/broker engines
- `raw_data/`, `data_clean/`, `data_features/`
- `data/manifests/committed_datasets.json`

## 7. Implementation Steps
1. Record baseline, assumptions, architecture, legacy characterization, and verification controls in this plan as the first tracked edit.
2. Add immutable Pydantic contracts, enums, bounded evidence structures, deterministic serialization, and explicit policy models.
3. Implement validation-only canonicalization and G1-G3 with timezone/DST, duplicate, numeric, geometry, and provenance-preserving diagnostics.
4. Implement KAN-9-backed G0 and explicit interval/calendar G4; compose stable G0-G9 reports with G6-G9 not evaluated.
5. Implement deterministic M1 resampling for M5/M15/M30/H1/H4/D1 with complete policy persistence and incomplete-bin handling.
6. Implement Decimal-safe HTF reconciliation and G5 result production.
7. Implement eligibility evaluation and callback execution guard.
8. Add import-safety, required synthetic scenarios, determinism reruns, and ordinary/research separation tests.
9. Run all local verification in the fresh Python 3.11 environment and independently recompute protected-data evidence.
10. Commit and push the existing branch, open one draft PR with the required title/body, wait for GitHub Actions, and stop for human review without merging.

## 8. Verification
Required local checks:
- protected dataset count, bytes, aggregate SHA-256 before and after
- committed manifest SHA-256 before and after
- manifest generator twice with unchanged second run
- `python scripts/verify_dataset_manifest.py`
- `python scripts/verify_git_hygiene.py --skip-dataset-integrity`
- import-safety test for every new canonical module
- focused canonical/gate/resampling/reconciliation/eligibility tests
- deterministic canonical frame, gate report, resampling, and reconciliation reruns with byte-identical output
- ordinary `python -m pytest -q`
- explicit `python -m pytest -q -m research tests/research`
- `python -m pip check`
- `git diff --check`
- editable package import from outside the repository root
- GitHub Actions on the draft PR head

No ordinary test may open a protected dataset. All required market-data fixtures are tiny, deterministic, and in memory or temporary files.

## 9. Data and Migration Impact
There is no committed dataset migration. Canonical output exists only in memory and is distinct from immutable inputs. No source CSV, clean/features CSV, path, line ending, or committed manifest record is changed.

The only package migration is exposing the existing `pipelines` namespace and its new canonical subpackage through setuptools. Legacy modules remain present and are not imported or called by canonical code.

Rollback is a normal revert of the KAN-10 commit. No history rewrite, force push, generated dataset rebuild, or engine migration is involved.

## 10. Risks and Limitations
- Timestamp correctness depends on supplied timezone and DST policy; unknown semantics block output.
- Calendar gap detection cannot prove market-session completeness without a versioned calendar.
- OHLCV cannot establish broker provenance, real volume, order flow, spread, fills, dealer intent, or execution readiness.
- Decimal-safe comparison does not make source prices exact; tolerance values remain explicit configuration.
- Duplicate repair can alter research samples, so validation-only REJECT remains the default and repair output is separately audited.
- G6-G9 are deliberately not evaluated and therefore block profiles requiring them.
- No analytical engine consumes this API in KAN-10, so integration risk is deferred rather than hidden.
- Look-ahead, repainting, survivorship, costs, and proxy limitations in analytical engines remain unchanged because those engines are untouched.

### Legacy Compatibility and Behavior Table

| Legacy surface | Observed legacy behavior | Canonical KAN-10 behavior |
| --- | --- | --- |
| `01_fix_data.py` timestamp parsing | Uses coercion and silently drops unparseable timestamps. | Reports affected source rows; validation-only mode emits no canonical output. |
| `01_fix_data.py` numeric parsing | Coerces and silently drops invalid numeric rows. | Reports each category with bounded examples; no silent drop. |
| `01_fix_data.py` duplicates | Silently keeps the last timestamp. | Defaults to explicit `REJECT`; repair requires requested mode and audit records. |
| `01_fix_data.py` persistence | Creates/writes configured filesystem directories and files. | Core API is in-memory and performs no file output. |
| `02_resample_mtf.py` timezone | Hardcodes `Asia/Tehran` for named markets. | Requires explicit IANA timezone evidence; never infers from market name. |
| `02_resample_mtf.py` session | Hardcodes 09:00-22:00 for two market labels. | Requires a supplied versioned calendar/session policy. |
| `02_resample_mtf.py` pandas behavior | Relies on resample defaults and drops NaN bins. | Persists label, closed, origin, interval, calendar, incomplete-bin, and volume policies. |
| `06_quality_check.py` orchestration | Reads script files and executes them with `exec()`. | Imports typed functions normally; no script execution or import-time I/O. |

Legacy behavior is documented as evidence, not preserved as correctness. Canonical modules do not call these legacy functions.

## 11. Progress Log

| Date | Command or activity | Result |
| --- | --- | --- |
| 2026-07-17 | `git fetch origin` | Passed; discovered the existing KAN-10 remote branch and updated `origin/main` to the required base. |
| 2026-07-17 | Branch/base comparison | Passed; KAN-10, `origin/main`, and required base all resolve to `3eded49f5ba9d91a87da8a8af2efb37cdaf7806e`. |
| 2026-07-17 | `git worktree add --track -b KAN-10-canonical-data-quality-gates ...` | Passed; attached the existing remote branch to an isolated sibling worktree. |
| 2026-07-17 | Governance and architecture review | Read all required specifications, KAN-9 controls, current-to-target map, and migration backlog. |
| 2026-07-17 | Independent protected-data hash calculation | Passed: 56 CSVs, 90,960,790 bytes, aggregate `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`. |
| 2026-07-17 | `Get-FileHash data/manifests/committed_datasets.json` | Passed: `4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`. |
| 2026-07-17 | Legacy source review | Confirmed silent drops, keep-last deduplication, output writes, hardcoded Tehran/session assumptions, pandas defaults, and `exec()` orchestration. |
| 2026-07-17 | Existing PR lookup | Passed: no PR exists for the KAN-10 head branch. |
| 2026-07-17 | `python --version` | Passed: Python 3.11.9. |
| 2026-07-17 | `python -m venv .venv` | Passed: fresh ignored environment created. |
| 2026-07-17 | `.venv` pip upgrade | Passed: pip 26.1.2. |
| 2026-07-17 | `.venv` `python -m pip install -e ".[test]"` | Passed in 121.4 seconds. |
| 2026-07-17 | Baseline ordinary pytest | Passed: 55 tests, 1 research test deselected in 13.93 seconds. |
| 2026-07-17 | Baseline explicit research pytest | Passed: 1 test in 0.02 seconds. |
| 2026-07-17 | Created this plan | First tracked edit; implementation pending. |
| 2026-07-17 | Added `pipelines.canonical` contracts and pure in-memory APIs | Completed G0-G5 contracts/evaluators, deterministic serialization, explicit resampling, reconciliation, and eligibility guard. |
| 2026-07-17 | First focused canonical test run | Failed: 17 failed, 28 passed. Causes were an over-broad import-safety read guard, duplicate-row index assumptions, and pandas 3 datetime storage-unit assumptions. |
| 2026-07-17 | Second focused canonical test run | Failed: 1 failed, 44 passed. Remaining cause was editable-install `.egg-info` metadata read by the import system. |
| 2026-07-17 | Import-safety guard correction | Passed: allowed Python/package loader metadata while continuing to block application file, CSV, output, and network access. |
| 2026-07-17 | Expanded focused canonical tests | Passed: 54 tests in 2.64 seconds. Required fixture scenarios, determinism reruns, import safety, and semantic evidence constraints are covered. |
| 2026-07-17 | Final `.venv` `python -m pip install -e ".[test]"` | Passed; rebuilt and installed the editable package with `pipelines*` included. |
| 2026-07-17 | Editable import outside repository root | Passed; `pipelines.canonical` resolved to the isolated worktree package without `pythonpath` or `sys.path` mutation. |
| 2026-07-17 | Final ordinary `python -m pytest -q` | Passed: 109 tests, 1 research test deselected in 9.24 seconds. |
| 2026-07-17 | Final explicit `python -m pytest -q -m research tests/research` | Passed: 1 test in 0.06 seconds. |
| 2026-07-17 | Manifest generator pass 1 | Passed: unchanged, 56 records. |
| 2026-07-17 | Manifest generator pass 2 | Passed: unchanged, 56 records; zero second-run diff. |
| 2026-07-17 | `python scripts/verify_dataset_manifest.py` | Passed. |
| 2026-07-17 | `python scripts/verify_git_hygiene.py --skip-dataset-integrity` | Passed: no forbidden paths, gitlinks, ignore failures, or submodule errors. |
| 2026-07-17 | Independent protected-data after-check | Passed: 56 CSVs, 90,960,790 bytes, aggregate `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`; no non-CSV protected paths. |
| 2026-07-17 | Committed manifest after-check | Passed: SHA-256 remains `4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`. |
| 2026-07-17 | Final `python -m pip check` | Passed: no broken requirements. |
| 2026-07-17 | `git diff --cached --check` | Passed with all created and modified files staged. |

## 12. Completion Evidence
Implemented interfaces:
- `pipelines.canonical` is installable and exports strict versioned contracts, in-memory canonicalization, G0-G4 quality composition, deterministic M1-to-HTF resampling, G5 reconciliation, and callback eligibility enforcement.
- G0-G5 produce operational results when their required evidence is supplied. G5 is `NOT_EVALUATED` when no supplied HTF comparison exists.
- G6-G9 are always present and default to `NOT_EVALUATED`; no evaluator or engine wiring was added.
- Canonical, report, resampling, and reconciliation rerun tests compare byte-identical serialized outputs.

Acceptance status:
- Required typed contracts, bounded findings, explicit policies, synthetic fixtures, import safety, determinism, and eligibility blocking: satisfied.
- Protected datasets and committed manifest: byte-identical before and after.
- Analytical, backtest, reporting, live/broker, and legacy surfaces: unchanged and not wired.
- Local verification: passed as recorded above.
- `git diff --check`: passed.
- Commit/push, draft PR creation, and GitHub Actions: pending publication steps; their results will be reported in the PR and final response so no post-success documentation commit retriggers CI.
