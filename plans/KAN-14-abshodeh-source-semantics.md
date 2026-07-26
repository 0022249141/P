# KAN-14 — Resolve Abshodeh Source Semantics and Canonical Eligibility

## 1. Objective

Promote only the Abshodeh source semantics supported by explicit platform evidence and
deterministic real-data reconciliation, then re-run the KAN-13 historical pilot through
the unchanged G0-G5 eligibility boundary.

The target outcome is a fail-closed, reproducible vertical slice:

```text
versioned source-semantics evidence
  -> canonical Tehran-to-UTC normalization
  -> explicit [09:00, 22:00) analytical-session partition
  -> governed sparse M1-to-M5 resampling
  -> native-M5 reconciliation
  -> guarded KAN-13 historical extraction
```

Protected CSV bytes, paths, and the committed dataset manifest remain unchanged.

## 2. Jira and specification trace

- Jira: `KAN-14 — Resolve Abshodeh Source Semantics and Canonical Eligibility`
- Baseline branch: `KAN-14-abshodeh-source-semantics`
- Baseline commit: `f2ed08dd9b70ca94470c0635916201731a994922`
- Governing files:
  - `AGENTS.md`
  - `PROJECT_SPEC.md`
  - `DATA_CONTRACT.md`
  - `DOMAIN_RULES.md`
  - `ACCEPTANCE_CRITERIA.md`
  - `PLANS.md`
- Upstream implementation:
  - KAN-9 committed dataset manifest
  - KAN-10 canonical G0-G9 contracts and G0-G5 evaluators
  - KAN-13 historical event/feature/label pilot

Acceptance trace:

1. Evaluate timezone and period-label candidates explicitly.
2. Reconcile across multiple non-adjacent dates and session boundaries.
3. Promote semantics only with a versioned, reproducible evidence trail.
4. Allow G2 only with sufficient timezone and period evidence.
5. Allow G4 only with an explicit session policy; keep holiday completeness unknown.
6. Allow G5 only after governed M1-derived M5 agrees with native M5.
7. Keep protected data and the committed manifest byte-identical.
8. Keep G6-G9, Herat, XAUUSD, Behavioral Fingerprint, probability, backtest, dashboard,
   and live execution outside scope.

## 3. Current-state evidence

### Repository state

- The branch and `main` both point to `f2ed08d`.
- KAN-13 is fail-closed because the manifest intentionally records source timezone and
  timestamp-period semantics as `UNKNOWN`.
- KAN-10 can normalize explicit timezone/period policies, but it has no source-semantics
  evidence contract.
- KAN-10 treats the session end as inclusive, treats out-of-session rows as a hard G4
  failure, and has no analytical-session partition.
- KAN-10 resampling supports only continuous, contiguous M1 input and explicitly rejects
  `VERSIONED_SESSION`.

### Explicit platform evidence supplied on 2026-07-26

- User-verified Faraz Chart display/export timezone:
  `Asia/Tehran (UTC+03:30)`.
- User-approved analytical session:
  `[09:00:00, 22:00:00)` local Tehran time.
- User-approved handling:
  retain `22:00` and later prints in raw/canonical evidence, but exclude them from
  structure, liquidity, labels, and downstream analytical signals.
- Screenshot evidence shows `UTC+3:30` on the Faraz chart for
  `abshodeNaghdiShanbei`.

### Independent external M5/M15 evidence

- User archive SHA-256:
  `a051db3d5b35f972d9c63c0eb5fa5c1d5bc9c908cd9ae95df723bbeffd7c6c6d`
- M5 member SHA-256:
  `409b0d5d73cafb8d44ec81263ed47e1871ad213e3c5f396e0da280a61ee69e07`
- M15 member SHA-256:
  `30efe139e13d3bcbced7580c1895ff04beaa48841b2c1bdd56b38718d1700f0a`
- Coverage: 88 distinct dates, 2026-04-28 through 2026-07-26.
- `PERIOD_START` candidate:
  - 4,287/4,287 exact OHLC matches;
  - 4,283/4,287 exact OHLCV matches;
  - four volume-only differences of 1-2 units.
