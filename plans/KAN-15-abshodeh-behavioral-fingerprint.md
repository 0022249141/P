# KAN-15 Abshodeh Behavioral Fingerprint

Status: implementation and local verification complete on
`KAN-15-abshodeh-behavioral-fingerprint`; publication to a Draft PR is pending.
The branch starts from the merged KAN-14 squash commit
`1e4e921f91b23e467014b660b05dcd89230ee3e2`. No KAN-12 work, protected
dataset edit, manifest edit, threshold optimization, probability model, or trading
decision was performed.

## 1. Objective

Build a deterministic, auditable, research-only Behavioral Fingerprint Engine that
groups the KAN-14-eligible KAN-13 event/feature records into preregistered descriptive
cells, then summarizes their retrospective labels without allowing labels to affect
cell assignment.

The engine will emit:

- deterministic fingerprint and cell identities;
- explicit source, policy, configuration, and code lineage;
- eligible, censored, feature-ineligible, and missing-semantics counts;
- labeled in-sample descriptive outcome frequencies;
- robust retrospective excursion, penetration, pullback, duration, and
  time-to-outcome summaries where the label contract makes them eligible;
- chronological-partition support and descriptive stability diagnostics;
- a deterministic G6 feature-reproduction result;
- explicit `NOT_EVALUATED` states for G7-G9;
- `HEURISTIC_ONLY` or `NOT_STATISTICALLY_ELIGIBLE` evidence labels.

It will not emit calibrated probability, expected return, trade direction, entry,
invalidation, target, profitability, execution assumptions, or live-readiness.

## 2. Jira and Specification Trace

- Jira: `KAN-15` - Build Abshodeh Behavioral Fingerprint Engine.
- Blocker: KAN-14 is `Done`; PR #30 was squash-merged at
  `1e4e921f91b23e467014b660b05dcd89230ee3e2`.
- Inputs:
  - KAN-13 immutable `MarketEventIdentity`, `AsOfFeatureSnapshot`,
    `HistoricalOutcomeLabel`, `CensoringRecord`, and
    `HistoricalExtractionResult`;
  - KAN-14 verified `Asia/Tehran`, `PERIOD_START`, `[09:00,22:00)`,
    exact M1-to-M5 reconciliation, and G0-G5 eligibility.
- Acceptance trace:
  - same input, configuration, and code produce byte-identical output;
  - feature buckets use only the event and as-of feature namespaces;
  - retrospective labels never affect cell identity or assignment;
  - bucket edges and views are explicit, versioned, and configuration-driven;
  - censoring, missing semantics, sparse support, and ineligibility are explicit;
  - chronological partitions are mandatory and random splits are prohibited;
  - permutation-order and label-mutation invariance are tested;
  - G6 is explicitly evaluated; G7-G9 are not promoted;
  - ordinary tests use synthetic/tiny inputs; full corpus is research-only;
  - only a compact audit is committed;
  - protected data and the committed manifest remain byte-identical.

## 3. Current-State Evidence

### 3.1 Repository state

- Branch: `KAN-15-abshodeh-behavioral-fingerprint`.
- Start commit: `1e4e921f91b23e467014b660b05dcd89230ee3e2`.
- KAN-14 produced 451 eligible event/feature/label triplets, 69 censored labels,
  and two feature-ineligible event records.
- G0-G5 passed and governed M1-to-M5 reconciliation was exact for
  12,317 of 12,317 overlapping bars.
- All 56 protected CSV files and the committed manifest were unchanged.

### 3.2 Reusable contracts

- `HistoricalExtractionResult` enforces one feature and one retrospective label for
  every eligible event, disjoint feature-ineligible identities, matching censoring
  records, and one `PASS` result for every G0-G5 gate.
- `MarketEventIdentity` carries deterministic event identity, market, symbol,
  event type, direction, source dataset/hash, source policy, and eligibility time.
- `AsOfFeatureSnapshot` contains only past/as-of values and a neutral session bucket.
- `HistoricalOutcomeLabel` contains the bounded retrospective outcome namespace.
- Feature and label types share only `event_id` and `schema_version`.

### 3.3 Boundary with deferred work

- KAN-12 remains deferred and is not started.
- Existing `pipelines/characterization` is a synthetic KAN-11 audit boundary, not a
  reusable historical fingerprint engine and will remain untouched.
- Herat, XAUUSD, cross-market alignment, regime discovery, historical analog search,
  adaptive decisions, walk-forward validation, purged validation, execution cost,
  and live brokerage are outside this task.
