# KAN-11 Structure and Liquidity Characterization

## Scope

This audit freezes the seven existing structure and liquidity surfaces on 14 small,
deterministic synthetic fixtures. It does not choose a canonical engine, change an
algorithm, repair temporal leakage, or add missing market semantics.

The machine-readable evidence is
`docs/audits/artifacts/KAN-11-structure-liquidity-comparison.json`. Every normalized
event records its implementation, event type, direction, historical origin/pivot,
observation timestamp, confirmation/availability timestamp, first downstream-eligible
timestamp, price/level, temporal classification, fixture identifier, and fixture
SHA-256. The artifact contains no protected-corpus data or environment-derived values.

## Frozen Sources

| Implementation | Repository path | Source SHA-256 | Normalized events |
| --- | --- | --- | ---: |
| `legacy-structure` | `pipelines/legacy/03_structure.py` | `da7fcd74639dd6f08dc7db2031bae99ff614e1304b752353894b28a8581cb435` | 5 |
| `vector-structure` | `src/structure_engine.py` | `9244891f9caf9100b255b1f7f410b3f3a3d5b53ce8272151c496261953709a3e` | 6 |
| `layer2-structure` | `src/layer2_structural_engine.py` | `74406477903916ababd4db7ce25b4e459e576e4bcce15bf52ff4a6ebb44d2310` | 9 |
| `legacy-liquidity` | `pipelines/legacy/04_liquidity.py` | `c42c1c76948f35b1091222e8ea3f1d46d7517a934c5dca26554c67bd3c4c5679` | 2 |
| `vector-liquidity` | `src/liquidity_engine.py` | `c42c1c76948f35b1091222e8ea3f1d46d7517a934c5dca26554c67bd3c4c5679` | 2 |
| `layer3-liquidity` | `src/layer3_liquidity_engine.py` | `f7f8b34135bcd4e6e9badd8f2c3024fbb73c08716cf6627ad0bf5600c51ce04c` | 17 |
| `zone-engine` | `src/zone_engine.py` | `fde09c7776f2e0b449c06f3b9191f35e5ddf7b0362ddb32ba659d55fbb9e8e37` | 0 |

The two simple liquidity files are byte-identical. Their clustering helper is
characterized independently and produces identical normalized events. Their public
`detect_sweeps` path is blocked by the committed configuration because
`liquidity_sweep_threshold_pct` is absent. The audit records that deterministic failure
and does not patch the configuration.

## Structure Behavior

| Behavior | Legacy structure | Vector structure | Layer 2 structure |
| --- | --- | --- | --- |
| Confirmed swing high/low | Observed at pivot row; two right candles; complete-frame ATR mean makes the result `INELIGIBLE`. | Observed at pivot row; negative-shift alignment effectively accepts one right candle; complete-frame ATR mean makes the result `INELIGIBLE`. | Observed at pivot row; symmetric right lookback; adapter delays use to confirmation as `POST_CONFIRMATION`. |
| Insufficient right confirmation | Candidate with one right candle is not emitted. | Candidate with one right candle is emitted and explicitly classified `INELIGIBLE`. | Candidate with one right candle is not emitted for `lookback=2`. |
| Bullish/bearish BOS | `is_bos` uses close displacement but selects the final non-null swing from the complete frame, so normalized events are `INELIGIBLE`. | Not exposed. | Both directions observed using wick penetration; fixture events are eligible only after referenced swing confirmation. |
| Bullish/bearish CHoCH | Not exposed. | Not exposed. | Both transitions observed from the internal trend state, using wick penetration. |
| Valid/incomplete MSS | `BLOCKED_BY_MISSING_SEMANTICS`. | `BLOCKED_BY_MISSING_SEMANTICS`. | Mentioned in prose but not implemented; both sequences remain blocked. |

The layer 2 wick rule is frozen as observed behavior. It diverges from the governed
close-based BOS/CHoCH definition and is not repaired by this task.

## Liquidity Behavior

