from __future__ import annotations

from pipelines.characterization import CapabilityStatus, EligibilityClassification
from pipelines.characterization.structure_liquidity import EXPECTED_SOURCE_SHA256
from tests.characterization_helpers import snapshot


LIQUIDITY_IMPLEMENTATIONS = (
    "legacy-liquidity",
    "vector-liquidity",
    "layer3-liquidity",
    "zone-engine",
)


def _events(identifier: str, fixture_id: str, event_type: str | None = None):
    return [
        event
        for event in snapshot(identifier).events
        if event.source_fixture == fixture_id
        and (event_type is None or event.event_type == event_type)
    ]


def _capability(identifier: str, capability: str):
    return next(
        item
        for item in snapshot(identifier).capabilities
        if item.capability == capability
    )


def test_liquidity_source_hashes_freeze_each_engine_unchanged() -> None:
    for identifier in LIQUIDITY_IMPLEMENTATIONS:
        assert snapshot(identifier).source_sha256 == EXPECTED_SOURCE_SHA256[identifier]


def test_byte_duplicate_liquidity_engines_freeze_equivalent_outputs() -> None:
    legacy = snapshot("legacy-liquidity")
    vector = snapshot("vector-liquidity")

    assert legacy.source_sha256 == vector.source_sha256
    assert [
        event.model_copy(update={"implementation_identifier": "same"})
        for event in legacy.events
    ] == [
        event.model_copy(update={"implementation_identifier": "same"})
        for event in vector.events
    ]
    assert _capability("legacy-liquidity", "SWEEP_SCORE").status is CapabilityStatus.BLOCKED
    assert _capability("vector-liquidity", "SWEEP_SCORE").status is CapabilityStatus.BLOCKED


def test_equal_high_and_equal_low_clusters_are_observed() -> None:
    events = _events("layer3-liquidity", "liquidity-equal-levels-v1")

    assert {(event.event_type, event.raw_observation["prior_match_count"]) for event in events} == {
        ("EQUAL_HIGH_CLUSTER", 3),
        ("EQUAL_LOW_CLUSTER", 3),
    }
    assert all(
        event.eligibility_classification is EligibilityClassification.REALTIME_ELIGIBLE
        for event in events
    )


def test_bsl_ssl_registration_and_untouched_proxies_are_explicit() -> None:
    events = _events("layer3-liquidity", "liquidity-pool-registration-v1")

    assert {event.event_type for event in events} == {
        "BSL_REGISTRATION_PROXY",
        "SSL_REGISTRATION_PROXY",
        "UNTOUCHED_BSL_PROXY",
        "UNTOUCHED_SSL_PROXY",
    }
    assert {event.observed_price_or_level for event in events} == {90.0, 100.0}
    assert all(
        event.eligibility_classification is EligibilityClassification.POST_CONFIRMATION
        for event in events
    )


def test_bearish_and_bullish_sweeps_wait_for_next_candle() -> None:
    bearish = _events(
        "layer3-liquidity", "liquidity-bearish-wick-raid-v1", "BEARISH_SWEEP"
    )[0]
    bullish = _events(
        "layer3-liquidity", "liquidity-bullish-wick-raid-v1", "BULLISH_SWEEP"
    )[0]

    for event in (bearish, bullish):
        assert event.observation_timestamp < event.confirmation_or_availability_timestamp
        assert event.first_downstream_eligible_timestamp == event.confirmation_or_availability_timestamp
        assert event.raw_observation["pool_registered_before_raid"] is True
        assert event.raw_observation["pool_confirmation_index"] < event.raw_observation["source_index"]


def test_wick_raid_and_close_through_are_not_promoted_to_acceptance() -> None:
    wick = _events(
        "layer3-liquidity", "liquidity-bearish-wick-raid-v1", "BEARISH_SWEEP"
    )[0]
    close_through = _events(
        "layer3-liquidity", "liquidity-bearish-close-through-v1", "BEARISH_SWEEP"
    )[0]

    assert wick.raw_observation["mitigation_score"] == 0.70
    assert close_through.raw_observation["mitigation_score"] == 0.95
    assert _capability("layer3-liquidity", "ACCEPTED_STATE").status is CapabilityStatus.BLOCKED
    assert _capability("layer3-liquidity", "RECLAIMED_STATE").status is CapabilityStatus.BLOCKED


def test_multiple_candidates_remain_unranked() -> None:
    events = _events("layer3-liquidity", "liquidity-multiple-destinations-v1")

    assert len([event for event in events if "REGISTRATION" in event.event_type]) == 4
    assert _capability("layer3-liquidity", "DESTINATION_RANKING").status is CapabilityStatus.BLOCKED
    assert all("rank" not in event.raw_observation for event in events)


def test_zone_engine_does_not_gain_liquidity_semantics() -> None:
    zone = snapshot("zone-engine")

    assert zone.events == ()
    assert all(item.status is CapabilityStatus.BLOCKED for item in zone.capabilities)
