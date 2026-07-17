# Analytical Domain Rules

## Evidence labels
Every material analytical statement must be tagged or traceable as:
- `OBSERVED`: directly present in source data.
- `DERIVED`: deterministic calculation from observed data.
- `INFERRED`: interpretation supported by derived evidence.
- `HYPOTHESIS`: research proposition awaiting validation.
- `UNKNOWN`: unavailable or not eligible to infer.

## Structural definitions
### Valid swing
A pivot is not valid at its visual timestamp until its confirmation condition is met. Every pivot record must include:
- pivot timestamp
- confirmation timestamp
- direction
- price
- range/ATR qualification
- source timeframe

Default research prior:
- HTF swing range threshold: `1.2 × ATR(14)`
- LTF swing range threshold: `0.8 × ATR(14)`

Thresholds are configuration values and require sensitivity analysis.

### BOS / CHoCH / MSS
- BOS/CHoCH require close-based confirmation beyond a confirmed pivot.
- Default break significance prior: `0.6 × ATR`, configurable.
- MSS requires a confirmed sequence, not a single wick: CHoCH → new swing → confirming BOS.
- All events must expose event time and confirmation time.

## Liquidity definitions
- BSL and SSL are candidate liquidity pools, not guaranteed orders.
- Classify internal/external, tested/untested, weak/strong, and priority.
- Sweep: excursion beyond a registered pool followed by failure to sustain acceptance.
- Reclaim: close-based return through the reference boundary under a specified confirmation rule.
- Acceptance: sustained closes/holding behavior outside the reference boundary under a configurable rule.
- Delivery target: a ranked liquidity destination with evidence and invalidation, not a price prediction stated as certainty.

## Session Intelligence
Session behavior is symbol-, feed-, regime-, calendar-, and news-dependent.
- Asia, London, London–New York overlap, New York AM, and New York PM are research partitions, not fixed narratives.
- Session boundaries must be DST-aware and derived from a versioned calendar.
- Measure range, true range, ADR consumption, directional efficiency, overlap, speed, spread/slippage when available, and prior-session liquidity state.
- Classify prior-session levels as untouched, swept-and-reclaimed, swept-and-accepted, fully consumed, double-sided sweep, or left behind.
- XAUUSD and Tehran Abshodeh must have separate calibrated models.

## Inventory and dealer logic
OHLCV does not directly observe dealer inventory. Terms such as accumulation, manipulation, distribution, rebalance, book pressure, and inventory intent are proxy classifications unless supported by direct order-flow data.

A Delivery Commit Score may use transparent components such as displacement, low overlap, follow-through, clean rejection, and absence of full retrace; it remains a heuristic until validated.

## Cross-market transmission
For Tehran Abshodeh, use Herat USD and XAUUSD as drivers under a time-aligned, regime-aware model. Do not assume static coefficients. DXY and US 2Y/10Y yields may only be used when valid synchronized data is available.

## Probabilities and confidence
- Do not emit numeric probabilities from heuristic scores alone.
- Before statistical eligibility, use `HEURISTIC_SCORE` and `QUALITATIVE_CONFIDENCE`.
- Numeric probabilities require out-of-sample calibration, sample-size disclosure, regime coverage, and reliability diagnostics.

## Execution readiness
Execution outputs are not eligible without sufficient evidence for spread, bid/ask, slippage, commission, fill policy, and trade logs. Research scenarios must be clearly separated from live-trading claims.
