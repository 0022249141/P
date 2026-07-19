# KAN-13 Market Event Schema and Historical Labeling

## Status

KAN-13 adds a research-only, deterministic schema and synthetic labeling harness. The
protected Abshodeh pilot is intentionally blocked by the existing KAN-10 gate. It does
not produce a historical event catalog or eligible historical labels.

## Governed Boundary

The immutable schema version is `1.0.0` and separates the historical records:

- `MarketEventIdentity` identifies one confirmed level event and records its origin,
  observation, confirmation, and first feature-eligible timestamps.
- `AsOfFeatureSnapshot` contains only measurements available at the event cutoff.
- `HistoricalOutcomeLabel` contains bounded future outcome evidence only.
- `CensoringRecord` explains why a bounded outcome could not be assigned.
- `LineageRecord` identifies source data, policies, code, and deterministic dirty-tree
  evidence without absolute paths or machine identity.
- `HistoricalExtractionResult` contains the deterministic in-memory event, feature,
  label, censoring, gate, policy, and count evidence from one eligible extraction.
- `LabelingEvidence` and `CalendarSemanticsEvidence` carry explicit PASS, FAIL, BLOCKED,
  UNKNOWN, or NOT_EVALUATED evidence into the label boundary.

Feature and label models are distinct, immutable namespaces joined only by `event_id`.
IDs are SHA-256 hashes of canonical, sorted material inputs. Serialization is sorted,
ASCII JSON and excludes wall-clock generation time, hostnames, usernames, and absolute
paths.

## Versioned Policies

| Concern | Version | Decision |
| --- | --- | --- |
| Bundle | `abshodeh-historical-labeling-v1` | Research-only configuration bundle |
| Canonical request | `abshodeh-canonical-request-v1` | M1 source and governed M5 event bars |
| Event source | `layer2-confirmed-swings-v1` | Confirmed swing highs/lows only |
| Features | `asof-features-v1` | Past-only measurements at eligibility |
| Labels | `abshodeh-level-outcome-v1` | Provisional symmetric level outcomes |
| Session | `abshodeh-research-session-v1` | Asia/Tehran, 09:00-22:00, no crossing |

The event adapter is pinned to `src/layer2_structural_engine.py` at SHA-256
`74406477903916ababd4db7ce25b4e459e576e4bcce15bf52ff4a6ebb44d2310`. It retains
`min_strength=0.6` and `lookback=2` and calls only the existing confirmed swing-high and
swing-low surfaces. BOS, CHoCH, MSS, liquidity lifecycle, reclaim, acceptance,
destination ranking, and trading decisions are excluded.

The adapter resolves `repository_root` against the checkout that loaded KAN-13, hashes
the exact approved source path, and loads that file directly with `importlib`. It does
not trust a same-named module from `sys.path`, another checkout, or an editable install.

Because timestamps are `PERIOD_START`, the adapter records confirmation and first
feature eligibility at the end of the confirming M5 period. M5 feature rows and H1
diagnostic rows are likewise filtered by period-end availability before use.

The session and period declarations are research hypotheses, not source facts. They do
not promote canonical gates. Holiday and trading-day completeness remains unknown.

## Feature Boundary

The snapshot cutoff is `first_feature_eligible_timestamp`. ATR uses a trailing 14-bar
window ending at that cutoff. Prior touches, approach velocity, overlap, range expansion,
body, and wick measurements use declared finite lookbacks. A higher-timeframe location
may use only the last completed H1 bar available by the cutoff. Herat and XAUUSD remain
`NOT_EVALUATED`.

Prefix and post-cutoff mutation tests demonstrate that later candles cannot change an
eligible event or its feature snapshot. No centered rolling window, negative shift,
backward fill, complete-series normalization, percentile, or extremum is used.

## Outcome Policy

Labeling is fail-closed. A direct caller must supply a typed `LabelingEvidence`; there
are no boolean or PASS defaults. Source and calendar statuses must both be explicit
`PASS` to produce a resolved label. Missing evidence is rejected, while FAIL, BLOCKED,
UNKNOWN, or NOT_EVALUATED evidence produces the corresponding censoring record.

`R` is the past-only ATR(14) stored in the feature snapshot. ABOVE and BELOW events use
an exactly mirrored outward coordinate. The external policy fixes penetration at
`0.10 R`, reentry at `0.00 R`, qualifying pullback at `0.25 R`, acceptance at two
closes beyond `0.10 R`, and continuation/reversal barriers at `1.00 R`. The bounded
horizon is 12 M5 bars and at most 3,600 seconds inside one session.

| Outcome | Deterministic condition |
| --- | --- |
| `DIRECT_CONTINUATION` | Outward barrier is first; no earlier higher-precedence sequence |
| `SWEEP_PULLBACK_CONTINUATION` | Penetration, reentry, pullback, then outward barrier |
| `FALSE_BREAK_REENTRY` | Penetration and reentry precede the inward barrier |
| `ACCEPTANCE_THEN_EXPANSION` | Two accepted closes precede the outward barrier |
| `FULL_RANGE_REVERSAL` | Inward barrier is first without a false-break sequence |
| `NO_RESOLUTION` | Complete horizon reaches neither terminal barrier |
| `CENSORED` | Horizon or evidence cannot support a deterministic outcome |

