from __future__ import annotations

import importlib
from types import SimpleNamespace

from pipelines.characterization import (
    EligibilityClassification,
    TemporalCheckStatus,
)
from pipelines.characterization.fixtures import fixture_catalog
from pipelines.characterization.structure_liquidity import scan_temporal_patterns
from tests.characterization_helpers import artifact, snapshot


def _check(identifier: str, name: str):
    return next(
        item
        for item in snapshot(identifier).temporal_checks
        if item.check == name
    )


def _simple_swing_prices(module_name: str, frame) -> list[float]:
    engine_class = importlib.import_module(module_name).StructuralEngine
    engine = engine_class(SimpleNamespace(df=frame.copy(deep=True)))
    engine.detect_swings(window=2)
    return engine.df["swing_high"].dropna().astype(float).tolist()


def test_static_temporal_scan_records_required_patterns_and_absences() -> None:
    assert _check("vector-structure", "NEGATIVE_SHIFT").status is TemporalCheckStatus.DETECTED
    for identifier in (
        "legacy-structure",
        "vector-structure",
        "legacy-liquidity",
        "vector-liquidity",
    ):
        assert _check(identifier, "WHOLE_SERIES_REDUCTION").status is TemporalCheckStatus.DETECTED
    for implementation in artifact().implementation_snapshots:
        checks = {item.check: item.status for item in implementation.temporal_checks}
        assert checks["CENTERED_ROLLING_WINDOW"] is TemporalCheckStatus.NOT_DETECTED
        assert checks["BACKWARD_FILL"] is TemporalCheckStatus.NOT_DETECTED
        assert checks["WHOLE_SERIES_EXTREMA"] is TemporalCheckStatus.NOT_DETECTED


def test_ast_scanner_detects_each_forbidden_source_pattern() -> None:
    findings = scan_temporal_patterns(
        "series = df['value']\n"
        "future = series.shift(-1)\n"
        "centered = series.rolling(3, center=True).mean()\n"
        "filled = series.bfill()\n"
        "maximum = series.max()\n"
        "average = series.mean()\n"
    )

    assert findings["NEGATIVE_SHIFT"] == (2,)
    assert findings["CENTERED_ROLLING_WINDOW"] == (3,)
    assert findings["BACKWARD_FILL"] == (4,)
    assert findings["WHOLE_SERIES_EXTREMA"] == (5,)
    assert findings["WHOLE_SERIES_REDUCTION"] == (6,)


def test_whole_series_atr_breaks_prefix_invariance_for_simple_engines() -> None:
    fixture = fixture_catalog()["structure-future-atr-leakage-v1"]
    prefix = fixture.frame.iloc[:6]

    for module_name in ("pipelines.legacy.03_structure", "src.structure_engine"):
        assert _simple_swing_prices(module_name, fixture.frame) == [11.0]
        assert _simple_swing_prices(module_name, prefix) == []


def test_layer2_confirmed_pivot_is_prefix_invariant_at_availability() -> None:
    fixture = fixture_catalog()["structure-future-atr-leakage-v1"]
    engine_class = importlib.import_module("src.layer2_structural_engine").StructuralEngine
    engine = engine_class(min_strength=0.0)
    full = engine.detect_swing_highs(fixture.frame.copy(deep=True), lookback=2)
    prefix = engine.detect_swing_highs(fixture.frame.iloc[:6].copy(deep=True), lookback=2)

    assert [(item["index"], item["price"]) for item in full] == [(3, 11.0)]
    assert [(item["index"], item["price"]) for item in prefix] == [(3, 11.0)]


def test_layer3_sweep_is_absent_until_confirmation_candle_exists() -> None:
    fixture = fixture_catalog()["liquidity-bearish-wick-raid-v1"]
    engine_class = importlib.import_module("src.layer3_liquidity_engine").LiquidityEngine
    engine = engine_class(tolerance_atr=0.15)
    swings = [dict(item) for item in fixture.context["swing_highs"]]

    raid_prefix = fixture.frame.iloc[:4].copy(deep=True)
    confirmation_prefix = fixture.frame.iloc[:5].copy(deep=True)
    assert engine.detect_sweeps(raid_prefix, swings, []) == []
    confirmed = engine.detect_sweeps(confirmation_prefix, swings, [])
    assert len(confirmed) == 1
    assert confirmed[0]["index"] == 3
    assert confirmed[0]["confirmation_index"] == 4


def test_every_eligible_event_respects_declared_confirmation_horizon() -> None:
    for implementation in artifact().implementation_snapshots:
        for event in implementation.events:
            if event.eligibility_classification is EligibilityClassification.INELIGIBLE:
                assert event.first_downstream_eligible_timestamp is None
            else:
                assert event.first_downstream_eligible_timestamp is not None
                assert (
                    event.first_downstream_eligible_timestamp
                    >= event.confirmation_or_availability_timestamp
                )


def test_pool_and_destination_temporal_contracts_are_not_invented() -> None:
    assert _check(
        "layer3-liquidity", "POOL_OUTCOME_BEFORE_REGISTRATION"
    ).status is TemporalCheckStatus.PASSED
    assert _check(
        "legacy-liquidity", "POOL_OUTCOME_BEFORE_REGISTRATION"
    ).status is TemporalCheckStatus.BLOCKED
    for identifier in ("legacy-liquidity", "vector-liquidity", "layer3-liquidity", "zone-engine"):
        assert _check(
            identifier, "DESTINATION_RANKING_USES_LATER_CANDLES"
        ).status is TemporalCheckStatus.BLOCKED
