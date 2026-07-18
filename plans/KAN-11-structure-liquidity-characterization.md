# KAN-11 Structure and Liquidity Characterization Plan

## 1. Objective

Freeze, compare, and audit the repository's existing structure and liquidity behavior
before any migration, consolidation, threshold change, or analytical rewrite. The
deliverable will provide deterministic fixture-backed observations, explicit origin and
availability timestamps, temporal-safety classifications, a machine-readable comparison
artifact, and human-readable limitations without changing engine algorithms.

This is a characterization boundary only. It does not choose a canonical algorithm,
repair unsafe behavior, implement missing market semantics, wire G6-G9, or move any
engine file.

## 2. Jira and Specification Trace

Jira key: `KAN-11` - Characterize Structure and Liquidity Behavior.

Specifications and audit evidence read before this first tracked edit:

- `AGENTS.md`
- `PLANS.md`
- `PROJECT_SPEC.md`
- `DATA_CONTRACT.md`
- `DOMAIN_RULES.md`
- `ACCEPTANCE_CRITERIA.md`
- `docs/audits/migration-backlog.md`
- `docs/audits/characterization-test-matrix.md`
- `docs/architecture/current-to-target-map.md`

The historical migration backlog calls structure/liquidity characterization KAN-5 and
architecture migration KAN-11. This plan follows the currently approved Jira key KAN-11
without rewriting historical audit records.

Acceptance trace:

- Confirmed swing records expose pivot/origin and confirmation/availability timestamps.
- Eligible outputs never appear before their confirmation evidence is available.
- BOS, CHoCH, and any MSS observation preserve current behavior and disclose whether the
  source uses wick or close confirmation.
- Liquidity pools are observed before any sweep/reclaim/acceptance characterization.
- Equal levels, BSL/SSL mappings, pool states, and multiple destination candidates are
  fixture-backed; absent source semantics are blocked rather than invented.
- Every duplicate pair receives one approved comparison classification.
- Static and prefix-invariance checks expose future shifts, centered windows, backfill,
  whole-series extrema/reductions, and other future-derived behavior.
- Deterministic JSON generation is byte-identical across reruns.
- Ordinary tests use only small synthetic data and do not open protected research CSVs.
- Protected datasets, the committed dataset manifest, canonical KAN-10 behavior, and
  G6-G9 statuses remain unchanged.

## 3. Current-State Evidence

Repository and branch state:

- Requested worktree: `P-KAN-11-structure-liquidity-characterization`.
- Local branch tracks the existing remote branch
  `origin/KAN-11-structure-liquidity-characterization`.
- Branch, `origin/main`, and the current main merge commit all resolve to
  `d429ed2fd0f2a1d654f26197acfd8bb89b92fae9` (`KAN-10 Add canonical data quality
  gates (#27)`).
- The sibling worktree was clean before this plan; the dirty primary checkout was not
  modified.
- No pull request currently exists for the KAN-11 head branch.

Protected-data baseline, independently recomputed from sorted tracked paths and bytes:

- CSV paths: 56.
- Bytes: 90,960,790.
- Aggregate SHA-256: `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`.
- Committed manifest SHA-256:
  `4d6c65d91a3c67448b60ba2e499ceea14e7536cd69b12c873fae06f8a7afceb1`.

Observed structure surfaces:

| Surface | Observed behavior before characterization |
| --- | --- |
| `pipelines/legacy/03_structure.py` | Left-window candidate plus two right-side confirmation candles; writes the swing value at the pivot row; uses whole-series mean ATR; `is_bos` selects the final non-null swing in the full frame and applies a market displacement percentage. No CHoCH or MSS API. |
| `src/structure_engine.py` | Vectorized swing flags with negative shifts/right-side rolling expressions; writes output at the pivot row; uses whole-series mean ATR. No BOS, CHoCH, or MSS API. Source SHA differs from legacy structure. |
| `src/layer2_structural_engine.py` | Symmetric left/right swing search and strength calculation; emits pivot timestamp only; BOS/CHoCH use high/low wick penetration, despite the governed close-based definition; stores swing lists in `DataFrame.attrs`. Mentions MSS in prose but implements no MSS sequence. |

