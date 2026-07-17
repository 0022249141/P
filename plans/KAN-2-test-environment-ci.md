# KAN-2 Test Environment and CI Plan

## 1. Objective

Repair the repository's Python 3.11 test baseline so a clean checkout can install test dependencies, collect pytest tests safely, and run a minimal CI workflow without relying on the committed `venv/`.

This is an environment and test-collection slice only. It does not refactor analytical engines, delete datasets, move modules, or change market definitions.

## 2. Jira and Specification Trace

Jira/backlog key: `KAN-2`, "Repair Test Environment and CI Baseline".

Source backlog: `docs/audits/migration-backlog.md`.

Specifications read and applied:

- `AGENTS.md`
- `PLANS.md`
- `PROJECT_SPEC.md`
- `DATA_CONTRACT.md`
- `DOMAIN_RULES.md`
- `ACCEPTANCE_CRITERIA.md`

KAN-2 acceptance criteria:

- `python -m pip install -e ".[test]"` succeeds in a fresh environment.
- `python -m pytest -q` runs without import-time file reads from missing `data/`.
- CI uses Python 3.11 and installs project/test dependencies.

## 3. Current-State Evidence

From KAN-1 audit:

- `pytest` was not installed in the active Python or committed `venv/`.
- `pyproject.toml` declares Python `>=3.10`, while `AGENTS.md` requires Python `>=3.11`.
- `.github/workflows/pylint.yml` uses Python 3.10, installs only `pylint`, and runs broad `pylint .`.
- Some pytest-discoverable files execute path mutation, prints, or data loading at import time.
- Many scripts refer to a `data/` path that is not the committed data layout.

Initial KAN-2 branch state:

- Branch: `KAN-2-test-environment-ci`
- Base: `origin/main` at merge commit `af368be3d1241ca8d4c604bd6950a67188541d37`
- Worktree: `C:\Users\pouria.sl\Documents\GitHub\P-KAN-2-test-environment-ci`

## 4. Assumptions and Domain Questions

Implementation assumptions:

- The smallest coherent KAN-2 slice is package/test/CI metadata plus pytest collection safety.
- Test environment repair should not require removing the tracked `venv/`; that is KAN-3.
- Placeholder tests may be converted into harmless assertions when their previous behavior only printed.
- Data-dependent script-style tests should be guarded or skipped when required local data is absent.
- CI should prefer `python -m pytest -q` over broad linting until package boundaries are repaired.

Domain questions:

- None blocking. KAN-2 does not alter analytical labels, market data, execution logic, or report claims.

## 5. Proposed Architecture

Configuration boundaries:

- `pyproject.toml` is the canonical package and pytest configuration.
- `requirements.txt` remains a simple runtime compatibility list for now.
- `.github/workflows/pylint.yml` will be repaired or replaced with a Python 3.11 test workflow that installs project test extras before running pytest.
- Tests must be import-safe: collection should not require local `data/` files or trigger analytical runs at module import time.

Compatibility strategy:

- Keep public module interfaces unchanged.
- Do not relocate `src/`, `pipelines/legacy/`, or engines.
- Keep data paths untouched; skip or isolate tests that depend on non-existent local data.

## 6. File-Level Change Map

Planned create:

- `plans/KAN-2-test-environment-ci.md`

Planned modify:

- `pyproject.toml`
- `.github/workflows/pylint.yml`
- pytest-discoverable files that are unsafe during collection, likely under `tests/`
- documentation if needed for fresh environment setup

Planned leave untouched:

- Analytical engines under `src/`, `engines/`, `pipelines/legacy/`, and `smc_validation/`
- Committed datasets
- Generated artifacts
- Tracked `venv/` and `.vs/` cleanup targets

## 7. Implementation Steps

1. Create this execution plan first.
2. Inspect current package metadata, CI workflow, and pytest-discoverable tests.
3. Establish a fresh Python 3.11 virtual environment outside tracked `venv/`.
4. Update package/test dependency metadata for Python 3.11 and pytest.
5. Repair CI to install test extras and run pytest on Python 3.11.
6. Make pytest collection safe without changing analytical engine behavior.
7. Run installation and pytest commands from a fresh environment.
8. Record all command results and failures in this plan.
9. Commit, push, and open a draft PR.

## 8. Verification

Required commands:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
```

Additional checks as applicable:

```powershell
git diff --check
git status --short --branch
```

Results will be appended in the progress log and completion evidence sections.

## 9. Data and Migration Impact

No data files should be modified. No data layout migration is in scope.

Expected impact:

- Fresh test environments should no longer rely on committed `venv/`.
- Pytest collection should not require local `data/` files.
- CI should run against Python 3.11 with declared test dependencies.

Rollback:

- Revert this PR to restore previous package/test/CI behavior.
- No dataset or analytical output rollback should be required.

## 10. Risks and Limitations

- Look-ahead/repainting risks found in KAN-1 are not fixed here.
- Missing spread/fill data remains a blocker for execution-readiness claims.
- The tracked `venv/`, `.vs/`, and broken gitlink cleanup remains KAN-3.
- Some existing tests are placeholders; KAN-2 may make them runnable but does not provide full characterization coverage.
- CI may still be noisy if broad linting remains; preference is a minimal pytest baseline first.

## 11. Progress Log

2026-07-17:

- Created branch/worktree `KAN-2-test-environment-ci` from `origin/main`.
- Read repository governance files and KAN-2 backlog.
- Created this plan before other repository edits.
- Updated `pyproject.toml` to require Python `>=3.11`, align pandas/numpy floors with `requirements.txt`, declare `pytest>=7.4`, and restrict pytest discovery to `test_*.py`.
- Replaced the broken broad pylint workflow with a Python 3.11 pytest workflow that installs `.[test]`.
- Added fresh environment setup commands to `README.md`.
- Reworked `tests/test_layer1_2.py` so pytest collection no longer reads from a local `data/` directory at import time.
- Created a fresh `.venv` and verified install/test commands.

## 12. Completion Evidence

Commands run on 2026-07-17:

| Command | Result |
| --- | --- |
| `python --version` | Passed: `Python 3.11.9`. |
| `git diff --check` | Passed after implementation edits. |
| `python -m venv .venv` | Passed. |
| `.\.venv\Scripts\python.exe -m pip install --upgrade pip` | Passed; upgraded pip from `24.0` to `26.1.2`. |
| `.\.venv\Scripts\python.exe -m pip install -e ".[test]"` | Passed; installed editable `smc-validation-0.1.0` with `pytest-9.1.1`, `pandas-3.0.3`, `numpy-2.4.6`, and `pydantic-2.13.4`. |
| `.\.venv\Scripts\python.exe -m pytest -q` | Passed: `17 passed in 9.26s`. |

Changed files:

- `.github/workflows/pylint.yml`
- `README.md`
- `plans/KAN-2-test-environment-ci.md`
- `pyproject.toml`
- `tests/test_layer1_2.py`

Acceptance-criteria status:

- `python -m pip install -e ".[test]"` succeeds in a fresh environment: complete.
- `python -m pytest -q` runs without import-time file reads from missing `data/`: complete.
- CI uses Python 3.11 and installs project/test dependencies: complete.

Draft PR URL: recorded in the PR body and final handoff after creation.
