# KAN-13 Market Event Schema and Historical Labeling

Status: draft PR #29 review remediation implemented, locally verified, and published
on the existing branch/worktree. PR #29 is the authoritative post-commit record for
the current head SHA and latest-head GitHub Actions evidence.
No analytical engine, protected dataset, manifest, original checkout, Jira issue,
branch, or pull request will be changed or created outside this existing KAN-13 scope.

## 1. Objective

Build a deterministic, auditable, leakage-controlled research boundary that converts a
temporally safe Abshodeh event source into five separate records:

1. `MarketEventIdentity`
2. `AsOfFeatureSnapshot`
3. `HistoricalOutcomeLabel`
4. `CensoringRecord`
5. `LineageRecord`

The first vertical slice will remain offline and research-only. It will use synthetic
fixtures for ordinary tests and will commit only contracts, policies, compact fixture
evidence, and an aggregate audit summary. Full historical event, feature, and label
catalogs will be ignored and uncommitted.

KAN-13 does not select a canonical structure/liquidity engine, repair analytical
algorithms, estimate probabilities, train a model, or create trading advice.

## 2. Jira and Specification Trace

- Jira: `KAN-13` - Build Market Event Schema and Historical Labeling.
- Governance: `AGENTS.md`, `PLANS.md`, `PROJECT_SPEC.md`, `DATA_CONTRACT.md`,
  `DOMAIN_RULES.md`, and `ACCEPTANCE_CRITERIA.md`.
- Audit inputs: migration backlog, characterization matrix, current-to-target map,
  KAN-11 audit narrative, and KAN-11 machine-readable comparison artifact.
- Data controls: KAN-9 committed manifest and verifier; KAN-10 canonical contracts,
  G0-G5 evaluators, deterministic resampling/reconciliation, and eligibility guard.
- Required invariants:
  - source and feature timestamps are UTC internally;
  - every event exposes origin, observation, confirmation, and eligibility timestamps;
  - feature values use only evidence available by first feature eligibility;
  - outcome values use only a declared bounded future horizon;
  - features and outcomes remain separate types and serialized collections;
  - no protected CSV or committed manifest byte changes;
  - G6-G9 remain `NOT_EVALUATED`;
  - no broker, live feed, external market data, or network service is used.

## 3. Current-State Evidence

### 3.1 Branch and worktree

- Original checkout: `C:/Users/pouria.sl/Documents/GitHub/P`, on unrelated dirty branch
  `codex/igle-phase1-data-gate`; it was not modified.
- Isolated worktree:
  `C:/Users/pouria.sl/Documents/GitHub/P-KAN-13-market-event-schema-labeling`.
- Local branch: `KAN-13-market-event-schema-labeling`, tracking the existing remote
  branch of the same name.
- `HEAD`, upstream, `origin/main`, and merge base are all
  `950a1238f32cb019a6f82309cac14dc3b56654d5`.
- That commit is `KAN-11 Characterize structure and liquidity behavior (#28)` with
  parent `d429ed2fd0f2a1d654f26197acfd8bb89b92fae9`.
- No pull request exists for the KAN-13 head branch at this checkpoint.

### 3.2 Abshodeh manifest inventory

The committed manifest contains 20 Abshodeh records: nine raw, nine clean, and two
feature files. Every record has canonical OHLCV header order, zero duplicate timestamps,
zero missing cells, and naive timestamps. For all 20 records, timezone, timestamp-period
semantics, source, price unit, and volume meaning are `UNKNOWN`; symbol/market/timeframe
are filename-derived `INFERRED` values. The manifest contains no authoritative holiday
or trading-day calendar.

