# KAN-15 Abshodeh Behavioral Fingerprint Audit

## Scope

KAN-15 groups the 451 KAN-14-eligible KAN-13 event/feature/label triplets into
preregistered descriptive cells. Cell assignment uses only `MarketEventIdentity` and
the matching `AsOfFeatureSnapshot`. Retrospective labels are joined only after the
assignment IDs and cell IDs are frozen.

This audit describes the bounded committed corpus. It does not estimate a calibrated
probability, expected return, trade direction, entry, invalidation, target,
profitability, or live-readiness.

## Governed Input

| Evidence | Result |
| --- | ---: |
| Eligible events/features/labels | 451 / 451 / 451 |
| Resolved retrospective labels | 382 |
| Censored retrospective labels | 69 |
| Feature-ineligible events retained in audit | 2 |
| Feature-ineligibility reasons | `INSUFFICIENT_PAST_ONLY_HISTORY` (1), `NON_POSITIVE_RANGE_FEATURE` (1) |
| Missing-semantics cell assignments | 0 |
| M1-to-M5 reconciliation | 12,317 / 12,317 exact OHLCV |
| Upstream gates | G0-G5 `PASS` |
| Protected source files | 56, unchanged |
| Committed manifest | unchanged |

Source semantics remain those approved in KAN-14: `Asia/Tehran`,
`PERIOD_START`, and the analytical session `[09:00,22:00)`.

## Preregistered Views

Every eligible event is present once in each view. The views are separate descriptive
cuts, not a single high-dimensional grid.

| View | Added as-of dimensions | Cells | `HEURISTIC_ONLY` | `NOT_STATISTICALLY_ELIGIBLE` |
| --- | --- | ---: | ---: | ---: |
| `CORE` | none beyond event type, direction, session | 8 | 8 | 0 |
| `TOUCH_CONTEXT` | prior-touch count | 24 | 10 | 14 |
| `APPROACH_CONTEXT` | approach velocity, overlap | 72 | 10 | 62 |
| `ORIGIN_BAR_CONTEXT` | range expansion, body ratio | 51 | 10 | 41 |
| `LEVEL_AGE_CONTEXT` | level age | 12 | 8 | 4 |
| `SNAPSHOT_CONTEXT` | eligibility-time penetration | 10 | 8 | 2 |
| **Total** | six independent views | **177** | **54** | **123** |

`HEURISTIC_ONLY` means only that the preregistered minimum support and chronological
descriptive-range rules were met in this corpus. It is not statistical eligibility.
Sparse or chronologically unsupported cells remain visible and fail closed as
`NOT_STATISTICALLY_ELIGIBLE`.

## Counting and Metric Rules

- Each cell reports eligible, resolved, censored, feature-ineligible, and
  missing-semantics counts.
- Outcome counts include censoring.
- Outcome frequencies exclude censored labels from the denominator and are labeled
  `DESCRIPTIVE_IN_SAMPLE_EMPIRICAL_FREQUENCY`.
- Censored labels never enter penetration, pullback, MAE, MFE, time-to-outcome, or
  duration summaries.
- Robust summaries use deterministic Decimal Type-7 linear quantiles.
- Three contiguous equal-event-count chronological partitions replace random splits.
- Every cell reports chronological support and its maximum descriptive outcome-frequency
  range where the denominator exists in all partitions.

The support policy is preregistered as:

| Rule | Value |
| --- | ---: |
| Minimum events per cell | 12 |
| Minimum resolved labels per cell | 9 |
| Minimum resolved labels per chronological partition | 2 |
| Maximum descriptive frequency range | 0.35 |

These thresholds are audit rules, not optimized market parameters.

## Outcome Coverage

| Retrospective class | Count |
| --- | ---: |
| `FULL_RANGE_REVERSAL` | 331 |
| `CENSORED` | 69 |
| `FALSE_BREAK_REENTRY` | 17 |
| `NO_RESOLUTION` | 12 |
| `DIRECT_CONTINUATION` | 11 |
| `ACCEPTANCE_THEN_EXPANSION` | 7 |
| `SWEEP_PULLBACK_CONTINUATION` | 4 |
| **Total** | **451** |

This imbalance is observed corpus composition. It is not a forecast and is not used to
alter bucket edges, event thresholds, or label definitions.

## Gate Disposition

| Gate | Status | Meaning |
| --- | --- | --- |
| G6 feature reproduction | `PASS` | Label-free assignments reproduce exactly after input permutation. |
| G7 analytical eligibility | `NOT_EVALUATED` | Regime/analog downstream validation is deferred. |
| G8 statistical eligibility | `NOT_EVALUATED` | No out-of-sample or purged validation exists. |
| G9 execution/backtest eligibility | `NOT_EVALUATED` | No execution or backtest policy exists. |

G6 does not promote G7, G8, or G9.

## Persistence and Reproduction

- Full catalog:
  `outputs/research/KAN-15/abshodeh-behavioral-fingerprint.json`
  (research-only, ignored, not committed).
- Compact machine-readable audit:
  `docs/audits/artifacts/KAN-15-abshodeh-behavioral-fingerprint.json`.
- The compact audit records the SHA-256 of the exact serialized full catalog, a bounded
  sample of at most 12 cells, configuration/support rules, view coverage, gate states,
  source/manifest preservation evidence, and limitations.
- The implementation revision is a content hash of the KAN-15 engine plus the governed
  canonical, historical-labeling, source-semantics, runner, and configuration inputs.

Reproduction requires:

```bash
python scripts/run_behavioral_fingerprint.py --research
python scripts/run_behavioral_fingerprint.py --research --check
```

## Limitations

- Holiday and trading-day completeness remains unknown.
- Sparse M1 intervals cannot always distinguish no-print periods from feed outages.
- Volume meaning remains unknown.
- HTF location, Herat, XAUUSD, regime discovery, analog search, adaptive decisions,
  execution, and live evidence are not evaluated.
- Bid/ask, spread, fill, slippage, news, order-flow, and institutional inventory
  evidence are unavailable.
- Chronological descriptive stability is not out-of-sample validation and does not
  establish generalization.
