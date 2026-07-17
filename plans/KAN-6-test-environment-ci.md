# KAN-6 Test Environment and CI Plan

## 1. Objective
Repair the repository's Python 3.11 test baseline so a clean checkout can install test dependencies, collect pytest tests safely, and run a minimal CI workflow without relying on the committed `venv/`.

This is an environment and test-collection slice only. It does not refactor analytical engines, delete datasets, move modules, or change market definitions.

## 2. Jira and Specification Trace
Jira key: `KAN-6` — Repair Test Environment and CI Baseline.

Source backlog: `docs/audits/migration-backlog.md`.

Specifications read and applied:
- `AGENTS.md`
- `PLANS.md`
- `PROJECT_SPEC.md`
- `DATA_CONTRACT.md`
- `DOMAIN_RULES.md`
- `ACCEPTANCE_CRITERIA.md`

Acceptance criteria:
- `python -m pip install -e ".[test]"` succeeds in a fresh environment.
- `python -m pytest -q` runs without import-time reads from missing `data/`.
- CI uses Python 3.11 and installs project/test dependencies.

## 3. Current-State Evidence
From the KAN-1 audit:
- `pytest` was absent from the active Python and committed `venv/`.
- `pyproject.toml` required Python `>=3.10`, while repository governance requires Python `>=3.11`.
- `.github/workflows/pylint.yml` used Python 3.10, installed only pylint, and ran broad `pylint .`.
- Some pytest-discoverable files performed path mutation, printing, or data loading during import.
- Several scripts referred to a `data/` path that is not the committed dataset layout.

Corrected traceability branch:
- Branch: `KAN-6-test-environment-ci`
- Base: `origin/main` at `af368be3d1241ca8d4c604bd6950a67188541d37`
- Implementation inherited from the reviewed KAN-2-named branch and re-keyed before merge.

## 4. Assumptions
- The smallest coherent slice is package/test/CI metadata plus pytest collection safety.
- Removing tracked `venv/`, `.vs/`, and the broken gitlink remains separate hygiene work.
- No analytical labels, market data, execution logic, or report claims are changed.

## 5. Design
- `pyproject.toml` is the canonical package and pytest configuration.
- Test dependencies are installed with `.[test]`.
- CI uses Python 3.11 and runs `python -m pytest -q`.
- Pytest discovery is restricted to `test_*.py`.
- Tests must not read local market data or trigger analytical runs at collection time.

## 6. Files Changed
- `.github/workflows/pylint.yml`
- `README.md`
- `pyproject.toml`
- `tests/test_layer1_2.py`
- `plans/KAN-6-test-environment-ci.md`

No analytical engines or datasets were changed.

## 7. Verification
Commands executed in a fresh Python 3.11 environment:

| Command | Result |
| --- | --- |
| `python --version` | Passed: Python 3.11.9 |
| `python -m venv .venv` | Passed |
| `.\.venv\Scripts\python.exe -m pip install --upgrade pip` | Passed |
| `.\.venv\Scripts\python.exe -m pip install -e ".[test]"` | Passed |
| `.\.venv\Scripts\python.exe -m pytest -q` | Passed: 17 tests |
| `git diff --check` | Passed |

GitHub Actions also completed successfully for the implementation head.

## 8. Risks and Limitations
- Look-ahead and repainting findings remain unresolved.
- Placeholder tests do not yet provide full characterization coverage.
- Live/broker execution remains out of scope and must be quarantined separately.
- Tracked environment and IDE artifacts remain for later cleanup.

## 9. Completion Evidence
- Fresh editable install succeeds.
- Pytest collection is safe from missing local market-data paths.
- All 17 tests pass locally.
- CI runs on Python 3.11 and passes.
- No engine refactor, dataset movement, or merge to `main` occurred during implementation.