| Path | Class / timeframe | Rows | Observed coverage | SHA-256 |
| --- | --- | ---: | --- | --- |
| `data_clean/abshodeNaghdi-1.csv` | CLEAN / M1 candidate | 50,000 | 2026-02-18 10:22 to 2026-05-18 22:00 | `73da57fbc4be42f6243b367a15d94285b511e9357428af011bc5c5e00bed1ddc` |
| `data_clean/abshodeNaghdi-5.csv` | CLEAN / M5 candidate | 50,000 | 2025-05-14 13:00 to 2026-05-18 22:00 | `a48d3adf07a31b36069ae3ee4d01ba1ee0ab0b9c3db78d3404a05ebe48744e97` |
| `data_clean/abshodeNaghdi-15.csv` | CLEAN / M15 | 50,000 | 2023-01-05 16:00 to 2026-05-18 22:00 | `8218da57a562ce3b85c668b09252428b0cc52bec8e00f3f03fbe8eb7df098fd2` |
| `data_clean/abshodeNaghdi-30.csv` | CLEAN / M30 | 50,000 | 2018-12-17 15:00 to 2026-05-18 22:00 | `854e066ba28dbe3bf877f960b7c4a71a87ab71febbe6e080cc82113e9eb295d5` |
| `data_clean/abshodeNaghdi-60.csv` | CLEAN / H1 | 36,402 | 2012-08-21 00:00 to 2026-05-18 22:00 | `92796753e33b260a7c5c5862fe1ac98f133364d318bba76c5553c1aacb5bb9e0` |
| `data_clean/abshodeNaghdi-240.csv` | CLEAN / H4 | 13,707 | 2012-08-21 00:00 to 2026-05-18 20:00 | `3c7aade0f5deb188adec7f6c0847a0b3c52ecef4e08adafa7817a2f960405146` |
| `data_clean/abshodeNaghdi-1D.csv` | CLEAN / D1 | 4,758 | 2012-08-20 to 2026-05-18 | `82e7c6320ce33574273f45438bc8766282f8c4c3df6c59f283a7a411e0751169` |
| `data_clean/abshodeNaghdi-1W.csv` | CLEAN / W1 | 715 | 2012-08-18 to 2026-05-16 | `820e73730b99969ed1d5f45d2a89c520346bb97785a65a0a0c9c2437048d4d7f` |
| `data_clean/abshodeNaghdi-1M.csv` | CLEAN / monthly | 166 | 2012-08-01 to 2026-05-01 | `672d5b599743099bfeae64ef8bc145de519ff5e2b5a460b4c58fc8b4883e8c2b` |
| `raw_data/abshodeNaghdi-1.csv` | RAW / M1 | 50,000 | 2026-02-25 10:51 to 2026-05-25 22:00 | `274be4cefd9293cea2b9b772e9feac9f4e755377070f35f8db25d905033ef5a0` |
| `raw_data/abshodeNaghdi-5.csv` | RAW / M5 | 50,000 | 2025-05-21 14:45 to 2026-05-25 22:00 | `01ceed702592485c530a4cbdc0c91efeb44979b489963745a49c9f3d4a20c182` |
| `raw_data/abshodeNaghdi-15.csv` | RAW / M15 | 50,000 | 2023-01-16 15:30 to 2026-05-25 22:00 | `f0e7808c74bae17c726dcb86c960d59f3f483e4568a74c811ff11436ad3a25fc` |
| `raw_data/abshodeNaghdi-30.csv` | RAW / M30 | 50,000 | 2018-12-29 16:00 to 2026-05-25 22:00 | `d63bf1bd32aa03d9fab5310015351af46b94a67c791f20aec8058c04d7a0e187` |
| `raw_data/abshodeNaghdi-60.csv` | RAW / H1 | 36,498 | 2012-08-21 00:00 to 2026-05-25 22:00 | `bd350f21f0b1d3658fd58f47202430be62ff373d91f24a5fc3daee10febb0f0b` |
| `raw_data/abshodeNaghdi-240.csv` | RAW / H4 | 13,735 | 2012-08-21 00:00 to 2026-05-25 20:00 | `0bc9ac2a791fe6979b517e5aaf8632b297d6b15630a42f27ced83341fdd17be2` |
| `raw_data/abshodeNaghdi-1D.csv` | RAW / D1 | 4,765 | 2012-08-20 to 2026-05-25 | `47f7ef9cc3d75b53cf9cc1452539fa58dff89cd21c0f287733c17e38b21d2952` |
| `raw_data/abshodeNaghdi-1W.csv` | RAW / W1 | 716 | 2012-08-18 to 2026-05-23 | `9ba98caa17043446f9b382328a2fd26ba1a7719e25255c0d4ef37977458e9908` |
| `raw_data/abshodeNaghdi-1M.csv` | RAW / monthly | 166 | 2012-08-01 to 2026-05-01 | `7ee6ed118e240f7e4e77c1c6ad3139aead4fbb48bf0cf8b34ea39b63bebe1538` |
| `data_features/abshodeNaghdi-1_5m.csv` | FEATURE / M1-to-M5 | 12,352 | 2026-02-18 10:20 to 2026-05-18 22:00 | `984735a9570cba89d258c0eec0876883f78b3e8f0cfc0289b9e32304c05dffcc` |
| `data_features/abshodeNaghdi-1_15m.csv` | FEATURE / M1-to-M15 | 4,345 | 2026-02-18 10:15 to 2026-05-18 22:00 | `0b819ccd5cb55cd8ec9b116035412e04966ec13c8e5ace0c0d1f89f5b818254f` |

The two `data_features` files are not eligible inputs for KAN-13 because their generation
lineage and temporal leakage behavior are not proven. They may be compared only as
non-authoritative diagnostics in an explicitly research-marked test.

### 3.3 Observed intraday/session evidence

Interpreting the naive clock values only as displayed values, not as a proven timezone:

| Clean file | Distinct dates | Observed clock range | Rows outside displayed 09:00-22:00 | Monotonic violations |
| --- | ---: | --- | ---: | ---: |
| M1 | 89 | 09:00-22:02 | 5 | 0 |
| M5 | 343 | 09:00-22:35 | 4 | 0 |
| M15 | 1,185 | 08:45-23:45 | 12 | 0 |
| M30 | 2,596 | 00:00-23:30 | 385 | 0 |
| H1 | 4,761 | 00:00-23:00 | 2,758 | 0 |
| H4 | 4,757 | 00:00-23:00 | 4,826 | 0 |

This pattern is compatible with, but does not prove, a Tehran-local operating window.
The few M1/M5 out-of-window rows and partial first/last days must be reported and may be
censored; they must not be silently discarded. Historical holiday/trading-day
completeness remains `UNKNOWN` without an authoritative calendar.

### 3.4 Canonical eligibility assessment

The KAN-10 evaluator was run against the clean M1 record using only committed manifest
semantics. Results were:

| Gate | Result |
| --- | --- |
| G0 provenance | PASS |
| G1 schema/parsing | PASS |
| G2 temporal integrity | BLOCKED - timezone and period evidence unknown |
| G3 OHLC/numeric | PASS |
| G4 calendar/coverage | BLOCKED - canonical dependency blocked |
| G5 reconciliation | NOT_EVALUATED |
| G6-G9 | NOT_EVALUATED |

No canonical frame was produced, and a G0-G4 feature-source eligibility profile returned
`eligible=False`. Therefore no committed Abshodeh file is production-canonical eligible
today. KAN-13 must not relabel that condition as a pass.

### 3.5 Approved pilot selection

- Primary source: `data_clean/abshodeNaghdi-1.csv` (M1). It is the smallest supported
  canonical source timeframe, is only 2,910,574 bytes, covers 89 observed dates, and can
  use the existing governed M1-to-M5/H1 resampler.
- Event/label timeframe: derived M5, not the committed feature file.
- Reconciliation candidate: `data_clean/abshodeNaghdi-5.csv`, source hash above, over
  the exact overlapping interval only. It is evidence for G5 comparison, not a source of
  features or labels.
- Long-history diagnostic only: `data_clean/abshodeNaghdi-60.csv`; its broad coverage is
  useful for coverage reporting but its coarser bars and 2,758 displayed out-of-window
  rows make it unsuitable for the first event-label pilot.
- This pilot demonstrates deterministic pipeline behavior only. It does not establish
  statistical sufficiency for a Behavioral Fingerprint model.

### 3.6 Operational event-source assessment

KAN-11 is not a production historical event stream:

- Its artifact has `fixture_scope=SYNTHETIC_ONLY`, 14 synthetic fixtures, seven frozen
  snapshots, and 11 comparisons.
- `build_characterization_artifact(root)` constructs the fixture catalog internally and
  calls private characterization adapters. It accepts no canonical market frame and
  emits no reusable historical catalog API.