Observed liquidity surfaces:

| Surface | Observed behavior before characterization |
| --- | --- |
| `pipelines/legacy/04_liquidity.py` | Clusters only prior swing/high-low values, computes same-candle penetration/reclaim score, uses whole-series mean ATR for a dynamic threshold, and writes a scalar score at the evaluated row. It has no explicit pool lifecycle or destination ranking. |
| `src/liquidity_engine.py` | Byte-identical to legacy liquidity; both files have SHA-256 `c42c1c76948f35b1091222e8ea3f1d46d7517a934c5dca26554c67bd3c4c5679`. |
| `src/layer3_liquidity_engine.py` | Equal-level counts use prior bars; sweep detection consumes supplied swings and requires the next candle to reverse, records `confirmation_index = i + 1`, but writes `is_sweep` at raid index `i`; resting liquidity is derived after considering the complete sweep list. No accepted/reclaimed lifecycle model or destination rank exists. |
| `src/zone_engine.py` | Detects FVG/order-block candidates from displacement and recent ATR. It does not register BSL/SSL, model sweep/reclaim/acceptance states, or rank liquidity destinations. |

Existing pytest coverage is smoke-level for these surfaces. `tests/test_layer1_2.py`
constructs a synthetic CSV but mutates `sys.path` and asserts only columns/length;
`tests/test_all_layers.py` contains print-only placeholders. Runner scripts under
`tests/run_*.py` are not assertion-backed characterization tests.

## 4. Assumptions and Domain Questions

Implementation assumptions:

- Synthetic fixtures express software invariants, not claims that a sequence is a
  representative market sample.
- A characterization event may map a source output into a normalized audit record, but
  the record must retain source path, source field/type, parameters, raw origin index,
  and raw output. Mapping `RESTING_HIGH` to candidate BSL and `RESTING_LOW` to candidate
  SSL is an explicit adapter mapping, not proof of resting orders.
- For symmetric pivots, availability is pivot index plus the configured right lookback.
  For the simple legacy/vector implementations, the observed two-right-candle dependency
  is recorded as availability at pivot index plus two. The engine's pivot-row output is
  therefore `POST_CONFIRMATION`, not real-time eligible at pivot time.
- A layer-3 sweep origin is the raid candle and availability is its recorded
  `confirmation_index`. Writing the flag on the raid row remains frozen but is labeled
  future-derived for real-time use.
- Prefix-invariance means rerunning on data available through time `t` must not change an
  output already declared eligible at or before `t`. Expected right-side confirmation is
  compared only after its declared availability.
- Static findings and dynamic fixture observations are separate evidence. A source token
  such as `shift(-1)` is not by itself proof of every output's leakage, while a changed
  prefix output is direct evidence of future dependence.
- Pairwise classification is deterministic and limited to:
  `EQUIVALENT`, `EQUIVALENT_WITH_PARAMETER_MAPPING`, `INTENTIONALLY_DIVERGENT`,
  `FUTURE_DERIVED_UNSAFE`, or `BLOCKED_BY_MISSING_SEMANTICS`.

Unresolved semantics that must remain blocked rather than implemented:

- No source defines a complete MSS contract of CHoCH, new swing, and confirming BOS.
- No source defines an auditable `UNTOUCHED -> SWEPT -> RECLAIMED/ACCEPTED` state machine
  with close-count/holding parameters.
- The simple liquidity score combines a same-candle reclaim component but does not emit a
  reclaim state or its confirmation time.
- Layer 3 models next-candle reversal sweeps but does not separately define close-based
  acceptance.
- No listed surface defines destination-ranking weights, tie policy, direction filter,
  invalidation, or as-of evidence contract. Stable source/input order is not silently
  relabeled as analytical rank.
- Governed BOS/CHoCH definitions are close-based, while layer 2 currently checks wicks.
  Characterization will freeze and label this divergence; changing it requires a later
  approved analytical task.
- The engines do not carry dataset timezone, period semantics, or G6 evidence. Fixtures
  use explicit UTC timestamps, while G6-G9 remain `NOT_EVALUATED` under KAN-10.

## 5. Proposed Architecture

