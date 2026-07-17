# Institutional Trading Lab — Governed Roadmap

## Phase 0 — Repository control plane and audit
- Codex governance documents
- inventory of modules, datasets, tests, workflows, and technical debt
- characterization tests around existing behavior
- dependency and packaging audit
- data/Git hygiene plan
- Jira/Confluence traceability

Exit: approved migration plan with no unverified destructive rewrite.

## Phase 1 — Data foundation
- canonical schemas and Pydantic contracts
- immutable raw/staged/curated layout
- provenance and run manifests
- validation gates G0–G9
- UTC normalization and versioned calendars
- deterministic multi-timeframe resampling

Exit: three reference markets pass required data gates and deterministic rebuilds.

## Phase 2 — Session Intelligence Engine
- DST-aware session calendar
- XAUUSD session profiles
- Tehran Abshodeh domestic-session profiles
- prior-session liquidity transfer states
- sweep/reclaim/acceptance classification
- daily high/low timing
- news/non-news and volatility regimes

Exit: leakage-free event dataset and baseline out-of-sample statistics.

## Phase 3 — Analytical engines
- confirmed market structure
- liquidity ladder and delivery destinations
- inventory/dealer proxy model
- cross-market transmission
- market state machine and memory

Exit: auditable registered events with tests and evidence labels.

## Phase 4 — Probability and validation
- hypothesis registry
- deterministic replay
- walk-forward and out-of-sample evaluation
- Monte Carlo and regime-cluster stress
- calibration, sensitivity, and robustness
- execution-cost eligibility gates

Exit: statistically eligible components are separated from heuristic-only components.

## Phase 5 — Product layer
- central orchestrator and typed event bus
- CLI/API services
- Persian RTL analytical reports
- dashboard and replay interface
- audit, health, lineage, and observability

Exit: reproducible local terminal with complete evidence and limitations.

## Phase 6 — Controlled operationalization
- broker/feed-specific calibration
- paper/replay monitoring
- drift and data-quality alerts
- human approval gates

Autonomous live execution is outside scope until independently approved.

## Current first Codex assignment
Codex must audit the existing repository and produce `plans/KAN-1-repository-migration.md`. It must not begin wholesale refactoring before the audit and characterization-test plan are reviewed.
