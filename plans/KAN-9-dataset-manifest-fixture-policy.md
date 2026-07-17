# KAN-9 Dataset Manifest and Fixture Policy Plan

## 1. Objective
Create a deterministic, versioned manifest for every committed CSV under the protected dataset directories; add a read-only verifier and CI gate; and document a fixture policy that keeps ordinary unit tests independent of the full research corpus.

## 2. Jira and Specification Trace
Jira key: `KAN-9` - Dataset manifest and fixture policy.

Specifications and audits read before implementation:
- `AGENTS.md`
- `PLANS.md`
- `PROJECT_SPEC.md`
- `DATA_CONTRACT.md`
- `DOMAIN_RULES.md`
- `ACCEPTANCE_CRITERIA.md`
- `docs/audits/data-and-git-hygiene.md`
- `docs/audits/migration-backlog.md`
- `plans/KAN-8-repository-git-hygiene.md`

The historical migration backlog describes this dataset-manifest work as KAN-4. This implementation follows the approved current Jira key, KAN-9, without modifying the historical audit.

Acceptance trace:
- Each tracked CSV under `raw_data/`, `data_clean/`, and `data_features/` appears exactly once in a committed deterministic manifest.
- Hashes, bytes, row counts, ordered columns, timestamp coverage, duplicate timestamps, missing cells, classification, parser decisions, and explicitly evidence-qualified semantic metadata are recorded.
- A read-only verifier rejects missing, duplicate, stale, nonexistent, untracked, malformed, or nondeterministically serialized records.
- Fixture classes and pytest markers distinguish small test fixtures from integration and research datasets.
- CI performs one explicit manifest verification step.
- Protected dataset paths and bytes remain unchanged.

## 3. Current-State Evidence
Baseline ref: `origin/main` / `origin/KAN-9-dataset-manifest-fixture-policy` at `65e481f`.

Protected dataset baseline, independently computed from sorted tracked paths and full SHA-256 values:
- CSV paths: 56.
- Bytes: 90,960,790.
- Aggregate manifest SHA-256: `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`.
- All 56 observed headers are `timestamp,open,high,low,close,volume`.
- `rg` found no direct protected-dataset path reference in the current Python test suite.

The branch is clean and exactly aligned with `origin/main`. Work is isolated in the sibling worktree `P-KAN-9-dataset-manifest-fixture-policy`; the existing dirty checkout remains untouched.

## 4. Assumptions and Domain Questions
Implementation assumptions:
- Directory membership declares only the storage classification: `raw_data/` is RAW, `data_clean/` is CLEAN, and `data_features/` is FEATURE.
- Header shape and measured file properties are OBSERVED evidence.
- Market, symbol, and timeframe tokens extracted from filenames are INFERRED and remain unnormalized.
- Source, timezone, bar-period semantics, volume meaning, and price unit remain UNKNOWN unless repository evidence explicitly declares them.
- Row count excludes the header. Duplicate timestamp count counts occurrences after the first observed value. Missing-cell count counts blank CSV cells.
- Timestamp coverage records the first and last parseable timestamp in file order without asserting timezone or bar semantics.

Open domain limitations:
- Filenames do not prove broker/source identity, timezone, volume units, price units, or whether timestamps denote period open/close.
- Similar filename tokens do not prove two files represent the same market or symbol contract.
- No semantic normalization will be introduced without declared evidence.

## 5. Proposed Architecture
- `data/manifests/committed_datasets.json` is the deterministic versioned contract for committed protected CSVs. It contains no generation timestamp or machine-specific path.
- A small reusable manifest module performs tracked-file discovery, streaming CSV measurement, semantic evidence labeling, canonical JSON rendering, and validation.
- `scripts/generate_dataset_manifest.py` is the only writer and replaces the manifest atomically only when content changes.
- `scripts/verify_dataset_manifest.py` is read-only. It validates structure and enums, compares manifest paths to the Git index, rebuilds measured metadata, and requires byte-for-byte canonical output.
- Unit tests use tiny temporary CSVs. Full-corpus verification runs once as an explicit CI command, outside ordinary pytest tests.