Add a separate, read-only characterization boundary without modifying engine files:

```text
pipelines/characterization/
  __init__.py
  comparisons.py
  contracts.py
  fixtures.py
  liquidity_adapters.py
  source_audit.py
  structure_adapters.py
  structure_liquidity.py
scripts/
  generate_structure_liquidity_characterization.py
docs/audits/
  structure-liquidity-characterization.md
  artifacts/KAN-11-structure-liquidity-comparison.json
tests/
  characterization_helpers.py
  test_structure_characterization.py
  test_liquidity_characterization.py
  test_structure_liquidity_temporal_safety.py
  test_structure_liquidity_artifact.py
```

`contracts.py` will own strict, immutable, versioned Pydantic contracts for surface IDs,
scenario IDs, temporal eligibility, source observations, pair classifications,
limitations, and deterministic sorted JSON serialization. Payloads will contain no
wall-clock time, host/user name, absolute path, or random identifier.

`structure_liquidity.py` will provide explicit adapters that invoke existing public
methods against copied in-memory frames. Adapters will not alter thresholds, patch
engine state, sort source outputs into a preferred answer, or hide raw observations.
They will add audit metadata outside the source objects: origin timestamp, availability
timestamp, evidence horizon, source parameters, and eligibility label.

The generator will run the approved synthetic scenario matrix, compute repository-relative
source hashes, include static temporal findings, sort all records deterministically, and
write the canonical JSON artifact only when bytes differ. The same builder will be used
by tests to prove the committed artifact is current and byte-identical on two reruns.

The human-readable audit will explain each implementation's observed behavior,
equivalence/divergence table, temporal limitations, missing semantics, and migration
blockers. It will not recommend consolidation beyond what evidence supports.

## 6. File-Level Change Map

Create:

- `plans/KAN-11-structure-liquidity-characterization.md`
- `pipelines/characterization/__init__.py`
- `pipelines/characterization/comparisons.py`
- `pipelines/characterization/contracts.py`
- `pipelines/characterization/fixtures.py`
- `pipelines/characterization/liquidity_adapters.py`
- `pipelines/characterization/source_audit.py`
- `pipelines/characterization/structure_adapters.py`
- `pipelines/characterization/structure_liquidity.py`
- `scripts/generate_structure_liquidity_characterization.py`
- `docs/audits/structure-liquidity-characterization.md`
- `docs/audits/artifacts/KAN-11-structure-liquidity-comparison.json`
- small synthetic fixture builders and focused structure/liquidity/temporal/artifact tests

Modify only if required by observed testability:

- `pyproject.toml` only if explicit test markers or package discovery need adjustment;
  current `pipelines*` discovery should already include the proposed package.
- The execution plan as a living command/decision log.

Leave untouched:

- all seven structure, liquidity, and zone engine source files
- `raw_data/`, `data_clean/`, `data_features/`
- `data/manifests/committed_datasets.json`
- KAN-10 canonical contracts, quality gates, resampling, reconciliation, and eligibility
- analytical thresholds, ATR coefficients, BOS/CHoCH rules, sweep formulas, and weights
- live/broker, reporting, scoring, backtest, and execution surfaces

No file will be moved, renamed, consolidated, deprecated, or deleted.

## 7. Implementation Steps

1. Capture baseline Python/test, import, protected-data, source-hash, and worktree evidence.
2. Add versioned characterization contracts and deterministic serialization.
3. Add tiny UTC synthetic fixture builders for confirmed/incomplete pivots, bullish and
   bearish breaks, equal highs/lows, pool lifecycle probes, wick/close differences, and
   multiple candidate destinations.
4. Add non-mutating adapters for all seven surfaces and retain raw source outputs.
5. Freeze swing-high/low and insufficient-right-confirmation behavior with origin and
   availability timestamps.
6. Freeze bullish/bearish BOS and CHoCH behavior; represent valid/incomplete MSS scenarios
   as observed capability or `BLOCKED_BY_MISSING_SEMANTICS`, never synthesized events.
7. Freeze equal-level, candidate BSL/SSL, sweep, resting/untouched, reclaim/acceptance,
   wick-only raid, and candidate-order behavior. Missing lifecycle/ranking behavior remains
   explicitly blocked.
