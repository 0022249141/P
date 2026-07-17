# Institutional Trading Lab — Codex Instructions

## Mission
Build a reproducible, offline-first institutional market-research platform for:
- XAUUSD
- Tehran Abshodeh
- Herat USD

The system combines SMC/ICT, RTM Quant, liquidity engineering, session intelligence, dealer/inventory proxies, cross-market transmission, deterministic replay, and quantitative validation.

## Authority model
- The repository specifications are the source of truth for implementation.
- Jira tracks execution; Confluence records decisions and research context.
- Codex may design, implement, test, document, and propose migrations.
- Human approval is required for market definitions, financial-validity claims, live-trading readiness, destructive data changes, and merges to `main`.

## Non-negotiable epistemic rules
- Never invent market data, fills, spread, slippage, order flow, or institutional intent.
- OHLCV-derived inventory or dealer behavior must be labeled as a proxy/inference, not observed fact.
- Use explicit evidence labels where relevant: `OBSERVED`, `DERIVED`, `INFERRED`, `HYPOTHESIS`, `UNKNOWN`.
- Never claim profitability or deployability without out-of-sample validation and execution-cost evidence.
- No look-ahead bias. Swing pivots and structural events must expose confirmation time.
- No repainting logic in backtests or reports.

## Engineering rules
- Python >= 3.11 is the reference runtime.
- Internal timestamps are UTC; Tehran time is presentation-only.
- Preserve raw data as immutable inputs with provenance and hashes.
- Required canonical OHLCV fields: `timestamp,open,high,low,close,volume`.
- Prefer typed Pydantic contracts at module boundaries.
- Keep engines modular, independently testable, configuration-driven, and market-agnostic where possible.
- Avoid monolithic scripts, duplicated logic, hidden global state, and hard-coded market narratives.
- Every feature requires tests, documentation, deterministic outputs, and an acceptance-criteria trace.
- Do not silently change public interfaces or data contracts.
- Do not merge failing tests.

## Repository target architecture
- `core/`: contracts, configuration, time/calendar, event bus, audit metadata
- `pipelines/`: ingestion, validation, normalization, resampling, orchestration
- `engines/`: structure, liquidity, sessions, inventory, cross-market, probability
- `services/`: application workflows and report generation
- `smc_validation/`: deterministic backtest and statistical validation
- `tests/`: unit, integration, regression, leakage, and reproducibility tests
- `docs/`: product, domain, architecture, data, decisions, and runbooks
- `data/`: local datasets only; large/raw files must not be committed unless explicitly approved

## Mandatory execution workflow
For any non-trivial change:
1. Read `PROJECT_SPEC.md`, `DATA_CONTRACT.md`, `DOMAIN_RULES.md`, and `ACCEPTANCE_CRITERIA.md`.
2. Create or update an execution plan under `plans/` using `PLANS.md`.
3. State assumptions and unresolved domain questions before coding.
4. Implement the smallest coherent vertical slice.
5. Add or update tests.
6. Run the relevant test suite and report exact commands/results.
7. Update documentation and trace the change to its Jira key.
8. Open a draft PR; do not merge to `main` without human approval.

## Git/Jira conventions
- Branch: `<JIRA-KEY>-<short-kebab-description>`
- Commit: `<JIRA-KEY> <imperative summary>`
- PR title: `<JIRA-KEY> <deliverable>`
- Every PR body must include: scope, design, tests, data impact, risks, limitations, rollback, and acceptance-criteria checklist.

## Current migration constraint
Existing code in `src/`, `smc_validation/`, and `pipelines/legacy/` must be audited before relocation. Do not rewrite working modules merely for aesthetics. Preserve behavior with characterization tests before refactoring.
