# Dataset Fixture Policy

## Purpose

Tests must be deterministic, reviewable, and proportionate to their purpose. Ordinary unit tests may not depend on the committed research corpus under `raw_data/`, `data_clean/`, or `data_features/`. The full corpus is validated once by the dataset-manifest gate and is reserved for explicitly marked integration or research work.

## Fixture Classes

| Class | Intended use | Size and storage | Required treatment |
| --- | --- | --- | --- |
| Unit | One behavior or validation rule | Tiny values inline or in `tests/fixtures/unit/` | Default pytest suite; no protected dataset dependency. |
| Synthetic | Constructed edge cases with no claim of market realism | Generated in memory, temporary directories, or `tests/fixtures/synthetic/` | State the invariant represented; use fixed values or seeds. |
| Curated | Small, hand-selected real-data excerpt | `tests/fixtures/curated/` | Document source path, selection rule, license/provenance, and any transformation. Never imply the excerpt is representative. |
| Integration | Cross-module or file-format behavior | Minimal dedicated fixture where possible | Mark with `pytest.mark.integration`; do not use the full corpus when a smaller fixture proves the contract. |
| Research | Corpus-scale analytical validation | Existing protected dataset directories | Mark with `pytest.mark.research`; run intentionally and keep separate from ordinary unit-test collection. |
| Generated | Reproducible test or report output | Temporary directories by default | Document the generator, version, seed, and regeneration command before committing any generated artifact. |

## Protected Corpus Rules

- Every tracked CSV under the three protected directories is classified as RAW, CLEAN, or FEATURE by directory policy and is recorded in `data/manifests/committed_datasets.json`.
- Unit and synthetic tests must use small temporary files or dedicated fixtures. They must not open protected dataset paths directly.
- A test that truly requires protected data must carry an `integration` or `research` marker and explain why a small fixture is insufficient.
- CI runs `python scripts/verify_dataset_manifest.py` once. Pytest tests for the manifest use only temporary small files and do not rehash the full corpus.
- Curated excerpts are new fixtures, not replacements for or modifications of protected source files. Selection must avoid future-data leakage and preserve source attribution.

## Evidence and Semantics

Manifest evidence statuses are deliberately narrow:

- `OBSERVED`: measured directly from committed bytes, such as columns or timestamp coverage.
- `DECLARED`: established by a versioned repository policy, such as directory classification or parser choice.
- `INFERRED`: parsed from a filename without external confirmation.
- `UNKNOWN`: not supported by repository evidence.

Filename-derived market, symbol, and timeframe labels remain `INFERRED`. Broker/source identity, timezone, timestamp period meaning, volume meaning, and price unit remain `UNKNOWN` unless a separate versioned contract declares them. An observed numeric column or naive timestamp does not establish those semantics.

## Commands

Regenerate deterministically:

```powershell
python scripts/generate_dataset_manifest.py
python scripts/generate_dataset_manifest.py
git diff --exit-code -- data/manifests/committed_datasets.json
```

Verify without writing:

```powershell
python scripts/verify_dataset_manifest.py
python -m pytest -q
```

The second generator run must report `Unchanged`, and the verifier must leave the worktree unchanged.