8. Add AST/static temporal checks and dynamic prefix-invariance tests. Mark outputs
   `REALTIME_ELIGIBLE`, `POST_CONFIRMATION`, or `INELIGIBLE` according to evidence.
9. Generate the deterministic JSON artifact twice, compare bytes, and write the audit
   documentation and pairwise classification table.
10. Run the complete local verification and independently recompute protected hashes.
11. Commit and push the existing KAN-11 branch, then create exactly one draft PR with the
    required title, wait for GitHub Actions, and stop for human review without merging.

Each slice leaves existing engine behavior runnable because the characterization layer is
additive and engine files remain unchanged.

## 8. Verification

Planned focused commands:

```powershell
python -m pytest -q tests/test_structure_characterization.py tests/test_liquidity_characterization.py
python -m pytest -q tests/test_structure_liquidity_temporal_safety.py
python -m pytest -q tests/test_structure_liquidity_artifact.py
python scripts/generate_structure_liquidity_characterization.py
python scripts/generate_structure_liquidity_characterization.py
git diff --exit-code -- docs/audits/artifacts/KAN-11-structure-liquidity-comparison.json
```

Planned repository checks:

```powershell
python -m pytest -q
python -m pytest -q -m research tests/research
python scripts/verify_dataset_manifest.py
python scripts/verify_git_hygiene.py --skip-dataset-integrity
python -m pip check
git diff --check
```

Additional checks:

- import safety for characterization modules and every engine surface used by adapters
- no `sys.path` mutation in new code
- deterministic artifact and normalized event reruns are byte-identical
- prefix-invariance and declared-availability checks for every eligible event type
- source files under the seven listed engine paths have unchanged hashes
- G6-G9 remain `NOT_EVALUATED`
- protected path count, aggregate bytes, aggregate SHA-256, and manifest SHA-256 match the
  baseline above
- GitHub Actions passes for both push and pull-request events

## 9. Data and Migration Impact

No dataset migration or analytical migration is permitted. All fixtures are small,
deterministic, in-memory values (or tiny dedicated synthetic fixture files if reviewability
requires them). Ordinary tests cannot access protected corpus paths under the existing
runtime guard.

The committed JSON is an audit artifact generated from synthetic scenarios and source
hashes. It is not market data, a feature dataset, a trading signal, or a claim of
representativeness. Rollback is a normal revert of the additive characterization commit;
no history rewrite, force push, dataset rebuild, or compatibility migration is involved.

## 10. Risks and Limitations

- Characterization freezes defects as evidence; it does not make future-derived output
  safe. Consumers must honor temporal eligibility and availability timestamps.
- Whole-series mean ATR can make prefix results depend on later volatility even when the
  explicit candidate window is past-only.
- Swing confirmation is visually attributed to a pivot but unavailable until right-side
  candles close; using the pivot row in a real-time backtest would repaint.
- Wick-based layer-2 BOS/CHoCH differs from the governed close-based definition and cannot
  be promoted to canonical behavior in this task.
- OHLCV does not observe resting orders or institutional intent. BSL/SSL and sweep labels
  remain deterministic proxy classifications.
- Missing spread, fills, order flow, holiday/session evidence, and execution costs are out
  of scope and cannot support execution-readiness claims.
- No out-of-sample, statistical, survivorship, or profitability claim is made. G6-G9
  remain not evaluated.
- An exact match on selected fixtures proves fixture equivalence only, not universal
  mathematical equivalence. Source hashes and parameter mappings remain part of the
  evidence.

## 11. Progress Log