- KAN-13 event and label thresholds and the KAN-11 structural algorithms will remain
  unchanged.

## 4. Assumptions and Domain Questions

### 4.1 Implementation assumptions

- The only eligible input is an immutable KAN-14-gated
  `HistoricalExtractionResult`.
- Cell assignment is a pure function of configuration, event identity, and the
  matching as-of feature snapshot.
- Events are ordered by `(first_feature_eligible_timestamp, event_id)` before
  chronological partitioning; caller order has no effect.
- Chronological partitions use contiguous, deterministic equal-event-count slices.
  No random split, shuffle, or seed is accepted.
- Feature-ineligible events have no retrospective label and therefore contribute only
  to explicit ineligibility support, never to outcome or metric summaries.
- Censored labels contribute to cell coverage and outcome counts but not to resolved
  outcome-frequency denominators or metric summaries.
- Quantiles use a declared deterministic Decimal linear interpolation rule.

### 4.2 Preregistered descriptive views

Every eligible event is assigned to these independently auditable views:

1. `CORE`: event type, direction, and neutral session bucket;
2. `TOUCH_CONTEXT`: core plus prior-touch bucket;
3. `APPROACH_CONTEXT`: core plus approach-velocity and overlap buckets;
4. `ORIGIN_BAR_CONTEXT`: core plus range-expansion and body-ratio buckets;
5. `LEVEL_AGE_CONTEXT`: core plus level-age bucket;
6. `SNAPSHOT_CONTEXT`: core plus eligibility-time penetration bucket.

This family avoids one high-dimensional Cartesian grid whose support would be mostly
single observations. The views and their edges are fixed in configuration before
aggregation. They are research categories, not discovered or profit-optimized states.

### 4.3 Unresolved evidence

- Holiday and trading-day completeness is unknown.
- Sparse M1 intervals cannot always distinguish no-print periods from feed outages.
- Volume meaning is unknown.
- HTF location is not available in the eligible KAN-14 extraction.
- No bid/ask, spread, fill, slippage, order-flow, news, or inventory evidence exists.
- Descriptive stability does not establish generalization or statistical significance.

These limitations do not change label definitions. They remain explicit output
evidence and prevent G7-G9 promotion.

## 5. Proposed Architecture

### 5.1 Dependency direction

`historical_labeling contracts -> behavioral_fingerprint contracts/config/assignment
-> aggregation -> compact audit`

The fingerprint package may import frozen KAN-13 contracts. Historical labeling and
canonical packages must not import the fingerprint package.

### 5.2 Typed contracts

- frozen configuration contracts for dimensions, edges, views, support rules, and
  chronological partitions;
- deterministic `FingerprintCell`, `PartitionDiagnostic`, `RobustSummary`,
  `FingerprintGateAudit`, and `BehavioralFingerprintArtifact`;
- canonical SHA-256 identities whose material includes source extraction identity,
  configuration hash/version, feature-bucket definition, source lineage, and
  deterministic cell dimensions;
- validators that reject label fields in bucket definitions, random partition
  strategies, non-monotonic edges, inconsistent counts, non-descriptive frequency
  labels, and prohibited readiness states.

### 5.3 Data flow

1. Validate the KAN-14-gated extraction and required G0-G5 evidence.
2. Join event and feature records by event ID.
3. Assign preregistered views without reading labels.
4. Freeze assignment identities.
5. Join retrospective labels and censor records by event ID.
6. Aggregate counts, descriptive frequencies, and eligible metrics.
7. Compute chronological-partition support and descriptive frequency ranges.
8. Reproduce assignment from a permuted input and emit G6 `PASS` only on exact match.
9. Emit G7-G9 as `NOT_EVALUATED` with blockers.
10. Serialize with sorted collections and stable ASCII JSON.

### 5.4 Persistence

- Ordinary tests create only temporary synthetic artifacts.
- Full-corpus execution requires `--research`.
- The full cell catalog is written only under ignored
  `outputs/research/KAN-15/` or another explicit unprotected destination.
- The committed audit contains configuration/schema hashes, counts, gate evidence,
  support diagnostics, limitations, and a compact bounded cell sample—not the full
  event or cell catalog.

## 6. File-Level Change Map

Create:

- `pipelines/behavioral_fingerprint/__init__.py`
- `pipelines/behavioral_fingerprint/contracts.py`
- `pipelines/behavioral_fingerprint/policies.py`
- `pipelines/behavioral_fingerprint/assignment.py`
- `pipelines/behavioral_fingerprint/aggregation.py`
- `pipelines/behavioral_fingerprint/artifact.py`
- `configs/research/abshodeh-behavioral-fingerprint-v1.json`
- `scripts/run_behavioral_fingerprint.py`
- `tests/behavioral_fingerprint_helpers.py`
- `tests/test_behavioral_fingerprint_contracts.py`
- `tests/test_behavioral_fingerprint_assignment.py`
- `tests/test_behavioral_fingerprint_aggregation.py`
- `tests/test_behavioral_fingerprint_runner.py`
- `tests/research/test_kan15_abshodeh_behavioral_fingerprint.py`
- `docs/audits/artifacts/KAN-15-abshodeh-behavioral-fingerprint.json`
- `docs/audits/abshodeh-behavioral-fingerprint.md`

Modify:

- `.gitignore` for full-corpus KAN-15 output;
- `scripts/run_abshodeh_source_semantics.py` only if a narrow, tested extraction
  handoff is required to avoid duplicating the KAN-14 governed path;
- this living plan.

Leave untouched:

- all protected CSV files and `data/manifests/committed_datasets.json`;
- KAN-11 characterization engines and artifacts;
- KAN-13 event, feature, and label definitions and thresholds;
- KAN-14 promoted source-semantics policy and committed audit;
- live broker, execution, dashboard, model, and KAN-12 paths.

## 7. Implementation Steps

1. Freeze versioned policies, typed output contracts, identity material, and
   prohibited-output validators.
2. Implement pure feature-bucket assignment with no label argument or import.
3. Add tiny synthetic fixtures and tests for edge semantics, prefix safety, label
   mutation invariance, caller-order invariance, and deterministic IDs.
4. Implement aggregation, censor/ineligibility handling, Decimal summaries, contiguous
   chronological partitions, support classification, and G6 evidence.
5. Add a research-only runner that reuses the governed KAN-14 extraction path and
   validates protected-output destinations before reading the corpus.
6. Generate the full uncommitted catalog and compact committed audit.
7. Run focused tests, the full ordinary suite, research tests, dependency checks,
   manifest verification, Git hygiene, deterministic reruns, and protected hash diff.
8. Publish one branch and Draft PR for human review. Do not merge.

## 8. Verification

- Contract immutability and deterministic serialization.
- Configuration hash and identity sensitivity.
- Rejection of label/outcome fields in bucket definitions.
- Rejection of random or non-chronological partitions.
- Edge inclusion and out-of-range bucket behavior.
- Feature assignment equality after future-label mutation.
- Feature assignment equality under prefix/truncation for retained events.
- Byte-identical output after input permutation.
- Exact count conservation across eligible, resolved, censored, ineligible, and
  missing-semantics states.
- Metrics exclude censored and missing values.
- Frequencies are labeled
  `DESCRIPTIVE_IN_SAMPLE_EMPIRICAL_FREQUENCY` and use the explicit resolved denominator.
- Sparse cells fail closed as `NOT_STATISTICALLY_ELIGIBLE`.
- G6 passes only after exact assignment reproduction.
- G7-G9 remain `NOT_EVALUATED`.
- `python -m pytest -q` passes.
- research-marked full-corpus tests pass only with explicit invocation.
- `python -m pip check`, manifest verification, and Git hygiene pass.
- two full-corpus runs are byte-identical after excluding no fields.
- before/after hashes match for every protected source and the manifest.

## 9. Data and Migration Impact

- No source, canonical, event, feature, or label schema migration.
- New additive fingerprint schema and configuration version `1.0.0`.
- No protected-data rebuild.
- Generated full catalogs are disposable and rebuilt from KAN-14 evidence.
- Rollback is removal of the additive package, configuration, runner, tests, compact
  audit, documentation, and ignore rule; upstream contracts remain unchanged.

## 10. Risks and Limitations

- Look-ahead: labels are structurally excluded from assignment and joined only after
  cell IDs are frozen.
- Repainting: input events retain KAN-13 confirmation/availability timestamps and
  prefix-invariance guarantees.
- Survivorship: only the bounded committed corpus is described; no external universe
  or delisted-instrument claim is made.
- Timezone/DST: KAN-14 declared `Asia/Tehran`; the evidence applies to the selected
  Faraz exports and not every source.
- Calendar: holiday/trading-day completeness remains unknown.
- Sparse support: small cells are retained and explicitly ineligible, not suppressed
  or promoted.