- `PERIOD_END` candidate:
  - 25/4,257 OHLC matches;
  - 9/4,257 OHLCV matches;
  - 39 generated-only and 30 native-only timestamps.

This evidence uniquely supports period-start labels. It does not establish volume
meaning or strict additivity.

### Protected repository M1/M5 evidence

Under the approved `[09:00, 22:00)` session and after excluding only the single partial
global coverage-boundary M5 bin:

- 12,317 common M5 bars across 89 dates;
- `PERIOD_START`: 12,317/12,317 exact OHLCV matches;
- `PERIOD_END`: 445/11,922 OHLC and 192/11,922 OHLCV matches, with hundreds of timestamp
  membership differences;
- 38 M1 rows occur at or after 22:00 and must be retained as source evidence but excluded
  from the analytical frame.

The many one-to-four-row M1 target bins still reconcile exactly with native M5. The
evidence therefore supports sparse print aggregation for this export, but does not prove
whether every absent minute is a no-trade interval or a feed outage.

## 4. Assumptions and domain questions

### Promoted semantics

- Source timezone: `Asia/Tehran`, evidence `DECLARED` from the user-verified platform
  setting.
- Bar label: `PERIOD_START`, evidence `DERIVED` from two independent real-data
  reconciliation families.
- Analytical session: `[09:00:00, 22:00:00)`, evidence `DECLARED` by human approval.
- Out-of-session handling: `RETAIN_SOURCE_EXCLUDE_ANALYTICS`.
- M1-to-M5 aggregation: first open, maximum high, minimum low, last close, summed source
  volume, using every available M1 print in the local five-minute bin.

### Unresolved and not promotable in KAN-14

- authoritative holiday/trading-day calendar;
- scheduled closure versus missing feed for every gap;
- volume meaning (`tick`, real, or other) and universal additivity;
- price-unit promotion beyond stored raw integers;
- direct order flow, spread, bid/ask, fills, slippage, or institutional inventory.

Unknown holiday/outage semantics remain explicit limitations and do not become factual
market definitions.

## 5. Proposed architecture

### Source-semantics evidence layer

Add a strict, frozen, versioned contract that records:

- source, market, symbol family, and protected M1/M5 paths;
- candidate timezones and period-label conventions;
- promoted/blocked/rejected status and evidence provenance;
- session start/end and exclusive end convention;
- out-of-session retention/exclusion policy;
- sparse-print and coverage-boundary policies;
- holiday/calendar limitation.

The contract is separate from the KAN-9 manifest. The manifest remains immutable evidence
of committed bytes and continues to record fields it cannot observe directly as
`UNKNOWN`.

### Canonical analytical partition

Extend the KAN-10 evaluation result with an analytical frame:

- `canonicalization.frame`: all valid canonical rows, including out-of-session prints;
- `analytical_frame`: only rows inside the versioned analytical session;
- excluded source-row indexes: stable audit evidence.

`OUT_OF_SESSION_BARS_EXCLUDED` is reported as a G4 diagnostic rather than silently
dropped. The default policy remains reject, preserving existing behavior.

### Versioned-session resampling

Add explicit session-local binning for `VERSIONED_SESSION`:

- timestamps remain UTC internally;
- membership and target labels are calculated in `Asia/Tehran`;
- session end is exclusive;
- sparse M1 bins may be retained only under an explicit policy;
- a partial global coverage-boundary target bin is dropped and audited;
- source-row lineage remains deterministic.

### Candidate and pilot artifact

The research-only probe emits a deterministic machine-readable artifact containing:

- candidate matrix;
- per-date reconciliation evidence;
- out-of-session counts and examples;
- promoted semantics and limitations;
- G0-G5 gate results;
- guarded KAN-13 pilot result;
- hashes for code-independent evidence inputs;
- protected-data before/after hash equality.

## 6. File-level change map

Create:

- `pipelines/source_semantics/__init__.py`
- `pipelines/source_semantics/contracts.py`
- `pipelines/source_semantics/probe.py`
- `configs/research/abshodeh-source-semantics-v1.json`
- `scripts/run_abshodeh_source_semantics.py`
- `tests/test_abshodeh_source_semantics.py`
- `tests/research/test_kan14_abshodeh_source_semantics.py`
- `docs/data/abshodeh-source-semantics.md`
- `docs/audits/artifacts/KAN-14-abshodeh-source-semantics.json`

Modify:

- `pipelines/canonical/contracts.py`
- `pipelines/canonical/quality.py`
- `pipelines/canonical/resampling.py`
- `pipelines/canonical/__init__.py`
- `pipelines/historical_labeling/contracts.py`
- `pipelines/historical_labeling/extraction.py`
- `pipelines/historical_labeling/features.py`
- `pipelines/historical_labeling/labels.py`
- `pipelines/historical_labeling/policies.py`
- `pipelines/historical_labeling/pilot.py`
- `configs/research/abshodeh-historical-labeling-v2.json`
- `scripts/run_abshodeh_source_semantics.py`
- focused canonical and historical-labeling tests as required.

Leave untouched:

- all files under `raw_data/`, `data_clean/`, and `data_features/`;
- `data/manifests/committed_datasets.json`;
- KAN-11 structure/liquidity engines;
- KAN-13 thresholds and event-source algorithms;
- broker/live code.

## 7. Implementation steps

1. Add strict source-semantics policy and candidate-result contracts.
2. Implement deterministic lower-to-higher timeframe candidate probes.
3. Add explicit exclusive-session and retain/exclude canonical partition behavior.
4. Add sparse versioned-session M1-to-M5 resampling with boundary-bin audit.
5. Build a research-only KAN-14 orchestrator that:
   - verifies protected hashes against the unchanged manifest;
   - evaluates candidates;
   - constructs canonical and resampling policies from the promoted contract;
   - canonicalizes M1 and native M5 independently;
   - reconciles the exact governed overlap;
   - invokes the existing KAN-13 gated pilot.
6. Generate deterministic machine-readable and human-readable evidence.
7. Run focused, ordinary, research-only, manifest, hygiene, and dependency checks.
8. Commit, push, and open one draft PR. Do not merge.
9. Address the six actionable Codex review findings without widening KAN-14:
   - reject output paths that alias protected datasets, the manifest, or either
     source-semantics/historical-policy configuration before artifact construction;
   - drop and audit the first partial coverage bin before applying the ordinary
     incomplete-bin policy;
   - apply session membership separately for `PERIOD_START` and `PERIOD_END`
     candidates;
   - evaluate final in-session period-start bars by their source labels while retaining
     availability timestamps for leakage control;
   - retain the complete typed identity of every feature-ineligible event;
   - preserve separate `DECLARED` timezone and `DERIVED` period-semantics evidence
     statuses in policy and audit output.
10. Address the four final-review contract findings:
   - record the complete mandatory analytical run manifest in the artifact;
   - apply partial-coverage handling to `PERIOD_END` resampling;
   - reject continuous-calendar session-exclusion policies;
   - derive canonical session membership from period semantics.
11. Address the five consistency findings from re-review:
   - hash input-only Git state without feeding the prior Artifact into provenance;
   - apply interval-start session membership in both G4 and resampling;
   - reject all continuous-calendar session bounds;
   - bump the canonical contract and evaluator version to `1.1.0`;
   - prove repeated generation is byte-identical.

## 8. Verification

Required checks:

```text
python -m pytest -q tests/test_abshodeh_source_semantics.py
python -m pytest -q tests/test_canonical_quality_and_eligibility.py
python -m pytest -q tests/test_canonical_resampling_reconciliation.py
python -m pytest -q tests/test_historical_labeling_pilot.py
python -m pytest -q
python -m pytest -q -m research tests/research/test_kan14_abshodeh_source_semantics.py
python scripts/verify_dataset_manifest.py
python scripts/verify_git_hygiene.py
python -m pip check
git diff --check
```

Determinism:

