# KAN-1 Packaging and Dependency Audit

## Scope

This audit covers `pyproject.toml`, `requirements.txt`, package discovery, installability checks, CI assumptions, and Windows-sensitive paths. It does not modify packaging metadata.

## Packaging Metadata

Current `pyproject.toml` facts:

| Setting | Current value | Audit note |
| --- | --- | --- |
| Build backend | `setuptools.build_meta` | Standard Python packaging path. |
| Project name | `smc-validation` | Names the validation package, not the full Institutional Trading Lab. |
| Python constraint | `>=3.10` | Conflicts with repository spec requiring Python `>=3.11`. |
| Runtime deps | `numpy>=1.23`, `pandas>=1.5`, `pydantic>=2.0` | Looser than `requirements.txt`; omits `scikit-learn` and `MetaTrader5`. |
| Optional test deps | `pytest>=7` | Not present in the active interpreter or committed `venv/`. |
| Console script | `smc-validate = smc_validation.cli:main` | Only declared CLI. |
| Package discovery | Include `smc_validation*`, `core*`, `engines*` | Excludes `pipelines`, `src`, and root modules. |

Setuptools discovery evidence:

```text
included: core, engines, smc_validation
all local packages: core, engines, pipelines, smc_validation, pipelines.legacy
```

Implication: installing the project exposes `core`, `engines`, and `smc_validation`, but not `pipelines.legacy`, `src/*`, or root scripts such as `pipelinerun_all.py`.

## Dependency Drift

| Dependency | Evidence | Status |
| --- | --- | --- |
| `numpy` | `pyproject.toml` requires `>=1.23`; `requirements.txt` requires `>=1.24.0`. | Version floor drift. |
| `pandas` | `pyproject.toml` requires `>=1.5`; `requirements.txt` requires `>=2.0.0`. | Version floor drift. |
| `pydantic` | Both require `>=2.0`. | Aligned. |
| `scikit-learn` | `requirements.txt` requires `>=1.3.0`; `src/ml_filter.py` imports `sklearn`. | Missing from package runtime deps. |
| `MetaTrader5` | `mt5_executor.py` imports `MetaTrader5`. | Missing from optional/live deps and should stay execution-gated. |
| `pytest` | Optional test dep only. | Needed for tests, but not installed in active Python or committed `venv/`. |

## Installability and Verification Evidence

Commands run on 2026-07-17 from branch `KAN-1-repository-audit`:

| Command | Result |
| --- | --- |
| `python --version` | Passed: `Python 3.11.9`. |
| `python -m pip --version` | Passed: `pip 26.1.2` under Python 3.11. |
| `python -m pip install . --dry-run --no-deps` | Passed: metadata built and pip reported `Would install smc-validation-0.1.0`. |
| `python -m compileall -q smc_validation core engines src pipelines` | Passed. |
| `python -m pytest -q` | Failed: `No module named pytest`. |
| `.\venv\Scripts\python.exe --version` | Passed: `Python 3.11.9`. |
| `.\venv\Scripts\python.exe -m pytest -q` | Failed: `No module named pytest`. |
| `.\venv\Scripts\python.exe -m pip list --format=freeze` | Failed inside pip with `ModuleNotFoundError: No module named 'pip._internal.operations.build'`. |

Interpretation:

- The package metadata is buildable in dry-run mode.
- The repository does not currently provide a working test environment from either the system Python or the committed `venv/`.
- The committed `venv/` is not a reliable reproducibility artifact and should not be used as the canonical environment.

## CI Audit

`.github/workflows/pylint.yml` observations:

| Line(s) | Finding | Risk |
| --- | --- | --- |
| 1-2 | Duplicate `name:` keys; line 1 has `name: - name: Run pylint`. | Ambiguous workflow metadata and likely accidental YAML content. |
| 16 | CI uses Python `3.10`. | Conflicts with `AGENTS.md` reference runtime Python `>=3.11`. |
| 18-21 | Installs only `pylint`. | Project dependencies are not installed before linting. |
| 23-25 | Runs `pylint .`. | Will include tracked `venv/`, data-adjacent scripts, generated files, and mixed experimental modules unless ignored. |

## Import and Packaging Boundaries

Observed import-path risks:

- 16 `sys.path.insert(...)` occurrences, mostly in `tests/` and runner scripts.
- Root modules import `src` modules by bare names after path mutation.
- `tests/test_layer1_2.py` imports and executes file loading at module import time.
- Package discovery excludes the very modules that many scripts import from `src/`.

This means a clean install of `smc-validation` is not equivalent to running the repository from its root.

## Windows and Cross-Platform Assumptions

| Evidence | Risk |
| --- | --- |
| `python 09_zone_scoring.py` and `src/New Python Source File.py` contain spaces in path names. | Awkward imports, quoting issues, and cross-platform command fragility. |
| Tracked `.vs/` and `venv/Scripts/*.exe`. | Windows-local state and binaries are committed. |
| `P` is a gitlink without `.gitmodules`. | Fresh checkouts and recursive operations fail or confuse users. |
| `transpose_matrix.sh` and `scripts/install-codex.sh`. | Shell scripts exist, but no cross-platform wrapper or documented runtime path. |
| Several scripts assume `data/` paths while tracked datasets are under `raw_data/`, `data_clean/`, and `data_features/`. | Examples and live scripts fail unless an untracked `data/` directory exists. |

## Packaging Recommendations

These should be separate PRs after KAN-1 approval:

1. Align Python runtime to `>=3.11` in package metadata and CI.
2. Split dependencies into runtime, test, research/ML, and live-broker extras.
3. Decide whether `pipelines` becomes installable now or remains legacy-only until characterized.
4. Add a fresh environment creation path and remove reliance on tracked `venv/`.
5. Replace path mutation with package imports after characterization tests protect current behavior.
6. Repair CI before enforcing lint broadly.
