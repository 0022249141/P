# Acceptance Criteria

## Global definition of done
A change is complete only when:
- requirements and assumptions are documented;
- typed interfaces and configuration are explicit;
- relevant tests pass;
- deterministic reruns produce identical outputs;
- temporal integrity and look-ahead checks pass;
- data and migration impact is documented;
- evidence limitations are disclosed;
- Jira key and acceptance criteria are traceable in the PR;
- documentation is updated.

## Data Pipeline
- Parses supported CSV formats without silent column shifts.
- Produces canonical UTC OHLCV records.
- Preserves raw inputs and provenance.
- Detects duplicates, invalid OHLC, missing/irregular intervals, and ambiguous timezone semantics.
- Reconciles M1-derived M5/M15/M30/H1/H4/D1 bars against supplied higher-timeframe datasets within documented tolerances.
- Emits G0–G9 gate status and blocks ineligible downstream processing.

## Session Intelligence Engine
- Uses versioned DST-aware session calendars.
- Separates broker time, UTC, exchange/session time, and Tehran presentation time.
- Computes session range, ADR consumption, directional efficiency, overlap, speed, and high/low timing without future leakage.
- Registers previous-session liquidity levels before testing them.
- Distinguishes sweep/reclaim from acceptance with configurable close-based rules.
- Separates XAUUSD and Tehran Abshodeh models.
- Separates news and non-news regimes when an eligible calendar is available.
- Reports sample size, regime coverage, and confidence limitations.

## Market Structure Engine
- Confirmed swings expose pivot and confirmation timestamps.
- BOS, CHoCH, and MSS are close-based and reproducible.
- No event appears before information was available in real time.
- Threshold changes are configuration-driven and sensitivity-tested.

## Liquidity Engine
- Liquidity pools are registered before outcomes are evaluated.
- Pool state transitions are explicit and auditable.
- Rankings include evidence, role, destination, and invalidation.
- No target is emitted without a registered liquidity destination.

## Inventory and Dealer Proxies
- Outputs are labeled as inferred proxies unless direct data supports observation.
- Score components are transparent and individually testable.
- No institutional-intent certainty claim is permitted from OHLCV alone.

## Backtesting and Validation
- Candle-by-candle replay is deterministic.
- Entry, stop, target, conflicts, and same-bar ambiguity use an explicit fill policy.
- In-sample, validation, and out-of-sample periods are separated.
- Walk-forward and Monte Carlo preserve temporal/regime structure where required.
- Costs are modeled only from available evidence; missing costs block execution-readiness claims.
- Reports include sample size, expectancy, drawdown, robustness, calibration, sensitivity, and limitations.

## Reporting
- Final reports distinguish observed, derived, inferred, hypothesis, and unknown claims.
- Persian output is readable and keeps technical English terms where precision benefits.
- No silent omission of failed gates, contradictory evidence, or unavailable data.