- repeat the source-semantics probe and compare bytes;
- repeat the eligible pilot and compare serialized output;
- hash protected files before and after;
- verify the committed manifest byte hash is unchanged.

Temporal safety:

- no period-end candidate may be promoted from weak matching;
- no `22:00` or later bar may enter the analytical frame;
- a valid `21:55` M5 bar remains usable when its availability timestamp is `22:00`;
- no source bar is deleted from canonical/raw evidence;
- no analytical extraction executes unless G0-G5 pass.

Review-regression safety:

- `DROP_PARTIAL_FIRST + REJECT` drops only the partial global coverage boundary and
  still rejects later incomplete bins;
- period-end candidate evidence uses `(09:00, 22:00]`, not the promoted period-start
  membership rule;
- the KAN-14 runner rejects output aliases to every protected/configuration input before
  reading market data or writing an artifact;
- existing hard-link aliases are rejected by file identity, not only by resolved path;
- `DROP_PARTIAL_FIRST` evaluates the candidate interval start for both `PERIOD_START`
  and `PERIOD_END`;
- canonical `PERIOD_END` session membership represents `[09:00, 22:00)` as
  `(09:00, 22:00]`;
- continuous calendars reject `EXCLUDE_AND_REPORT` instead of silently ignoring it;
- the artifact records all mandatory run provenance and `--check` preserves the
  provenance of the run that produced the committed artifact;
- repeated non-check generation over the same input-only state is byte-identical;
- G4, canonical partitioning, and resampling share interval-start membership for
  `PERIOD_END`;
- canonical contract and evaluator output identify the new behavior as `1.1.0`;
- feature-ineligibility records expose the rejected event's pivot and confirmation
  identity;
- requested configuration reports timezone and period evidence independently.

## 9. Data and migration impact

- No protected dataset migration.
- No manifest migration.
- New source-semantics policy is additive and versioned.
- KAN-13 remains fail-closed when called without the new KAN-14 evidence policy.
- Downstream consumers must use the analytical frame, not the all-row canonical frame,
  when a retain/exclude session policy is active.

Rollback:

- remove the additive KAN-14 policy, probe, runner, tests, docs, and artifact;
- revert canonical session-partition and versioned-session resampling additions;
- KAN-13 returns to `BLOCKED_BY_SOURCE_SEMANTICS`;
- no data restoration is required because protected data is never modified.

## 10. Risks and limitations

- User-verified platform timezone is authoritative for the captured export setting, not
  proof that every historical Faraz export used the same setting.
- Exact OHLC reconciliation strongly supports shared aggregation semantics but does not
  prove legal/organizational source identity.
- Sparse M1 rows can represent no prints, feed interruptions, or both; this task does not
  classify every gap.
- Holiday completeness remains unknown.
- External M5/M15 evidence is hash-addressed but not committed; the protected M1/M5
  research test is the repository-reproducible evidence path.
- Volume meaning remains unknown despite near/exact additivity.
- G6-G9 remain not evaluated, so no statistical, execution, or live-readiness claim is
  permitted.

## 11. Progress log

- 2026-07-26: branch confirmed identical to `main` at `f2ed08d`.
- 2026-07-26: user verified Faraz export timezone as `Asia/Tehran`.
- 2026-07-26: real M5/M15 evidence uniquely supported `PERIOD_START`.
- 2026-07-26: user approved `[09:00, 22:00)` and retain-source/exclude-analytics handling
  for `22:00` and later prints.
- 2026-07-26: protected M1/M5 probe produced 12,317/12,317 exact OHLCV matches under
  `PERIOD_START` after one partial global boundary bin.
- 2026-07-26: canonical evaluation retained all 50,000 source rows, partitioned 49,962
  analytical rows, and explicitly excluded 38 rows at or after `22:00`.
- 2026-07-26: the initial guarded KAN-13 pilot became `ELIGIBLE` with 451 events, 451
  as-of features, 451 retrospective labels, 74 censored labels, and two explicitly
  audited feature-ineligible events.