| Behavior | Observed characterization |
| --- | --- |
| Equal highs/lows | Simple engines expose deterministic ATR-gap clustering only. Layer 3 emits prior-touch counts at the current third-or-later touch using past candles. |
| BSL/SSL registration | Layer 3 `RESTING_HIGH`/`RESTING_LOW` outputs are retained as explicit `BSL_REGISTRATION_PROXY`/`SSL_REGISTRATION_PROXY` adapter mappings. They are OHLCV proxies, not evidence of resting orders. |
| Untouched | Layer 3 resting membership is frozen as `UNTOUCHED_BSL_PROXY`/`UNTOUCHED_SSL_PROXY` after supplied swing confirmation. |
| Swept | Layer 3 observes high-side and low-side raids only after the next candle reverses. Output written at the raid row is downstream-eligible only at the confirmation candle. |
| Reclaimed | `BLOCKED_BY_MISSING_SEMANTICS`; no source emits a reclaim state or confirmation rule. |
| Accepted | `BLOCKED_BY_MISSING_SEMANTICS`; layer 3 mitigation scores distinguish wick-only (`0.70`) from close-through (`0.95`) on the selected fixture, but this is not an acceptance/hold contract. |
| Multiple destinations | Candidate order is deterministic source/input order, but no score, rank, tie policy, direction filter, or as-of contract exists. Ranking remains blocked. |
| Zone engine | Exposes FVG/order-block scores, not BSL/SSL, sweep lifecycle, or destination ranking. |

Every synthetic layer 3 sweep references a supplied pool whose confirmation precedes
the raid. No pool outcome is promoted when registration evidence is absent.

## Comparison Classifications

| Comparison | Capability | Classification | Evidence summary |
| --- | --- | --- | --- |
| Legacy vs vector structure | Swing high/low | `INTENTIONALLY_DIVERGENT` | Vector emits extra pivots and accepts the one-right-candle candidate. |
| Legacy vs layer 2 structure | Confirmed pivots | `EQUIVALENT_WITH_PARAMETER_MAPPING` | Selected fixture matches for `window=2`, `lookback=2`, `min_strength=0.0`; fixture equivalence only. |
| Vector vs layer 2 structure | Swing high/low | `INTENTIONALLY_DIVERGENT` | Vector alignment produces additional and insufficient-right outputs. |
| Legacy vs layer 2 structure | Prefix invariance | `FUTURE_DERIVED_UNSAFE` | Future ATR values change a legacy pivot after its nominal confirmation; layer 2 remains stable. |
| All structure surfaces | MSS | `BLOCKED_BY_MISSING_SEMANTICS` | No complete or incomplete MSS output contract exists. |
| Legacy vs vector liquidity | All exposed behavior | `EQUIVALENT` | Files are byte-identical; independent freezes and committed-config failure match. |
| Legacy vs layer 3 liquidity | Sweep/equal levels | `INTENTIONALLY_DIVERGENT` | Internal same-candle score differs from layer 3 counts and next-candle confirmation. |
| Vector vs layer 3 liquidity | Sweep/equal levels | `INTENTIONALLY_DIVERGENT` | Output shape, parameters, and confirmation horizons differ. |
| Legacy vs zone engine | Lifecycle/ranking | `BLOCKED_BY_MISSING_SEMANTICS` | No compatible lifecycle or ranking contract exists. |
| Vector vs zone engine | Lifecycle/ranking | `BLOCKED_BY_MISSING_SEMANTICS` | No compatible lifecycle or ranking contract exists. |
| Layer 3 vs zone engine | Lifecycle/ranking | `BLOCKED_BY_MISSING_SEMANTICS` | Layer 3 has resting/sweep proxies only; zone engine exposes neither contract. |

## Temporal Audit

An AST scan and dynamic prefix/truncation fixtures record the following:

- Negative `shift(-1)` is detected in `src/structure_engine.py`.
- No centered rolling window is detected in the seven audited files.
- No backward fill is detected in the seven audited files.
- No direct whole-series min/max extrema call is detected. Separate unsafe complete-frame
  reductions and level selection are recorded rather than mislabeled as extrema.
- Complete-frame ATR means are detected in both simple structure files and both simple
  liquidity files.
- The legacy BOS method selects the final non-null swing from the complete frame; adding
  a later swing changes an earlier BOS result.
- All swing engines require future pivot confirmation, but only layer 2 has a stable
  downstream horizon on the tested prefix. Simple swing outputs remain `INELIGIBLE` due
  to the complete-frame ATR threshold.
- Layer 3 sweeps consume candle `i+1`, record `confirmation_index=i+1`, and write the
  flag at raid candle `i`. The normalized event is `POST_CONFIRMATION` and first eligible
  at `i+1`.
- Layer 3 resting output is calculated from a complete sweep list without an as-of
  timestamp. It cannot be treated as a historical lifecycle state.
- Destination ranking cannot be tested for later-candle dependence because no ranking
  semantics exist; it remains blocked rather than synthesized.

## Limits

This evidence covers deterministic software behavior on selected fixtures, not universal
mathematical equivalence, profitability, execution readiness, or institutional intent.
No protected research dataset is used by ordinary characterization tests. G0-G5 behavior
is untouched, and G6-G9 remain `NOT_EVALUATED`.