- Stability: chronological descriptive ranges are diagnostics, not out-of-sample
  validation.
- Proxy vs observation: feature buckets are deterministic software-derived
  descriptions, not institutional positioning or inventory observations.
- Execution: spread, fills, slippage, latency, and order constraints are absent.

## 11. Progress Log

| Date | Entry |
| --- | --- |
| 2026-07-27 | KAN-14 PR #30 confirmed merged at `1e4e921`; Jira KAN-14 moved to Done. |
| 2026-07-27 | Jira KAN-15 blocker cleared, issue moved to In Progress, and fresh branch created from merged main. |
| 2026-07-27 | Audited KAN-13/14 contracts and confirmed that KAN-15 can consume `HistoricalExtractionResult` without starting KAN-12 or changing upstream analytical thresholds. |
| 2026-07-27 | Preregistered six low-dimensional descriptive views and explicit non-probabilistic support/stability semantics. |
| 2026-07-27 | Implemented frozen policies/contracts, label-free assignment, deterministic aggregation, Decimal summaries, chronological diagnostics, fail-closed support classification, and G6-G9 audit states. |
| 2026-07-27 | Added a typed KAN-14 extraction handoff while preserving the existing `build_artifact` API; 26 focused KAN-14/KAN-15 regression tests passed. |
| 2026-07-27 | Real-corpus run produced 451 eligible events, 382 resolved labels, 69 censored labels, two unassigned feature-ineligible events, and 177 cells across six views. |
| 2026-07-27 | Real classification: 54 cells `HEURISTIC_ONLY`, 123 cells `NOT_STATISTICALLY_ELIGIBLE`; G6 passed and G7-G9 remained not evaluated. |
| 2026-07-27 | Full catalog remained ignored (about 1.9 MB); a bounded compact audit (about 24 KB) was generated with all 56 protected source hashes and manifest hash unchanged. |

## 12. Completion Evidence

### 12.1 Output identity and coverage

- Compact audit:
  `docs/audits/artifacts/KAN-15-abshodeh-behavioral-fingerprint.json`
- Compact audit SHA-256:
  `3688a29649f530a65595426ae334ad7c5a2bbe5ef5e95ab37415b77cc57d7ac1`
- Audit ID:
  `bfpa_244a54bd33d64c37b926e6d7235833079ab6f8262a48646b0ec390c7c7f91f07`
- Fingerprint ID:
  `bfp_db09521a89a7c9b714d8760b8cae546e9dedc4cbda1ad3545fdf2d38270a75ff`
- Full ignored catalog SHA-256:
  `c29328d26769dcd9492144c50e778d35a0f793b263a8ebebbad909cb8d9f5378`
- Content revision:
  `content-sha256:7d675f0e3a2a876733a0904396632b616ea9f1d9a669f4b15385f40eeb3d973b`
- Unique events: 451; resolved labels: 382; censored labels: 69.
- Feature-ineligible events: two; one `INSUFFICIENT_PAST_ONLY_HISTORY` and one
  `NON_POSITIVE_RANGE_FEATURE`.
- Cells: 177; 54 `HEURISTIC_ONLY`; 123 `NOT_STATISTICALLY_ELIGIBLE`.
- View cells: CORE 8, TOUCH 24, APPROACH 72, ORIGIN_BAR 51, LEVEL_AGE 12,
  SNAPSHOT 10. Every view conserves all 451 eligible events.
- G6 `PASS`; G7, G8, and G9 `NOT_EVALUATED`.

### 12.2 Exact verification

Commands and final results:

```text
python -m pytest -q
249 passed, 4 deselected

python -m pytest -q -m research tests/research/test_kan15_abshodeh_behavioral_fingerprint.py
1 passed

python -m pytest -q -m research
4 passed, 249 deselected

python scripts/run_behavioral_fingerprint.py --research --check
G6 PASS; G7-G9 NOT_EVALUATED; outputs current

python -m pip check
No broken requirements found

python scripts/verify_dataset_manifest.py
Dataset manifest verification passed

python scripts/verify_git_hygiene.py --skip-dataset-integrity
No forbidden tracked paths, gitlinks, submodule failures, or ignore-probe failures

git diff --check
PASS
```

All 56 protected source hashes and the committed manifest hash are identical before
and after the real run. The approximately 1.9 MB full catalog is ignored and
uncommitted; only the bounded approximately 24 KB audit is in scope for publication.

Draft PR URL, CI result, review findings, and final disposition remain to be appended
after publication. Merge remains blocked on explicit human approval.
