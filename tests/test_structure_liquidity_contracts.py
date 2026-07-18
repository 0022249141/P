from __future__ import annotations

import pytest
from pydantic import ValidationError

from pipelines.characterization import (
    Direction,
    EligibilityClassification,
    EventObservation,
)
from tests.characterization_helpers import artifact


def _event_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "implementation_identifier": "contract-probe",
        "event_type": "SWING_HIGH",
        "direction": Direction.ABOVE,
        "origin_or_pivot_timestamp": "2025-01-01T00:00:00Z",
        "observation_timestamp": "2025-01-01T00:10:00Z",
        "confirmation_or_availability_timestamp": "2025-01-01T00:15:00Z",
        "first_downstream_eligible_timestamp": "2025-01-01T00:15:00Z",
        "observed_price_or_level": 100.0,
        "eligibility_classification": EligibilityClassification.POST_CONFIRMATION,
        "temporal_evidence": ("synthetic contract probe",),
        "source_fixture": "contract-probe-v1",
        "fixture_sha256": "a" * 64,
    }
    payload.update(updates)
    return payload


def test_contract_rejects_confirmation_before_observation() -> None:
    with pytest.raises(ValidationError, match="confirmation cannot precede observation"):
        EventObservation(
            **_event_payload(
                confirmation_or_availability_timestamp="2025-01-01T00:05:00Z"
            )
        )


def test_contract_rejects_eligibility_before_observation() -> None:
    with pytest.raises(
        ValidationError, match="at or after both observation and confirmation"
    ):
        EventObservation(
            **_event_payload(
                confirmation_or_availability_timestamp="2025-01-01T00:10:00Z",
                first_downstream_eligible_timestamp="2025-01-01T00:05:00Z",
                eligibility_classification=EligibilityClassification.REALTIME_ELIGIBLE,
            )
        )


def test_contract_rejects_eligibility_before_confirmation() -> None:
    with pytest.raises(
        ValidationError, match="at or after both observation and confirmation"
    ):
        EventObservation(
            **_event_payload(
                observation_timestamp="2025-01-01T00:05:00Z",
                confirmation_or_availability_timestamp="2025-01-01T00:10:00Z",
                first_downstream_eligible_timestamp="2025-01-01T00:07:00Z",
            )
        )


def test_ineligible_event_still_requires_null_eligible_timestamp() -> None:
    with pytest.raises(
        ValidationError, match="ineligible events cannot declare downstream eligibility"
    ):
        EventObservation(
            **_event_payload(
                eligibility_classification=EligibilityClassification.INELIGIBLE
            )
        )


def test_all_generated_events_satisfy_the_strengthened_contract() -> None:
    for implementation in artifact().implementation_snapshots:
        for event in implementation.events:
            assert EventObservation.model_validate(event.model_dump()) == event