## 6. File-Level Change Map
Create:
- `plans/KAN-9-dataset-manifest-fixture-policy.md`
- `data/manifests/committed_datasets.json`
- `docs/data/fixture-policy.md`
- `scripts/generate_dataset_manifest.py`
- `scripts/verify_dataset_manifest.py`
- focused manifest and fixture-policy tests using temporary files

Modify:
- `pyproject.toml` to register integration and research markers
- `.github/workflows/pylint.yml` to add one manifest verification step

Leave byte-for-byte untouched:
- every file under `raw_data/`
- every file under `data_clean/`
- every file under `data_features/`

## 7. Implementation Steps
1. Record this plan as the first tracked edit, including independent baseline evidence and semantic non-assumptions.
2. Implement deterministic manifest construction and canonical serialization with explicit schema/parser versions.
3. Implement a read-only verifier covering path set, tracked state, required fields, enums, content measurements, and deterministic bytes.
4. Generate the committed 56-record manifest twice and require the second generation to produce no diff.
5. Document fixture classes, register pytest markers, and add a source audit preventing ordinary unit tests from depending directly on protected research datasets.
6. Add focused temporary-file tests and exactly one CI manifest verification step.
7. Recompute protected-dataset paths, bytes, and aggregate SHA-256; then perform fresh Python 3.11 installation and full verification.
8. Commit, push the existing branch, open one draft PR with the required title, wait for GitHub Actions, and stop for human review.

## 8. Verification
Required checks:
- generator run twice, with no diff after the second run
- `python scripts/verify_dataset_manifest.py`
- `git diff --check`
- protected path-set, byte-count, and aggregate full-hash comparison
- `git diff -- raw_data data_clean data_features` is empty
- fresh Python 3.11 virtual environment
- fresh environment: `python -m pip install -e ".[test]"`
- fresh environment: `python -m pytest -q`
- fresh environment: `python -m pip check`
- GitHub Actions on the final draft PR head

Focused tests will use temporary small CSV files and will not repeatedly hash or parse the approximately 90 MB research corpus.

## 9. Data and Migration Impact
There is no dataset migration. The manifest describes existing committed files and does not alter their bytes, paths, line endings, schemas, or timestamps. Rollback is a normal revert of the KAN-9 commit; no history rewrite is involved.

## 10. Risks and Limitations
- Manifest generation validates observed structure and content integrity, not market truth or broker provenance.
- UNKNOWN semantic fields are intentional safety signals, not missing implementation work.
- Filename-derived labels are INFERRED and must not be promoted to DECLARED or OBSERVED evidence downstream.
- Full verification necessarily reads the protected corpus once per verifier invocation; ordinary unit tests remain corpus-free.
- No analytical engine, result output, external service, credential, dataset, or Git history is changed.

## 11. Progress Log
- 2026-07-17: Confirmed the existing KAN-9 branch is clean, matches `origin/main`, and has no existing pull request.
- 2026-07-17: Created and selected the isolated sibling worktree without modifying the dirty primary checkout.
- 2026-07-17: Read all required governance, audit, and KAN-8 plan files.
- 2026-07-17: Independently recorded the 56-file, 90,960,790-byte protected dataset baseline and aggregate SHA-256.
- 2026-07-17: Confirmed one canonical observed header and no current direct test dependency on protected paths.
- 2026-07-17: Created this plan as the first tracked edit.
- 2026-07-17: Implemented deterministic manifest measurement, generation, canonical serialization, and read-only verification.
- 2026-07-17: Added the fixture policy, pytest marker registration, protected-path source audit, focused temporary-file tests, and one CI manifest gate.
- 2026-07-17: Generated the 56-record manifest twice; the second run was unchanged and byte-identical.
- 2026-07-17: Completed fresh Python 3.11 installation, full pytest, dependency, hygiene, and dataset-integrity checks.

## 12. Command and Failure Ledger

