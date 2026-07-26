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
| Protected M1 → native M5 | 89 | 12,317/12,317 exact OHLCV | 192/11,922 exact OHLCV |
| External M5 → native M15 | 88 | 4,287/4,287 exact OHLC; 4,283 exact OHLCV | 25/4,257 exact OHLC; 9 exact OHLCV |

The four external start-label mismatches are volume-only differences of 1-2 units.
Price membership remains exact. Each candidate applies the partial-coverage policy in
its own timestamp convention. Under the promoted start-label convention, the protected
M1/M5 overlap is exact after excluding the one global partial coverage-boundary bin
whose source begins at `10:22` inside the `10:20` M5 interval.

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
- 69 censored labels where outcome evidence is incomplete or ambiguous.

The review-corrected run uses each timestamp candidate's own session membership and
keeps the valid `21:55` M5 period-start bar when it becomes available at `22:00`.
Five labels that were previously censored at the boundary are therefore evaluated from
valid in-session evidence: one false-break/re-entry, three full-range reversals, and one
no-resolution horizon.

The canonical session partition uses the same interval rule. A `PERIOD_START` source
uses `[09:00, 22:00)`, while an equivalent `PERIOD_END` source uses `(09:00, 22:00]`.
Canonical partitioning, G4 audit, and session-local resampling all derive membership
from the interval start. Continuous-calendar policies cannot declare session bounds or
request session exclusion; those contradictory combinations are rejected at contract
validation instead of silently retaining rows. The changed canonical evidence contract
and evaluator identify themselves as version `1.1.0`.

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

The artifact includes a mandatory run manifest containing code revision and dirty/diff
state, CLI and entrypoint, configuration snapshot, all source hashes and byte sizes,
locale and runtime/analytical timezones, calendar and bar-builder versions, Python,
pandas, numpy and floating-point settings, and explicit null seeds under the
no-randomness policy. `--check` reproduces the analytical payload while preserving the
recorded provenance of the run that wrote the artifact.

Git dirty/diff provenance is computed over the input tree and explicitly excludes the
generated Artifact path. Repeating the same command against the same input state
therefore emits byte-identical output instead of feeding the previous Artifact bytes
back into its own provenance hash.

Output symlinks are rejected before Artifact construction so a lexical alias cannot
re-enter the provenance hash through its target. Coverage-boundary detection first
derives the target group's left edge from `timestamp_label`, then applies the
`PERIOD_START`/`PERIOD_END` source offset. The historical evidence schema is also
versioned as `1.1.0` after adding `DECLARED` to its published evidence enum.

The run also verifies that all protected CSV hashes and
`data/manifests/committed_datasets.json` remain byte-identical.