Censoring covers insufficient future horizon, session boundary, dataset end, missing
bars, failed source eligibility, unavailable calendar semantics, ambiguous intrabar
terminal order, and an explicit upstream reason. When a continuation terminal is first,
acceptance outranks sweep/pullback, which outranks direct continuation. When a reversal
terminal is first, false-break/reentry outranks full-range reversal. A bar spanning both
terminal barriers is censored because OHLC data cannot establish intrabar order.

### Metric scope

All existing penetration, pullback, MAE, MFE, outside-bar, and outside-time fields are
terminal-scoped; no separate full-horizon copies are retained:

- for a terminal outcome, `metric_scope=PRE_TERMINAL_INCLUSIVE`, and every metric uses
  bars from the first post-eligibility bar through the first terminal bar, inclusive;
- for `NO_RESOLUTION`, `metric_scope=COMPLETE_HORIZON_NO_TERMINAL`, and metrics use all
  12 bounded bars;
- for a censored label, `metric_scope=NOT_EVALUATED`, metric timestamps are null, the
  metric bar count is zero, and numeric excursion fields are null;
- `metric_end_timestamp`, `metric_bar_count`, and Pydantic field descriptions make this
  scope machine-readable in the committed JSON schema;
- session, gap, ambiguity, or candle evidence after the first terminal cannot change
  classification, terminal timestamps, or scoped metrics.

These thresholds are provisional research parameters. They are not market truth,
optimized values, calibrated probabilities, or final Behavioral Fingerprint settings.

## Synthetic Evidence

`docs/audits/artifacts/KAN-13-market-event-labeling-fixture.json` contains schemas and
20 deterministic synthetic cases: all six resolved outcomes in both ABOVE and BELOW
directions, plus all eight censoring reasons. Every expected result matches the observed
result. The artifact contains synthetic data only.

The same artifact also records one complete synthetic M1-to-M5 extraction: G0-G5 all
PASS, the supplied M5 bars exactly reconcile with governed resampling, and the result
contains two confirmed events, two as-of features, two bounded labels, and zero
censoring records. This proves the executable path, not market or statistical validity.

Reproduce it with:

```text
python scripts/generate_historical_labeling_fixture.py
python scripts/generate_historical_labeling_fixture.py --check
```

## Protected Pilot

The requested source is `data_clean/abshodeNaghdi-1.csv`, manifest dataset
`abshode-naghdi-clean-m1-manifest-v1`, SHA-256
`73da57fbc4be42f6243b367a15d94285b511e9357428af011bc5c5e00bed1ddc`.
It contains 50,000 rows and covers displayed timestamps from
`2026-02-18 10:22:00` through `2026-05-18 22:00:00`.

The extractor calls the KAN-10 evaluator with committed manifest semantics before any
resampling, structure engine, feature, or label operation. G0-G4 must pass before M5
resampling/reconciliation, and G0-G5 must all pass before analytical extraction. The
protected result is:

| Gate | Status | Reason |
| --- | --- | --- |
| G0 | PASS | Manifest identity matches |
| G1 | PASS | Parser and canonical columns are valid |
| G2 | BLOCKED | `G2_TEMPORAL_EVIDENCE_BLOCKED` |
| G3 | PASS | OHLC and numeric checks pass |
| G4 | BLOCKED | `G4_CANONICAL_DEPENDENCY_BLOCKED` |
| G5 | NOT_EVALUATED | No eligible derived bars were produced |
| G6-G9 | NOT_EVALUATED | No evaluator or eligible research output |

The terminal result is exactly `BLOCKED_BY_SOURCE_SEMANTICS`. The requested
Asia/Tehran `PERIOD_START` configuration is recorded as a hypothesis and never used to
convert G2 or G4 to PASS. No native M5 reconciliation, H1 diagnostic, historical event
catalog, feature catalog, or label catalog runs in this state. The committed output is
only `docs/audits/artifacts/KAN-13-abshodeh-pilot-summary.json`.

Run the protected check only through explicit research selection:

```text
python scripts/run_historical_labeling.py --research
python scripts/run_historical_labeling.py --research --check
python -m pytest -q -m research tests/research
```

## Limitations

- The source does not independently establish timezone or period semantics.
- No authoritative holiday or trading-day calendar is available.
- Native M5 is reconciliation evidence only and H1 is diagnostic only; neither is read
  after the mandatory source gate blocks.
- The 50,000-row pilot demonstrates the governed pipeline boundary, not statistical
  sufficiency for a Behavioral Fingerprint model.
- No ML, clustering, analog search, probability, entry, invalidation, target, execution,
  broker, live-feed, or external-service behavior is included.
- G6-G9, Herat, and XAUUSD remain `NOT_EVALUATED`.
