# KAN-1 — Repository Audit and Migration Plan

## Objective
Transform the current repository into a governed, reproducible Institutional Trading Lab without breaking verified behavior or replacing working modules blindly.

## Current-state evidence
Observed from the repository:
- deterministic backtest and Monte Carlo package exists under `smc_validation/`;
- analytical modules exist under `src/`;
- historical pipeline scripts exist under `pipelines/legacy/`;
- local CSV datasets are committed under `data/`;
- generated caches and local-path inventory artifacts appear in the repository tree;
- current package metadata exposes `smc_validation`, `core`, and `engines`, while actual code locations require reconciliation;
- existing `AGENTS.md` did not previously define governance, evidence, data, or acceptance rules.

## Audit workstreams

### A. Repository inventory
- enumerate tracked files from Git rather than `project_tree.txt`;
- classify source, tests, data, generated files, caches, docs, scripts, and dead code;
- identify duplicate implementations and imports relying on path mutation/importlib;
- map all entrypoints and runnable commands.

### B. Packaging and dependency audit
- validate `pyproject.toml` package discovery against actual directories;
- identify undeclared runtime/test dependencies;
- test clean installation in Python 3.11;
- document Windows-specific assumptions.

### C. Characterization tests
Before moving or rewriting modules:
- capture current outputs for representative fixtures;
- add deterministic regression tests for pipelines, structure, liquidity, session labeling, signals, backtest, and report contracts;
- identify tests that are scripts rather than pytest tests;
- detect future leakage and import-time side effects.

### D. Data and Git hygiene
- determine which CSVs are required fixtures versus large/raw user datasets;
- hash and inventory committed datasets;
- remove tracked `__pycache__` and generated artifacts in a separate reviewed change;
- replace local absolute-path tree snapshots with reproducible repository inventory tooling;
- propose `.gitignore` and optional LFS/local-data policy.

### E. Target architecture mapping
Map existing behavior into:
- `core/`
- `pipelines/`
- `engines/`
- `services/`
- `smc_validation/`
- `tests/`
- `docs/`

No file relocation until characterization coverage exists for affected behavior.

## Verification commands to establish
Codex must determine and document exact working commands for:
- editable installation;
- unit tests;
- integration tests;
- full local pipeline;
- deterministic validation CLI;
- lint/type checks currently available.

## Risks
- code-search inventory may differ from tracked Git state;
- committed data may be large or contain ambiguous provenance/timezone semantics;
- legacy scripts may encode hidden assumptions;
- apparent module duplication may represent divergent behavior;
- existing tests may not protect against look-ahead or repainting.

## Deliverables
1. `docs/audits/repository-inventory.md`
2. `docs/audits/packaging-and-dependencies.md`
3. `docs/audits/data-and-git-hygiene.md`
4. `docs/architecture/current-to-target-map.md`
5. characterization-test matrix
6. prioritized Jira-ready migration backlog
7. exact test/run evidence

## Human approval gate
Stop after the audit deliverables and migration backlog. Do not perform wholesale architecture migration, delete datasets, rewrite engines, or merge to `main` without review.