- The committed artifact SHA-256 is
  `24393818414c659e33182d5cb929f50f11f96bf97dd29325c4615f72d6b554bd`.
- Simple structure outputs are ineligible; layer-2 BOS/CHoCH uses wick penetration and
  conflicts with the governed close-based definition; MSS is missing; layer-3 resting
  liquidity uses a complete sweep list; reclaim, acceptance, complete lifecycle, and
  destination ranking are blocked.

There is therefore no eligible production event stream for KAN-13 to consume.

The smallest proposed research-only adapter will call only
`StructuralEngine.detect_swing_highs` and `detect_swing_lows` from
`src/layer2_structural_engine.py`, whose source SHA-256 is
`74406477903916ababd4db7ce25b4e459e576e4bcce15bf52ff4a6ebb44d2310`.
It will preserve existing defaults (`min_strength=0.6`, `lookback=2`), attach the
right-side confirmation bar and bar-availability timestamp, and emit only confirmed
`SWING_HIGH`/`SWING_LOW` level events. It will not call layer-2 BOS/CHoCH, layer-3
liquidity, resting-liquidity, MSS, reclaim, acceptance, or ranking paths.

The adapter is additive research infrastructure, not a claim that layer 2 is canonical.
Its source hash, parameter values, KAN-11 classification, prefix results, and limitations
will be present in lineage and audit evidence.

## 4. Assumptions and Domain Questions

### 4.1 Approved provisional research policy

These are versioned research hypotheses, not source facts:

- market configuration: `abshodeh-research-session-v1`;
- timezone interpretation: `Asia/Tehran`, evidence `HYPOTHESIS`;
- operating window: 09:00 through 22:00 local;
- timestamp semantics: `PERIOD_START`, evidence `HYPOTHESIS`;
- source bars are M1; event bars are deterministic M5 bars;
- a period-start bar is available only at its period end;
- layer-2 source parameters remain `min_strength=0.6`, `lookback=2`;
- label policy values in section 5.6 are research priors and are not optimized.

These assumptions are approved for an explicitly research-only policy request. They do
not upgrade manifest evidence, prove source semantics, or establish production or
research-record eligibility. The command requires the policy file and has no implicit
market/time policy.

The approved label policy is provisional and versioned as
`abshodeh-level-outcome-v1`. Every threshold and horizon is externalized from code. `R`
is past-only ATR(14) known at `first_feature_eligible_timestamp`; complete-series ATR,
normalization, percentiles, extrema, and later-candle inputs are prohibited. Thresholds
are not market truth, optimized values, calibrated probabilities, or final behavioral
parameters. High-side/low-side symmetry and deterministic precedence are invariants.

### 4.2 Mandatory source-eligibility constraint

- KAN-13 must consume the existing KAN-10 report and eligibility guard; it must not
  replace, reinterpret, or bypass them.
- Hypothetical `Asia/Tehran` and `PERIOD_START` requests are recorded as requested
  configuration only. They must not convert committed-manifest `UNKNOWN` evidence into
  G2 or G4 `PASS`.
- G0-G4 must pass before governed M1-to-M5 resampling and reconciliation. The historical
  extractor rejects any source that does not pass the complete KAN-10 G0-G5 profile.
- The selected M1 source is currently blocked by unknown timezone and period semantics,
  so the full-corpus pilot result is exactly `BLOCKED_BY_SOURCE_SEMANTICS`.
- In the blocked state, no canonical historical frame is promoted, no analytical engine
  is called, and no historical event, feature, or label catalog is generated.
- The only protected-corpus output is a compact deterministic audit summary containing
  dataset identifiers, source hashes and coverage, requested configuration, exact G2/G4
  blockers, unresolved evidence, and G6-G9 `NOT_EVALUATED` status.
- The source acceptance gate is never weakened merely to complete a pilot.

### 4.3 Blocked or unknown semantics

- Feed timezone and period labeling are not declared by the source.
- Holiday/trading-day completeness is unavailable.
- Price unit, volume meaning, and source vendor are unknown.
- Full market closures and missing data cannot always be distinguished.
- The first/last source dates are partial coverage boundaries.
- Layer-2 swing strength is software behavior, not a universal market definition.
- BOS/CHoCH close semantics, MSS, BSL/SSL lifecycle, reclaim, acceptance, and ranking are
  not operational event sources for this task.
- Herat and XAUUSD as-of alignment and covariates are `NOT_EVALUATED`.
- Spread, bid/ask, fills, slippage, news, and order flow are unavailable.
- Outcome classes are retrospective research labels, not probabilities or trade signals.

Any change to the proposed timestamp, event, threshold, session, or horizon policy after
approval requires a new policy version and regenerated research evidence.

## 5. Proposed Architecture

### 5.1 Dependency flow

```text
committed manifest + explicit Abshodeh research config
    -> pipelines.canonical G0-G4 normalization gate
    -> deterministic M1-to-M5 resampling + supplied-M5 G5 reconciliation
    -> guarded G0-G5 eligibility decision
    -> research-only layer-2 confirmed-pivot adapter
    -> MarketEventIdentity records
    -> past-only AsOfFeatureSnapshot records
    -> separate bounded-horizon HistoricalOutcomeLabel/CensoringRecord records
    -> LineageRecord + compact aggregate audit summary
```

Feature code will not import label code. Label code may consume event identity and bars,
but it will not mutate or enrich feature records. Orchestration joins collections only by
`event_id` after each collection has been produced independently.

### 5.2 Typed contracts

All contracts will be strict, frozen Pydantic models with deterministic sorted JSON,
UTC offset-aware timestamps, normalized decimal strings, bounded evidence lists, and no
absolute paths or environment-derived identity fields.

`MarketEventIdentity`:

- `event_id`, `schema_version`, `event_policy_version`;
- `market`, `symbol`, `timeframe`, `source_timeframe`;
- `source_dataset_id`, `source_sha256`, `implementation_identifier`;
- `event_type`, `direction`, `level_type`, `level_price`;
- `level_origin_timestamp`, `observation_timestamp`;
- `confirmation_or_availability_timestamp`;
- `first_feature_eligible_timestamp`;
- immutable source parameters and parameter-policy hash.

Timestamp validation will require:

```text
origin <= observation <= confirmation_or_availability <= first_feature_eligible
```

`AsOfFeatureSnapshot`:

- `event_id`, `schema_version`, `feature_policy_version`, `snapshot_timestamp`;
- fixed typed `FeatureMeasure` fields carrying `value`, `status`, evidence, and declared
  lookback where applicable;
- prior touch count and lookback;
- level age;
- approach velocity;
- approach compression/overlap;
- range expansion;
- wick/body measures;
- trailing current/past-only volatility normalization;
- penetration/break distance observable by the snapshot;
- local session date and neutral session-time bucket;
- HTF location through a completed-bar as-of join only;
- Herat/XAUUSD fields explicitly `NOT_EVALUATED` with null values.

`HistoricalOutcomeLabel`:

- `event_id`, `schema_version`, `label_policy_version`;
- horizon start/end, maximum bars, maximum elapsed time;
- outcome class;
- penetration depth, pullback depth, MAE, MFE;
- bars and elapsed time outside the level;
- reentry and acceptance timestamps when the versioned definitions are satisfied;
- time to destination and final destination class;
- horizon completion status and conflict status.

`CensoringRecord`:

- `event_id`, `schema_version`, `label_policy_version`;
- one primary reason plus bounded secondary reasons;
- reasons include insufficient horizon, session boundary, dataset end, missing bars,
  failed eligibility, unavailable calendar semantics, intrabar/ordering ambiguity, and
  other explicit reason;
- evidence timestamps and affected interval.

`LineageRecord`:

- `event_id` or run scope, source dataset IDs/hashes/bytes;
- canonical schema/policy and bar-builder versions;
- event, feature, session, and label policy versions/hashes;
- analytical source path/hash/parameters;
- code revision, dirty-tree status, and diff hash when dirty;
- Python/pandas/numpy versions and deterministic serialization version;
- no hostname, username, wall-clock timestamp, or absolute path.

### 5.3 Event ID inputs

`event_id` will be `evt_` plus lowercase SHA-256 over ASCII canonical JSON with sorted
keys and compact separators. Material inputs are:

```text
schema_version
event_policy_version
market and symbol
timeframe and source_timeframe
source_dataset_id and source_sha256
implementation_identifier and source-parameter hash
event_type, direction, and level_type
normalized decimal level_price
level_origin_timestamp
observation_timestamp
confirmation_or_availability_timestamp
first_feature_eligible_timestamp
```

The ID will change when any material input changes and remain stable across identical
reruns. Paths, host/user identity, current time, output ordering, and git dirty status are
excluded from event identity. Dirty state belongs in lineage, not identity.

### 5.4 Feature leakage boundary

- The snapshot cutoff is exactly `first_feature_eligible_timestamp`.
- A source bar may be used only when its bar-availability timestamp is at or before the
  cutoff. Period-start timestamps are advanced to period end before availability checks.
- Pivot features may use the pivot bar and earlier bars. Right-side confirmation bars
  may be used only for explicitly named confirmation-distance features available by the
  cutoff; they will never be included in approach features.
- Prior touch count uses 50 M5 bars strictly before the level-origin bar and a tolerance
  of `0.10 * event-time trailing ATR(14)`.
- Approach velocity uses the three M5 closes ending at the origin and is normalized by
  event-time trailing ATR(14).
- Compression/overlap uses five M5 bars ending at the origin.
- Range expansion and wick/body measures use the origin bar against 14 prior complete
  bars; no future or complete-series statistic is permitted.
- Volatility is a trailing ATR(14) computed from bars available by each calculation
  point; no complete-frame mean, percentile, extrema, fit, or scaler is allowed.
- HTF location may use only the last completed H1 bar whose availability is at or before
  the event cutoff. It is `NOT_EVALUATED` when that as-of bar is unavailable.
- No centered window, backward fill, negative shift, final-session high/low, later HTF
  candle, or cross-market forward fill is permitted.
- Prefix and truncation invariance are required for each feature and event type.

### 5.5 Session and horizon policy

- Session policy version: `abshodeh-research-session-v1`.
- Neutral buckets: `09:00-12:00`, `12:00-15:00`, `15:00-18:00`, and
  `18:00-22:00`; these are descriptive labels, not behavioral regimes.
- For period-start M1 bars, a bar is in session only when the entire interval is inside
  `[09:00, 22:00]`; the final eligible M1 start is 21:59.
- Derived M5 bars must also be wholly contained in the same local session.
- No event label may cross a local session date or 22:00 boundary. Such events are
  `CENSORED` with `SESSION_BOUNDARY`.
- Events on partial first/last dates are censored unless the full required past lookback
  and future horizon are present.
- Gaps inside the horizon produce `MISSING_BARS` censoring. Inter-session closures are
  not missing bars.
- Holiday/trading-day completeness remains `UNKNOWN`; no overnight carry is labeled.
- Pilot horizon: 12 complete M5 bars and at most 60 elapsed minutes after the first
  feature-eligible timestamp. Outcome bars begin strictly after the snapshot cutoff.

### 5.6 Label policy decision table

Policy version: `abshodeh-level-outcome-v1`. Values are fixed research priors, not
profit-optimized thresholds or claims of universal market behavior.

For an `ABOVE` level, outward distance is `(price - level) / R`. For a `BELOW` level,
outward distance is `(level - price) / R`. `R` is the past-only trailing ATR(14) fixed at
the feature snapshot. This signed coordinate makes high/low behavior exactly symmetric.

Definitions:

- penetration: maximum outward wick distance is at least `+0.10 R`;
- reentry: after penetration, a completed close returns to `<= 0.00 R`;
- qualifying pullback: after penetration, a completed close reaches `<= -0.25 R`;
- acceptance: two consecutive completed closes at or beyond `+0.10 R`;
- continuation: first completed close at or beyond `+1.00 R`;
- full reversal: first completed close at or beyond `-1.00 R`;
- maximum horizon: 12 M5 bars / 60 minutes, wholly inside one session.

