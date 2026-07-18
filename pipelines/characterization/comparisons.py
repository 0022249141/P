"""Pairwise classifications derived after independent freezes."""

from __future__ import annotations

from pipelines.characterization.contracts import Comparison, ComparisonClassification

def _comparisons() -> tuple[Comparison, ...]:
    comparisons = (
        Comparison(
            comparison_id="structure-legacy-vector-swings",
            left_implementation="legacy-structure",
            right_implementation="vector-structure",
            capability="SWING_HIGH_LOW",
            classification=ComparisonClassification.INTENTIONALLY_DIVERGENT,
            evidence="The vector surface emits extra pivots and accepts a candidate with one right candle; source hashes differ.",
            fixture_ids=(
                "structure-confirmed-pivots-v1",
                "structure-insufficient-right-confirmation-v1",
            ),
        ),
        Comparison(
            comparison_id="structure-legacy-layer2-confirmed-pivots",
            left_implementation="legacy-structure",
            right_implementation="layer2-structure",
            capability="CONFIRMED_SWING_HIGH_LOW",
            classification=ComparisonClassification.EQUIVALENT_WITH_PARAMETER_MAPPING,
            evidence="The selected confirmed high/low fixture matches after mapping legacy window=2 to layer2 lookback=2 and min_strength=0.0; this is fixture equivalence only.",
            fixture_ids=("structure-confirmed-pivots-v1",),
            parameter_mapping=("legacy.window=2", "layer2.lookback=2", "layer2.min_strength=0.0"),
        ),
        Comparison(
            comparison_id="structure-vector-layer2-swings",
            left_implementation="vector-structure",
            right_implementation="layer2-structure",
            capability="SWING_HIGH_LOW",
            classification=ComparisonClassification.INTENTIONALLY_DIVERGENT,
            evidence="Vector alignment emits additional pivots and insufficient-right output that symmetric layer2 does not emit.",
            fixture_ids=(
                "structure-confirmed-pivots-v1",
                "structure-insufficient-right-confirmation-v1",
            ),
        ),
        Comparison(
            comparison_id="structure-simple-layer2-temporal-safety",
            left_implementation="legacy-structure",
            right_implementation="layer2-structure",
            capability="PREFIX_INVARIANCE",
            classification=ComparisonClassification.FUTURE_DERIVED_UNSAFE,
            evidence="Legacy whole-series ATR makes a nominally confirmed pivot depend on later candles; layer2 stays stable at its declared availability.",
            fixture_ids=("structure-future-atr-leakage-v1",),
        ),
        Comparison(
            comparison_id="structure-mss-all-surfaces",
            left_implementation="legacy-structure",
            right_implementation="layer2-structure",
            capability="MSS",
            classification=ComparisonClassification.BLOCKED_BY_MISSING_SEMANTICS,
            evidence="No listed structure surface emits a complete or incomplete MSS sequence contract.",
            fixture_ids=(
                "structure-mss-valid-sequence-v1",
                "structure-mss-incomplete-sequence-v1",
            ),
        ),
        Comparison(
            comparison_id="liquidity-legacy-vector",
            left_implementation="legacy-liquidity",
            right_implementation="vector-liquidity",
            capability="ALL_EXPOSED_BEHAVIOR",
            classification=ComparisonClassification.EQUIVALENT,
            evidence="The files are byte-identical and independent freezes produce identical cluster events and the same committed-config failure.",
            fixture_ids=("liquidity-equal-levels-v1",),
        ),
        Comparison(
            comparison_id="liquidity-legacy-layer3",
            left_implementation="legacy-liquidity",
            right_implementation="layer3-liquidity",
            capability="SWEEP_AND_EQUAL_LEVELS",
            classification=ComparisonClassification.INTENTIONALLY_DIVERGENT,
            evidence="Simple liquidity uses internal clustering/same-candle scoring, while layer3 emits prior-touch counts and next-candle-confirmed sweep records.",
            fixture_ids=(
                "liquidity-equal-levels-v1",
                "liquidity-bearish-wick-raid-v1",
            ),
        ),
        Comparison(
            comparison_id="liquidity-vector-layer3",
            left_implementation="vector-liquidity",
            right_implementation="layer3-liquidity",
            capability="SWEEP_AND_EQUAL_LEVELS",
            classification=ComparisonClassification.INTENTIONALLY_DIVERGENT,
            evidence="The byte-duplicate simple surface and layer3 expose different outputs, parameters, and confirmation horizons.",
            fixture_ids=(
                "liquidity-equal-levels-v1",
                "liquidity-bullish-wick-raid-v1",
            ),
        ),
        Comparison(
            comparison_id="liquidity-legacy-zone",
            left_implementation="legacy-liquidity",
            right_implementation="zone-engine",
            capability="LIQUIDITY_LIFECYCLE_AND_RANKING",
            classification=ComparisonClassification.BLOCKED_BY_MISSING_SEMANTICS,
            evidence="Neither surface exposes the required lifecycle and destination-ranking contract; ZoneEngine is FVG/order-block focused.",
            fixture_ids=("liquidity-multiple-destinations-v1",),
        ),
        Comparison(
            comparison_id="liquidity-vector-zone",
            left_implementation="vector-liquidity",
            right_implementation="zone-engine",
            capability="LIQUIDITY_LIFECYCLE_AND_RANKING",
            classification=ComparisonClassification.BLOCKED_BY_MISSING_SEMANTICS,
            evidence="The compared sources do not expose compatible lifecycle or ranking semantics.",
            fixture_ids=("liquidity-multiple-destinations-v1",),
        ),
        Comparison(
            comparison_id="liquidity-layer3-zone",
            left_implementation="layer3-liquidity",
            right_implementation="zone-engine",
            capability="LIQUIDITY_LIFECYCLE_AND_RANKING",
            classification=ComparisonClassification.BLOCKED_BY_MISSING_SEMANTICS,
            evidence="Layer3 has resting/sweep proxies but no reclaim, acceptance, or rank; ZoneEngine exposes none of those liquidity semantics.",
            fixture_ids=(
                "liquidity-pool-registration-v1",
                "liquidity-multiple-destinations-v1",
            ),
        ),
    )
    return tuple(sorted(comparisons, key=lambda item: item.comparison_id))