| Command | Result |
| --- | --- |
| `git status --short --branch` | Passed: clean existing KAN-9 branch tracking its remote branch. |
| `git rev-parse HEAD` and `git rev-parse origin/main` | Passed: both `65e481f7ec3b77f9764f34a3006b3f49276b2e9d`. |
| Independent sorted protected-file SHA-256 calculation | Passed: 56 paths, 90,960,790 bytes, aggregate `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`. |
| Header inventory for tracked protected CSVs | Passed: all 56 have canonical OHLCV header order. |
| `rg -n --glob "*.py" "(?:raw_data|data_clean|data_features)[/\\\\]" tests` | Returned exit 1 with no output, meaning no matches were found. |
| `python -m pytest tests/test_dataset_manifest.py tests/test_fixture_policy.py -q` using system Python | Failed before collection: the Python 3.11 installation has no `pytest` module. A fresh project virtual environment is required and will be used for all subsequent tests. |
| `python --version` | Passed: Python 3.11.9. |
| `python -m venv .venv` | Passed: created a fresh ignored environment in the isolated worktree. |
| `.venv` Python: `python -m pip install --upgrade pip` | Passed: upgraded pip from 24.0 to 26.1.2. |
| `.venv` Python: `python -m pip install -e ".[test]"` | Passed: installed the project and test dependencies in 128.4 seconds. |
| Focused `.venv` pytest run | Passed: 19 manifest and fixture-policy tests; final focused rerun completed in 0.92 seconds. |
| First `python scripts/generate_dataset_manifest.py` | Passed: wrote 56 records in 11.547 seconds. |
| Second generator run | Passed: reported `Unchanged` in 6.793 seconds; manifest SHA-256 remained `4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`. |
| Timed `python scripts/verify_dataset_manifest.py` with before/after status and hash checks | Passed in 7.465 seconds; manifest bytes and worktree status were unchanged. |
| Final generator and verifier reruns after diagnostic hardening | Passed: generator remained unchanged and verifier passed. |
| `.venv` Python: `python -m pytest -q` | Passed: 49 tests in 2.70 seconds (4.662 seconds process wall time). |
| `.venv` Python: `python -m pip check` | Passed: no broken requirements. |
| `.venv` Python: `python scripts/verify_git_hygiene.py` | Passed: 56 protected paths, 90,960,790 bytes, unchanged aggregate SHA-256, no forbidden tracked paths, no gitlinks, and successful submodule status. |
| `git diff --check` | Passed with no whitespace errors. |
| `git diff --quiet -- raw_data data_clean data_features` | Passed with no protected dataset diff. |
| Independent post-change protected-file SHA-256 calculation | Passed: 56 paths, 90,960,790 bytes, aggregate `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`. |

Publication and GitHub Actions results are recorded in the draft PR checks so a post-success documentation commit does not retrigger the workflow.

## 13. Completion Evidence

Manifest inventory:

| Metric | Result |
| --- | ---: |
| Records | 56 |
| RAW | 27 |
| CLEAN | 27 |
| FEATURE | 2 |
| Canonical OHLCV schema status | 56 |
| Naive timestamp syntax with unknown timezone | 56 |
| Observed duplicate timestamps | 5 |
| Observed missing cells | 0 |

Evidence status counts across classification, columns, timestamp coverage, and the nine semantic/parser fields on every record:

| Evidence status | Fields | Meaning in this manifest |
| --- | ---: | --- |
| `OBSERVED` | 112 | Ordered columns and parseable timestamp coverage. |
| `DECLARED` | 112 | Directory classification and parser decision. |
| `INFERRED` | 168 | Filename-derived market, symbol, and timeframe labels. |
| `UNKNOWN` | 280 | Source, timezone, period semantics, volume meaning, and price unit. |

Protected dataset integrity:

| Metric | Before | After |
| --- | ---: | ---: |
| Paths | 56 | 56 |
| Bytes | 90,960,790 | 90,960,790 |
| Aggregate full-hash SHA-256 | `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543` | `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543` |

Unresolved semantic limitations:
- All observed timestamps are naive; the timezone is unknown.
- Broker/source identity, period-open/period-close meaning, volume meaning, and price unit remain unknown.
- Market, symbol, and timeframe values are unnormalized filename inferences, not declarations of broker contracts.
- The five duplicate timestamps are recorded, not repaired; dataset mutation is outside KAN-9 scope.