| Outcome | Required side/direction | Required sequence within the complete horizon | Precedence condition |
| --- | --- | --- | --- |
| `CENSORED` / `INSUFFICIENT_HORIZON` | ABOVE or BELOW | Failed eligibility, fewer than 12 complete future bars, session crossing, dataset end, missing bar, unavailable required semantics, or unresolved ordering conflict | Always first; no resolved outcome is assigned |
| `FALSE_BREAK_REENTRY` | ABOVE outward is bullish; BELOW outward is bearish | Penetration, then close-based reentry, then `-1.00 R` full reversal before `+1.00 R` continuation | First terminal close is reversal and qualifying penetration/reentry precedes it |
| `FULL_RANGE_REVERSAL` | Symmetric ABOVE/BELOW | `-1.00 R` full reversal before any qualifying penetration and before continuation | First terminal close is reversal without a prior false-break sequence |
| `ACCEPTANCE_THEN_EXPANSION` | Symmetric ABOVE/BELOW | Acceptance completes, then a later completed close reaches `+1.00 R` before reversal | First terminal close is continuation and acceptance completed strictly earlier |
| `SWEEP_PULLBACK_CONTINUATION` | Symmetric ABOVE/BELOW | Penetration, close-based reentry, qualifying `-0.25 R` pullback, then `+1.00 R` continuation before reversal | First terminal close is continuation; no prior acceptance; pullback sequence precedes it |
| `DIRECT_CONTINUATION` | Symmetric ABOVE/BELOW | `+1.00 R` continuation before reversal without earlier acceptance or qualifying pullback sequence | First terminal close is continuation after higher-precedence continuation classes fail |
| `NO_RESOLUTION` | ABOVE or BELOW | Complete uncensored horizon with neither continuation nor full reversal | Last and only non-censored fallback |

Label precedence is the table order for censoring, followed by the first terminal close.
Within a continuation terminal, acceptance outranks sweep/pullback, which outranks direct
continuation. Within a reversal terminal, false-break/reentry outranks full-range
reversal. A close cannot be simultaneously `+1.00 R` and `-1.00 R`; duplicate timestamps,
invalid OHLC, or any remaining same-bar sequence ambiguity are censored rather than
resolved by an invented intrabar path. Penetration, pullback, MAE, MFE, outside-bar, and
outside-time metrics end at the first terminal bar, inclusive. `NO_RESOLUTION` uses the
complete 12-bar horizon; censored records have no evaluated metrics. Later bars cannot
alter classification or metrics. Terminal ordering uses completed closes.

Destination in KAN-13 means only the policy's symmetric continuation/reversal barrier.
It is not the blocked KAN-11 liquidity-destination ranking concept. The final destination
class will be `OUTWARD_BARRIER`, `INWARD_BARRIER`, `NONE`, or `CENSORED`.

## 6. Proposed File-Level Change Map

Create:

- `pipelines/historical_labeling/__init__.py` - import-safe public contracts/functions.
- `pipelines/historical_labeling/contracts.py` - records, enums, validators, canonical
  serialization, and event ID builder.
- `pipelines/historical_labeling/policies.py` - strict event/feature/session/label policy
  contracts and policy hashing.
- `pipelines/historical_labeling/event_source.py` - research-only layer-2 confirmed-pivot
  adapter with source hash guard and explicit confirmation availability.
- `pipelines/historical_labeling/extraction.py` - deterministic eligible G0-G5 event,
  feature, label, and censoring extraction result.
- `pipelines/historical_labeling/features.py` - past-only feature snapshots.
- `pipelines/historical_labeling/labels.py` - bounded future outcomes and censoring.
- `pipelines/historical_labeling/pilot.py` - KAN-10-gated pilot and compact audit
  aggregation without feature/outcome model coupling.
- `configs/research/abshodeh-historical-labeling-v1.json` - explicit research policy.
- `scripts/run_historical_labeling.py` - opt-in research command.
- `scripts/generate_historical_labeling_fixture.py` - deterministic synthetic compact
  evidence generator with `--check`.
- focused synthetic tests for contracts, IDs, source timing, feature leakage, labels,
  sessions, serialization, imports, and artifact determinism.
- `tests/research/test_kan13_blocked_pilot.py` - module-level research marker,
  protected pilot/checkpoint test, and temporary output only.
- `docs/audits/market-event-schema-labeling.md` - human-readable policy and pilot audit.
- `docs/audits/artifacts/KAN-13-market-event-labeling-fixture.json` - compact synthetic
  contract/decision evidence.
- `docs/audits/artifacts/KAN-13-abshodeh-pilot-summary.json` - aggregate counts, hashes,
  policy versions, feature/session coverage, censoring, missing semantics, and limitations;
  no candle rows or full event records.

Modify:

- `.gitignore` - ignore `outputs/research/KAN-13/` full catalogs.
- this plan - maintain progress, failures, commands, results, and completion evidence.

Leave untouched:

- all files under `raw_data/`, `data_clean/`, and `data_features/`;
- `data/manifests/committed_datasets.json`;
- every structure/liquidity analytical engine and KAN-11 artifact;
- KAN-10 canonical behavior and public exports;
- live/broker surfaces and all cross-market engines.

No engine relocation, threshold rewrite, dependency addition, protected-data migration,
or full-catalog commit is proposed.

## 7. Implementation Steps

1. Record checkpoint approval and mandatory KAN-10 source block in this plan; reconfirm
   clean worktree, source hashes, and protected baseline.
2. Add strict typed contracts, deterministic serialization, policy hashes, and event ID
   sensitivity tests.
3. Add versioned Abshodeh research config with no implicit default market behavior.
4. Add the narrow layer-2 confirmed-pivot adapter; freeze source hash and defaults; add
   prefix/truncation and availability tests before any feature work.
5. Add past-only feature extraction and per-feature prefix-invariance tests.
6. Add bounded label/censoring logic from the exact decision table, with symmetric
   ABOVE/BELOW fixtures for every outcome and precedence conflict.
7. Add pilot gating and an import-safe research command. Require explicit `--research`,
   config path, and the approved repository-relative dataset path. Evaluate
   KAN-10 eligibility before resampling or engine execution and emit only a compact
   `BLOCKED_BY_SOURCE_SEMANTICS` summary for the selected protected source.
8. Generate compact synthetic evidence twice and require byte-identical output.
9. Run the protected pilot through the explicit research path; commit only its compact
   blocked audit summary and no event, feature, or label catalog.