| Date | Command or decision | Result |
| --- | --- | --- |
| 2026-07-18 | First `git fetch origin` | Failed with a transient SSH connection timeout; no repository change occurred. |
| 2026-07-18 | Retry `git fetch origin` | Passed; discovered the existing KAN-11 remote branch and current main `d429ed2`. |
| 2026-07-18 | Worktree/branch audit | Target sibling path was free; no local KAN-11 branch or existing KAN-11 PR existed. |
| 2026-07-18 | `git worktree add --track -b KAN-11-structure-liquidity-characterization ...` | Passed; attached a local tracking branch to the existing remote branch. |
| 2026-07-18 | Base verification | Passed: KAN-11 and `origin/main` are identical at current merge commit `d429ed2`. |
| 2026-07-18 | Governance and audit review | Read every required specification, backlog, characterization matrix, and architecture map. |
| 2026-07-18 | Seven-surface source audit | Confirmed duplicate/simple/layered behavior, future-derived operations, missing lifecycle/MSS/ranking semantics, and no current characterization coverage. |
| 2026-07-18 | Protected-data baseline | Passed: 56 CSVs, 90,960,790 bytes, expected aggregate and manifest SHA-256 values. |
| 2026-07-18 | Created this execution plan | First tracked edit. Engine behavior remains unchanged; implementation awaits explicit continuation after plan review. |
| 2026-07-18 | Human planning checkpoint | Approved; implementation continued only in the isolated KAN-11 worktree. |
| 2026-07-18 | First direct generator run with system Python | Failed because the system interpreter had neither the editable package nor `pytest`; no artifact was written by that failed run. |
| 2026-07-18 | `py -3.11 -m venv .venv` and `python -m pip install -e ".[test]"` | The combined shell command timed out while pip continued as a child process. The process completed after 59.9 additional seconds; fresh Python 3.11 environment has pip 26.1.2 and pytest 9.1.1. |
| 2026-07-18 | Initial focused characterization suite | Failed: 25 passed, 2 failed. Both were harness defects (NumPy boolean identity and packaging metadata blocked by the import guard), not analytical differences. Corrected without touching engines. |
| 2026-07-18 | Direct generator under the fresh editable environment | Failed first on unpackaged `market_params`, then on namespace-style `src`; adapter now loads the exact repository modules by path without `sys.path` mutation or package-boundary changes. |
| 2026-07-18 | AST temporal scanner | Added and tested detection for negative shift, centered rolling, backward fill, whole-series extrema, and whole-series reductions. |
| 2026-07-18 | Final focused characterization suite | Passed: 28 tests in 4.47 seconds. |
| 2026-07-18 | Generator rerun check | Passed: two no-op reruns and `--check`; artifact SHA-256 remained `24393818414c659e33182d5cb929f50f11f96bf97dd29325c4615f72d6b554bd`. |
| 2026-07-18 | `python -m pytest -q` | Passed: 148 tests, 1 research test deselected, 19.10 seconds. |
| 2026-07-18 | `python -m pytest -q -m research tests/research` | Passed: 1 test in 0.03 seconds. |
| 2026-07-18 | `python scripts/verify_dataset_manifest.py` | Passed. |
| 2026-07-18 | `python scripts/verify_git_hygiene.py --skip-dataset-integrity` | Passed: no forbidden paths, ignore failures, gitlinks, or submodule errors; protected corpus was not opened by this command. |
| 2026-07-18 | `python -m pip check` | Passed: no broken requirements. |
| 2026-07-18 | Protected-data and source-hash audit | Passed: 56 CSVs, 90,960,790 bytes, aggregate/manifest SHA-256 unchanged; all seven engine source hashes unchanged. |
| 2026-07-18 | `git diff --check` | Passed before staging. |
| 2026-07-18 | Staged-diff modularity review | Split the new 1,324-line adapter module into focused source-audit, structure, liquidity, comparison, and orchestration modules; no generated bytes or engine sources changed. |
| 2026-07-18 | Post-split focused suite | Passed: 28 tests in 6.10 seconds. |
| 2026-07-18 | Post-split ordinary suite | Passed: 148 tests, 1 research test deselected, 11.70 seconds. |

## 12. Completion Evidence

Planning checkpoint and local implementation are complete. The additive characterization
boundary freezes all seven implementations independently, records explicit temporal
provenance for every emitted event, generates deterministic synthetic-only evidence, and
documents every required pairwise classification. All seven analytical source files,
protected datasets, the committed manifest, canonical G0-G5 behavior, and G6-G9 status are
unchanged.

Commit, push, one draft PR, and both push/pull-request GitHub Actions results remain
pending at this point in the log. The PR will remain draft, open, and unmerged for human
review.
