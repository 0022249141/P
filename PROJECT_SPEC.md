# Institutional Trading Lab — Product Specification

## Product objective
Create an offline-first, reproducible market-intelligence and research terminal that transforms local CSV market data into auditable structural, liquidity, session, cross-market, probabilistic, and validation outputs.

## Reference markets
1. Tehran Abshodeh — primary domestic market.
2. Herat USD — primary transmission driver for Abshodeh.
3. XAUUSD — global gold driver and independent research market.

For Abshodeh, the default causal prior is `Herat influence > XAUUSD influence`; weights must be measured and regime-dependent rather than hard-coded as truth.

## Primary users
- Researcher/trader validating institutional-style market hypotheses.
- Developer maintaining deterministic analytical engines.
- Reviewer auditing evidence, assumptions, leakage, and reproducibility.

## Core capabilities
1. Data ingestion, validation, normalization, timezone alignment, resampling, lineage, and quality gates.
2. Session Intelligence Engine for symbol-, broker-, regime-, and news-specific behavior.
3. Market Structure Engine for confirmed swings, BOS, CHoCH, MSS, dealing ranges, and regime state.
4. Liquidity Engine for BSL/SSL, internal/external liquidity, sweep, reclaim, acceptance, and delivery targets.
5. Inventory and Dealer Proxy Engine with explicit inference labeling.
6. Cross-Market Transmission Engine for Abshodeh/Herat/XAUUSD and later DXY/US yields when valid data exists.
7. Probability and Scenario Engine that only emits calibrated probabilities after eligible validation.
8. Deterministic Backtest, walk-forward, Monte Carlo, sensitivity, and robustness analysis.
9. Persian RTL analytical report and dashboard with evidence, contradictions, limitations, and readiness gates.
10. Replay, audit trail, run manifests, configuration snapshots, and reproducible artifacts.

## Required analytical output contract
The final analytical report must support:
- Decision Snapshot
- Data and Gate Summary
- Structural Context
- Liquidity Ladder
- Pressure and Delivery
- Market-Maker Narrative
- Primary Scenario
- Execution Map
- Alternative Scenario
- Evidence, Contradictions, and Limitations
- Statistical and Strategy Readiness
- Complete Coverage Ledger
- Research Appendix

No entry without a trigger, no stop without structural invalidation, and no target without a liquidity destination.

## Non-goals for initial delivery
- Autonomous live order placement.
- Claims of direct institutional order-book visibility from OHLCV.
- Unvalidated machine-learning prediction.
- Dependence on a live broker API.
- Copying XAUUSD session rules directly onto Tehran Abshodeh.

## Operational model
- CSV-first and locally runnable.
- Raw datasets are immutable.
- Transformations are deterministic and configuration-driven.
- Computation uses UTC internally.
- Reports may present Tehran time and Persian dates.
- Every output carries source, configuration, code-version, and eligibility metadata.

## Definition of success
The system is successful when the same raw inputs, configuration, calendar version, and code revision produce identical registered events, features, backtest results, and reports; all analytical claims are traceable to evidence and readiness gates.