10. Run full verification, review the complete diff for accidental engine/data changes,
    commit and push the existing branch, open exactly one draft PR, wait for both Actions
    events, and stop for human review. Do not merge. Steps 1-9 are complete.

## 8. Verification and Test Matrix

| Area | Required evidence |
| --- | --- |
| Contract validation | Required fields, enums, UTC timestamps, timestamp order, decimal normalization, fail-closed evidence, unknown/not-evaluated representation |
| Event identity | identical rerun stability; sensitivity to market, timeframe, source hash, origin, availability, level, source parameters, and policy version; absence of path/host/user/time |
| Event source | exact layer-2 source hash/defaults; high/low symmetry; insufficient right confirmation; no event before confirmation; prefix/truncation invariance |
| Feature leakage | mutation of any post-cutoff candle cannot change features; declared trailing lookbacks; no centered windows, bfill, negative shift, whole-series reductions, or later HTF joins |
| Label policy | explicit PASS evidence; ABOVE and BELOW fixture for every outcome; first-terminal precedence; acceptance vs sweep vs direct; false-break vs reversal; no-resolution; same-bar/invalid conflict censoring |
| Horizon/censoring | dataset end, missing bars, failed eligibility, session boundary, unavailable calendar, partial day, and complete horizon |
| Separation | feature records contain no future outcome fields; label code does not mutate features; joins use only event ID |
| Session | timezone conversion, neutral buckets, full-interval containment, 22:00 boundary, no cross-session labels, holiday limitation |
| HTF/cross-market | completed H1 as-of join only; absent HTF explicit; Herat/XAUUSD always NOT_EVALUATED |
| Determinism | sorted records and canonical bytes; generator twice; `--check`; compact artifact hash stable |
| Eligible extraction | synthetic canonical M1 -> governed M5 -> exact G5 reconciliation -> confirmed events -> as-of features -> bounded labels/censoring; deterministic typed result |
| Import safety | no protected/local file read, output write, engine execution, broker, network, or current-time capture on import |
| Ordinary-test policy | synthetic/tiny fixtures only; protected-path guard passes; research tests excluded by default |
| Research pilot | explicit research selection reads the approved M1 source, stops at KAN-10 G2/G4, and writes only a compact blocked summary; M5/H1 and catalogs are not read or produced |
| Preservation | engine hashes, KAN-11 artifact, protected paths/bytes/hashes, manifest, G0-G5 behavior, and G6-G9 status unchanged |

Planned commands include:

```text
python -m pytest -q tests/test_historical_labeling_*.py
python -m pytest -q
python -m pytest -q -m research tests/research
python scripts/generate_historical_labeling_fixture.py
python scripts/generate_historical_labeling_fixture.py
python scripts/generate_historical_labeling_fixture.py --check
python scripts/verify_dataset_manifest.py
python scripts/verify_git_hygiene.py --skip-dataset-integrity
python -m pip check
git diff --check
git diff --exit-code -- raw_data data_clean data_features data/manifests/committed_datasets.json
```

The explicit blocked-pilot command is:

```text
python scripts/run_historical_labeling.py --research \
  --config configs/research/abshodeh-historical-labeling-v1.json \
  --dataset data_clean/abshodeNaghdi-1.csv \
  --summary-output docs/audits/artifacts/KAN-13-abshodeh-pilot-summary.json
```

The command refuses an omitted `--research`, an unapproved dataset path, a missing
manifest record, or a source hash mismatch. KAN-10-ineligible source evidence produces
only the compact blocked audit summary; it never invokes the analytical callback.

## 9. Data and Migration Impact

No protected input is modified, moved, renamed, or regenerated. Full catalogs are local
derived research outputs and are ignored. Compact committed artifacts contain only
synthetic records or aggregate counts and hashes; they contain no complete candle/event
catalog, absolute path, hostname, username, wall-clock generation time, credential, or
account information.

The initial protected baseline is:

- 56 tracked CSV files;
- 90,960,790 bytes;
- aggregate sorted path/content SHA-256
  `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`;
- committed manifest SHA-256
  `4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`;
- manifest verifier passed against all 56 records.

Rollback is a normal revert of additive code/docs/config. No history rewrite, force push,
dataset rebuild, or schema migration is required.

## 10. Risks and Limitations

- The research timezone and period-start choices are hypotheses because the feed does
  not declare them. They can shift UTC values, M5 membership, session boundaries, event
  IDs, features, and labels.
- The KAN-11 layer-2 result is characterization on synthetic fixtures, not universal
  proof. The adapter remains research-only and source-hash pinned.
- Complete-frame invocation is acceptable only if prefix tests prove eligible outputs
  identical to cutoff runs; otherwise extraction must run incrementally or block.
- OHLC bars do not reveal intrabar paths, resting orders, institutional intent, spread,
  fills, or order flow. Close-based terminal ordering avoids invented intrabar sequence.
- The 89-date M1 source is capped at 50,000 rows and starts/ends on partial dates. It is
  not a complete historical population.
- Missing holiday semantics prevent claims about full trading-day coverage.
- Outcome frequencies are descriptive counts, not calibrated probabilities or evidence
  of profitability.
- No survivorship, execution cost, out-of-sample, or cross-market claim is made.
- Herat/XAUUSD covariates, regime probabilities, G6-G9 readiness, and live execution
  remain `NOT_EVALUATED`.

## 11. Progress Log

