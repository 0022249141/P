from __future__ import annotations

import importlib
from types import SimpleNamespace

from pipelines.characterization import (
    CapabilityStatus,
    Direction,
    EligibilityClassification,
)
from pipelines.characterization.fixtures import fixture_catalog
from pipelines.characterization.structure_liquidity import EXPECTED_SOURCE_SHA256
from tests.characterization_helpers import snapshot


STRUCTURE_IMPLEMENTATIONS = (
    "legacy-structure",
    "vector-structure",
    "layer2-structure",
)


def _events(identifier: str, fixture_id: str, event_type: str):
    return [
        event
        for event in snapshot(identifier).events
        if event.source_fixture == fixture_id and event.event_type == event_type
    ]


def _capability(identifier: str, capability: str):
    return next(
        item
        for item in snapshot(identifier).capabilities
        if item.capability == capability
    )


def test_structure_source_hashes_freeze_each_engine_unchanged() -> None:
    for identifier in STRUCTURE_IMPLEMENTATIONS:
        assert snapshot(identifier).source_sha256 == EXPECTED_SOURCE_SHA256[identifier]


def test_confirmed_high_and_low_are_frozen_independently() -> None:
    fixture_id = "structure-confirmed-pivots-v1"
    legacy = _events("legacy-structure", fixture_id, "SWING_HIGH") + _events(
        "legacy-structure", fixture_id, "SWING_LOW"
    )
    vector = _events("vector-structure", fixture_id, "SWING_HIGH") + _events(
        "vector-structure", fixture_id, "SWING_LOW"
    )
    layer2 = _events("layer2-structure", fixture_id, "SWING_HIGH") + _events(
        "layer2-structure", fixture_id, "SWING_LOW"
    )

    assert [(event.event_type, event.observed_price_or_level) for event in legacy] == [
        ("SWING_HIGH", 16.0),
        ("SWING_LOW", 7.0),
    ]
    assert sorted((event.event_type, event.observed_price_or_level) for event in vector) == [
        ("SWING_HIGH", 13.0),
        ("SWING_HIGH", 16.0),
        ("SWING_LOW", 7.0),
        ("SWING_LOW", 9.0),
    ]
    assert [(event.event_type, event.observed_price_or_level) for event in layer2] == [
        ("SWING_HIGH", 16.0),
        ("SWING_LOW", 7.0),
    ]


def test_pivot_origin_confirmation_and_eligibility_are_distinct() -> None:
    event = _events(
        "layer2-structure", "structure-confirmed-pivots-v1", "SWING_HIGH"
    )[0]

    assert event.origin_or_pivot_timestamp == "2025-01-01T00:15:00Z"
    assert event.observation_timestamp == event.origin_or_pivot_timestamp
    assert event.confirmation_or_availability_timestamp == "2025-01-01T00:25:00Z"
    assert event.first_downstream_eligible_timestamp == "2025-01-01T00:25:00Z"
    assert event.eligibility_classification is EligibilityClassification.POST_CONFIRMATION


def test_insufficient_right_confirmation_exposes_vector_divergence() -> None:
    fixture_id = "structure-insufficient-right-confirmation-v1"

    assert _events("legacy-structure", fixture_id, "SWING_HIGH") == []
    assert _events("layer2-structure", fixture_id, "SWING_HIGH") == []
    vector = _events("vector-structure", fixture_id, "SWING_HIGH")
    assert len(vector) == 1
    assert vector[0].observed_price_or_level == 16.0
    assert vector[0].confirmation_or_availability_timestamp == "2025-01-02T00:25:00Z"
    assert vector[0].eligibility_classification is EligibilityClassification.INELIGIBLE


def test_bullish_and_bearish_bos_and_choch_are_characterized() -> None:
    simple_bos = _events("legacy-structure", "structure-simple-bos-v1", "BOS")
    layer2_bos = _events(
        "layer2-structure", "structure-layer2-break-sequence-v1", "BOS"
    )
    layer2_choch = _events(
        "layer2-structure", "structure-layer2-break-sequence-v1", "CHOCH"
    )

    assert {event.direction for event in simple_bos} == {
        Direction.BULLISH,
        Direction.BEARISH,
    }
    assert all(
        event.eligibility_classification is EligibilityClassification.INELIGIBLE
        for event in simple_bos
    )
    assert {event.direction for event in layer2_bos} == {
        Direction.BULLISH,
        Direction.BEARISH,
    }
    assert {event.direction for event in layer2_choch} == {
        Direction.BULLISH,
        Direction.BEARISH,
    }
    assert all(event.raw_observation["break_basis"] == "wick" for event in layer2_bos)


def test_valid_and_incomplete_mss_are_blocked_not_synthesized() -> None:
    for identifier in STRUCTURE_IMPLEMENTATIONS:
        assert _capability(identifier, "MSS_VALID_SEQUENCE").status is CapabilityStatus.BLOCKED
        assert _capability(identifier, "MSS_INCOMPLETE_SEQUENCE").status is CapabilityStatus.BLOCKED
        assert all(event.event_type != "MSS" for event in snapshot(identifier).events)


def test_simple_bos_uses_a_later_full_frame_swing() -> None:
    fixture = fixture_catalog()["structure-future-level-selection-v1"]
    engine_class = importlib.import_module(
        "pipelines.legacy.03_structure"
    ).StructuralEngine
    full = engine_class(SimpleNamespace(df=fixture.frame.copy(deep=True)))
    prefix = engine_class(SimpleNamespace(df=fixture.frame.iloc[:4].copy(deep=True)))

    assert bool(prefix.is_bos(3, "bullish")) is True
    assert bool(full.is_bos(3, "bullish")) is False