- 2026-07-26: full verification passed: 214 ordinary tests and 3 research tests.
- 2026-07-26: Codex review on Draft PR #30 reported six actionable findings: one P1
  protected-output overwrite path and five P2 semantic/audit defects.
- 2026-07-26: all six findings were accepted for remediation on the existing KAN-14
  branch; `main` remains unchanged and merge remains out of scope.
- 2026-07-26: review remediation retained the final `21:55` M5 bar through its `22:00`
  availability time, reducing boundary-driven censoring from 74 to 69 while leaving all
  451 event/feature/label identities and G0-G5 eligibility intact.
- 2026-07-26: the two feature-ineligible records now retain full typed event identities,
  including pivot and confirmation timestamps.
- 2026-07-26: review-remediated verification passed: 223 ordinary tests, 3 real-data
  research tests, manifest verification, git-hygiene verification, dependency check,
  deterministic artifact checks, and protected-source hash equality.
- 2026-07-27: second Codex review found two additional boundary-safety defects: existing
  hard-link aliases could bypass path-only output protection, and the partial global
  coverage bin was not dropped for the `PERIOD_END` candidate.
- 2026-07-27: both second-review findings were remediated with real inode-identity and
  candidate-interval regression tests; verification passed with 224 ordinary tests and
  3 research tests, while G0-G5 and the 451-event pilot remained unchanged.
- 2026-07-27: final Codex re-review found four additional contract gaps in mandatory
  run provenance, generic `PERIOD_END` boundary handling, continuous-calendar exclusion,
  and canonical `PERIOD_END` session membership.
- 2026-07-27: all four final-review findings were remediated with strict contracts and
  direct regression tests; the analytical result remained 12,317/12,317 exact M1-to-M5
  matches, 451 events/features/labels, and 69 censored labels.
- 2026-07-27: re-review found five consistency gaps: output-self-referential provenance,
  unshifted `PERIOD_END` membership in G4 and resampling, continuous calendars accepting
  unused session bounds, and unchanged canonical evaluator versioning.
- 2026-07-27: the five consistency gaps were remediated with input-only Git provenance,
  shared interval-start membership, fail-closed calendar validation, canonical version
  `1.1.0`, and a byte-stability regression.

## 12. Completion evidence

Implemented surfaces:

- `pipelines/canonical/`: versioned session contract, analytical/source partition, and
  session-anchored M1-to-M5 resampling;
- `pipelines/source_semantics/`: strict evidence contracts and candidate probe;
- `pipelines/historical_labeling/`: analytical-frame consumption and explicit feature
  ineligibility audit;
- `configs/research/`: KAN-14 semantics and KAN-13 v2 guarded-pilot policies;
- `scripts/run_abshodeh_source_semantics.py`: deterministic fail-closed research runner;
- `tests/` and `tests/research/`: unit, integration, and protected real-data checks;
- `docs/data/` and `docs/audits/artifacts/`: versioned contract and evidence artifact.

Verification:

- ordinary suite: `230 passed, 3 deselected`;
- research suite: `3 passed, 230 deselected`;
- G0-G5: all `PASS`;
- protected M1-to-M5 reconciliation: 12,317/12,317 exact OHLCV;
- canonical/source rows: 50,000 retained;
- analytical rows: 49,962;
- out-of-session rows excluded from analytics: 38;
- real pilot: `ELIGIBLE`, 451 events/features/labels, 69 censored labels;
- explicit feature-ineligible events: 2;
- KAN-14 artifact SHA-256 is computed and reported by the final release check rather
  than embedded here, avoiding a provenance self-reference.
- committed manifest SHA-256 before/after:
  `4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`;
- all 56 protected source hashes are byte-identical before/after;
- manifest verification, git-hygiene verification, `pip check`, and `git diff --check`
  pass.

Human review remains required before merge. Review must confirm the user-evidence record,
the `[09:00, 22:00)` end-exclusive policy, the explicit non-silent exclusion behavior,
and the limitations in section 10. Branch head SHA and Draft PR URL are recorded in the
PR rather than precomputed in this plan.