| Date | Command or decision | Result |
| --- | --- | --- |
| 2026-07-19 | Read attached KAN-13 brief and GitHub workflow guidance | Confirmed planning-only checkpoint, existing branch/worktree requirements, and no-PR/no-merge guardrails. |
| 2026-07-19 | Original checkout audit | Found unrelated dirty `codex/igle-phase1-data-gate`; left every tracked/untracked path untouched. |
| 2026-07-19 | `git fetch origin --prune` | Passed; discovered existing remote KAN-13 branch and updated `origin/main` to `950a1238...`. |
| 2026-07-19 | Base relationship audit | Branch, upstream, `origin/main`, and merge base all equal required `950a1238...`; required base is an ancestor. |
| 2026-07-19 | Attach isolated worktree | Passed; local tracking branch attached to the existing remote branch at the requested sibling path. |
| 2026-07-19 | First upstream verification command | Read-only command failed because unquoted PowerShell `@{u}` was parsed as a hash literal; rerun with `'@{u}'` passed. |
| 2026-07-19 | Governance/source review | Read every required governance, audit, architecture, canonical, characterization, manifest, and verifier input. |
| 2026-07-19 | Abshodeh manifest inventory | Found 20 records across raw/clean/features; all canonical-shaped and duplicate/missing-free, but all temporal/source/unit/volume semantics remain unknown. |
| 2026-07-19 | Intraday clock/session scan | Clean M1/M5 are mostly displayed within 09:00-22:00 but contain outliers; longer timeframes contain many out-of-window values. No timezone claim made. |
| 2026-07-19 | KAN-10 canonical evaluation of clean M1 | G0/G1/G3 passed; G2/G4 blocked; G5-G9 not evaluated; no canonical frame and feature-source eligibility false. |
| 2026-07-19 | KAN-11 event-source assessment | Confirmed synthetic-only builder and no operational canonical-frame event stream; selected only a proposed hash-pinned layer-2 confirmed-pivot research adapter. |
| 2026-07-19 | `python scripts/verify_dataset_manifest.py` | Passed against all 56 protected records. |
| 2026-07-19 | First PowerShell aggregate display | Protected count/bytes and manifest hash were correct, but old .NET lacked `Convert.ToHexString`; compatible byte formatting rerun produced the expected aggregate. |
| 2026-07-19 | Protected-data baseline | Passed: 56 CSVs, 90,960,790 bytes, aggregate and manifest SHA-256 values match KAN-9/KAN-11 evidence. |
| 2026-07-19 | `gh pr list --state all --head KAN-13-market-event-schema-labeling` | Passed; no existing PR found. No PR was created. |
| 2026-07-19 | Created this plan | First and sole tracked edit; implementation stopped for human review. |
| 2026-07-19 | Human planning checkpoint | Approved the pilot selection, swing-only adapter, provisional label policy, and session policy with a mandatory KAN-10 source-eligibility constraint. |
| 2026-07-19 | Mandatory blocked-pilot decision | The selected M1 source must finish as `BLOCKED_BY_SOURCE_SEMANTICS`; no historical catalog or eligible labels may be emitted while G2/G4 remain blocked. |
| 2026-07-19 | Fresh Python 3.11 environment | Created ignored `.venv`; combined install command exceeded the shell timeout while pip continued, then editable `.[test]` installation completed and was independently verified. |
| 2026-07-19 | First focused KAN-13 run | Failed with 2 harness-only cases and 35 passes: Decimal/`pytest.approx` incompatibility and import guard blocking package metadata. Corrected tests without changing runtime behavior. |
| 2026-07-19 | Contract and policy implementation | Added five immutable record types, canonical event IDs/serialization, externally versioned event/feature/label/session policies, and import-safe public APIs. |
| 2026-07-19 | Temporal availability review | Detected that `PERIOD_START` M5/H1 rows require period-end availability. Externalized 300/3,600-second periods and updated event confirmation, feature cutoffs, HTF joins, labels, and tests. |
| 2026-07-19 | Intermediate focused rerun | Failed with 1 stale-artifact assertion and 36 passes after the policy hash changed; regenerated the expected artifact, and the next run passed. |
| 2026-07-19 | Blocked-pilot implementation | KAN-10 G0/G1/G3 pass, G2/G4 block, G5-G9 are not evaluated; analytical callback count remains zero and no event, feature, or label catalog is produced. |
| 2026-07-19 | Deterministic generators | Synthetic fixture and blocked summary each ran twice with an unchanged second run, then passed `--check`. |
| 2026-07-19 | Final focused pytest | Passed: 39 tests in 12.08 seconds after contract-state hardening. |
| 2026-07-19 | Final ordinary pytest | Passed: 192 tests, 2 research tests deselected, in 28.66 seconds. |
| 2026-07-19 | Explicit research pytest | Passed: 2 tests in the final 1.45-second run; protected pilot remained blocked. |
| 2026-07-19 | Manifest, hygiene, dependencies, and whitespace | Passed manifest verification, hygiene `--skip-dataset-integrity`, `pip check`, staged/unstaged `git diff --check`, and submodule status. |
| 2026-07-19 | Final protected/source preservation | 56 CSVs, 90,960,790 bytes, aggregate/manifest hashes unchanged; protected paths, all seven characterized engines, and the KAN-11 artifact have zero diff from `origin/main`. |
| 2026-07-19 | Diagnostic command failures | One `rg` search returned exit 1 for no matches and another used unsupported Windows wildcard path syntax; explicit paths were used for the successful reruns. One patch application missed a documentation context line and was reapplied in smaller verified hunks. |
| 2026-07-19 | Draft PR #29 human review | Four blockers accepted: fail-closed label evidence, a real eligible synthetic extractor, mandatory G0-G5 gating/reconciliation, and explicit terminal-scoped metrics. The same branch/worktree/PR will be updated; no merge is permitted. |
| 2026-07-19 | Review-thread helper | Bundled helper failed before reading comments because numeric owner `0022249141` was coerced to GraphQL numeric input. Manual GraphQL with string owner succeeded and found no inline review threads; the supplied top-level blocker list is authoritative. |
| 2026-07-19 | Review remediation design | Require typed PASS evidence for source/calendar labels; add deterministic `HistoricalExtractionResult`; require G0-G5 and real M1-to-M5 reconciliation before callback; load/verify layer-2 from the approved worktree path; compute metrics only through first terminal and test later-candle invariance. |
| 2026-07-19 | First remediation-focused pytest | Failed: 28 tests failed and 20 passed because helper insertion accidentally displaced `synthetic_snapshot`'s return statement. Restored the fixture helper; no analytical engine behavior changed. |
| 2026-07-19 | Fail-closed evidence remediation | Removed source/calendar boolean defaults. Labeling now requires immutable typed evidence, and every absent, unknown, blocked, failed, or not-evaluated state rejects or censors before a resolved outcome. |
| 2026-07-19 | Eligible extraction remediation | Added typed deterministic `HistoricalExtractionResult` and a synthetic M1 -> G0-G4 -> M5 -> G5 -> confirmed swing -> as-of feature -> bounded label/censoring path. It emits 2 events, 2 features, 2 labels, and 0 censoring records; cardinality validators require exactly one feature and label per unique event. |
| 2026-07-19 | Canonical gate remediation | The analytical callback now requires explicit PASS for G0-G5. Focused tests prove G5 `FAIL`, `BLOCKED`, and `NOT_EVALUATED` all hold event/feature/label counts at zero and never invoke extraction. |
| 2026-07-19 | Terminal metric remediation | Declared terminal-inclusive metric scope and end/count evidence. Later valid values, truncation, and duplicate rows strictly after the first terminal destination cannot alter classification or metrics. |
| 2026-07-19 | Exact source remediation | Layer-2 is loaded from the hash-pinned file under the supplied repository root, its module `__file__` is verified, and a different checkout/editable-install root is rejected. Approved SHA-256 remains `74406477903916ababd4db7ce25b4e459e576e4bcce15bf52ff4a6ebb44d2310`. |
| 2026-07-19 | Search diagnostics | Windows wildcard syntax in one `rg` command failed, and a corrected no-match search returned exit 1; explicit files/source inspection identified and ran the import-safety test successfully. |
| 2026-07-19 | Final remediation-focused pytest | Passed: 55 tests in 24.20 seconds after final result-cardinality hardening. |
| 2026-07-19 | Final remediation ordinary/research pytest | Passed: 208 ordinary tests with 2 research tests deselected in 74.15 seconds; explicit research selection passed 2 tests in 5.85 seconds. |
| 2026-07-19 | Final deterministic generation | Synthetic fixture and protected blocked summary each ran twice unchanged and passed `--check`; fixture SHA-256 is `ffceaa107e96367f337aed5ac4b39b5364ccf31e1349880dd881015e44918b4e`, blocked summary SHA-256 remains `1d1c66b684ca8ec058bdf6851626d584857f1c47597536fdb4c8680d7287c24c`. |
| 2026-07-19 | Final governance checks | Manifest verification, full and skip-dataset hygiene, import-safety test, `pip check`, and `git diff --check` passed. |
| 2026-07-19 | Final protected/source evidence | Unchanged: 56 CSVs, 90,960,790 bytes, aggregate `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`, manifest `4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`; protected paths, seven KAN-11 engines, and the KAN-11 artifact have zero diff from `origin/main`. |

