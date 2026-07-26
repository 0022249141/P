# KAN-14 — Abshodeh Faraz Source Semantics

## Decision

The selected Faraz Chart Abshodeh CSV sources are eligible for canonical research under
this versioned contract:

```yaml
policy_version: abshodeh-faraz-source-semantics-v1
source_timezone: Asia/Tehran
timestamp_period_semantics: PERIOD_START
analytical_session: "[09:00:00, 22:00:00)"
session_end: EXCLUSIVE
out_of_session_policy: EXCLUDE_AND_REPORT
internal_timestamp_timezone: UTC
```

This decision promotes source-time and bar-membership semantics only. It does not promote
volume meaning, holiday completeness, execution readiness, or institutional intent.

## Evidence hierarchy

### Timezone

`Asia/Tehran` is `DECLARED` from the explicit user-verified Faraz platform setting:

- the chart displayed `UTC+03:30`;
- the user verified that CSV output uses that chart timezone.

UTC and unknown server-time candidates are rejected because they conflict with stronger
explicit platform-setting evidence.

### Bar timestamp semantics

`PERIOD_START` is `DERIVED` from two independent real-data comparisons.

| Evidence | Dates | PERIOD_START | PERIOD_END |
|---|---:|---:|---:|
| Protected M1 → native M5 | 89 | 12,317/12,317 exact OHLCV | 194/11,907 exact OHLCV |
| External M5 → native M15 | 88 | 4,287/4,287 exact OHLC; 4,283 exact OHLCV | 25/4,257 exact OHLC; 9 exact OHLCV |

The four external start-label mismatches are volume-only differences of 1-2 units.
Price membership remains exact. The protected M1/M5 overlap is exact after excluding one
global partial coverage-boundary bin whose source begins at `10:22` inside the `10:20`
M5 interval.

Therefore:

```text
M5 timestamp 14:15
  = available M1 prints in [14:15, 14:20)

M15 timestamp 14:15
  = M5 bars at 14:15, 14:20, and 14:25
```

### Session boundary

Human approval defines the analytical session as `[09:00, 22:00)` Tehran time.

- `09:00` is included.
- `22:00` is excluded.
- Prints at `22:00`, `22:01`, `22:02`, or later remain in immutable source and canonical
  evidence.
- They are excluded from the analytical frame and cannot create Structure, BOS, CHoCH,
  Sweep, feature, label, or signal events.

The protected M1 source contains 50,000 canonical rows; 38 are outside the approved
analytical session, leaving 49,962 analytical rows.

## Sparse interval behavior

Many M5 bins contain fewer than five recorded M1 rows. They are retained under an
explicit sparse-source policy because their OHLCV aggregation reconciles exactly with
native M5 over 12,317 bars.

This proves the reviewed aggregation behavior:

```text
open   = first available source open
high   = maximum available source high
low    = minimum available source low
close  = last available source close
volume = sum of available source volume
```

It does not prove that every absent minute is a no-trade minute. An absent row may still
represent no print, feed interruption, or another unavailable condition. G4 reports gaps;
bounded historical labels censor missing or irregular future evidence.

## Gate and pilot result

The KAN-14 governed run produces:

| Gate | Result |
|---|---|
| G0 provenance | PASS |
| G1 schema/parsing | PASS |
| G2 timezone/period semantics | PASS |
| G3 OHLC/numeric | PASS |
| G4 session/coverage | PASS with reported gaps and exclusions |
| G5 M1-derived M5 reconciliation | PASS — 12,317 exact OHLCV |
| G6-G9 | NOT_EVALUATED |

The guarded KAN-13 extraction is `ELIGIBLE` and emits:

- 451 eligible events;
- 451 past-only feature snapshots;
- 451 bounded historical labels;
- 74 censored labels where outcome evidence is incomplete or ambiguous.

Two additional source events are explicitly recorded as feature-ineligible: one lacks
sufficient past-only history and one has a non-positive range feature. They are not
silently omitted or misrepresented as eligible records. These counts are a deterministic
catalog result, not statistical sufficiency, calibrated probability, profitability, or
live readiness.

## Unresolved evidence

- authoritative holiday and trading-day calendar;
- scheduled closure versus feed outage for every gap;
- volume meaning and universal additivity;
- price-unit promotion beyond stored raw integers;
- spread, bid/ask, fill, commission, slippage, news, and order flow;
- Herat and XAUUSD synchronization;
- G6-G9 statistical and execution eligibility.

## Reproduction

The full-corpus operation is research-only:

```bash
python scripts/run_abshodeh_source_semantics.py --research
python scripts/run_abshodeh_source_semantics.py --research --check
```

Machine-readable evidence:

`docs/audits/artifacts/KAN-14-abshodeh-source-semantics.json`

The run verifies that all protected CSV hashes and
`data/manifests/committed_datasets.json` remain byte-identical.