## 12. Completion Evidence

The four review blockers are locally complete. Changed interfaces remain additive under
`pipelines.historical_labeling`: immutable evidence/result contracts, the hash-pinned
confirmed-swing adapter, past-only feature builder, bounded label state machine,
G0-G5-gated pilot, deterministic fixtures, and import-safe public exports. The external
bundle remains `abshodeh-historical-labeling-v1`; schema remains `1.0.0`; event, feature,
label, and session policies remain `layer2-confirmed-swings-v1`, `asof-features-v1`,
`abshodeh-level-outcome-v1`, and `abshodeh-research-session-v1`.

Exact final local commands and results:

```text
.venv/Scripts/python.exe -m pytest -q tests/test_historical_labeling_contracts.py tests/test_historical_labeling_events_features.py tests/test_historical_labeling_labels.py tests/test_historical_labeling_pilot.py tests/test_historical_labeling_artifact.py
55 passed in 24.20s

.venv/Scripts/python.exe -m pytest -q
208 passed, 2 deselected in 74.15s

.venv/Scripts/python.exe -m pytest -q -m research tests/research
2 passed in 5.85s

.venv/Scripts/python.exe scripts/generate_historical_labeling_fixture.py  # twice
.venv/Scripts/python.exe scripts/generate_historical_labeling_fixture.py --check
second run unchanged; check current

.venv/Scripts/python.exe scripts/run_historical_labeling.py --research  # twice
.venv/Scripts/python.exe scripts/run_historical_labeling.py --research --check
BLOCKED_BY_SOURCE_SEMANTICS; second run unchanged; check current

.venv/Scripts/python.exe scripts/verify_dataset_manifest.py
.venv/Scripts/python.exe scripts/verify_git_hygiene.py --skip-dataset-integrity
.venv/Scripts/python.exe -m pip check
git diff --check
all passed
```

The synthetic artifact contains 20 matching policy cases: six resolved outcomes in both
ABOVE and BELOW directions plus eight censoring classes. It also records a deterministic
eligible extraction with G0-G5 PASS, 2 events, 2 as-of feature snapshots, 2 resolved
labels, and 0 censoring records. Its SHA-256 is
`ffceaa107e96367f337aed5ac4b39b5364ccf31e1349880dd881015e44918b4e`.
The compact pilot artifact SHA-256 is
`1d1c66b684ca8ec058bdf6851626d584857f1c47597536fdb4c8680d7287c24c`.
It records exact G2/G4 blockers, all policy versions and requested hypotheses, source
identity/hash/coverage, zero eligible events/features/labels, no catalog, and G6-G9,
Herat, and XAUUSD as `NOT_EVALUATED`.

Protected evidence remains 56 CSVs and 90,960,790 bytes with aggregate SHA-256
`781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`.
The committed manifest SHA-256 remains
`4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`.
No protected path, manifest, analytical engine, KAN-11 artifact, broker, live surface,
or original-checkout file changed.

Acceptance is satisfied for fail-closed typed evidence, deterministic eligible synthetic
extraction, mandatory G0-G5 gating, terminal-scoped metrics, exact source-path/hash
verification, schema immutability, namespace separation, deterministic IDs/serialization,
external policy values, temporal availability, prefix/truncation invariance, bounded
symmetric outcomes, precedence/conflict handling, censor coverage, import safety,
research-test isolation, and mandatory KAN-10 rejection. Statistical
sufficiency, source timezone/period proof, holiday completeness, native-M5
reconciliation, H1 diagnostics, ML/probability/trading outputs, Herat, XAUUSD, and G6-G9
remain explicitly outside scope or `NOT_EVALUATED`. The real protected pilot remains
`BLOCKED_BY_SOURCE_SEMANTICS`, with no catalog and zero event/feature/label counts.
Publication and both latest-head GitHub Actions results are maintained in draft PR #29
because those are post-commit evidence.
