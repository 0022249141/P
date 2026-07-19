from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from pydantic import ValidationError

from pipelines.historical_labeling.contracts import (
    AsOfFeatureSnapshot,
    HistoricalOutcomeLabel,
    MarketEventIdentity,
    OutcomeClass,
    build_event_id,
)
from pipelines.historical_labeling.fixtures import (
    synthetic_event,
    synthetic_outcome_frame,
    synthetic_snapshot,
)
from pipelines.historical_labeling.labels import label_historical_outcome
from tests.historical_labeling_helpers import policy


def test_approved_policy_values_are_externalized_and_exact() -> None:
    configured = policy()

    assert configured.event_source.min_strength == Decimal("0.6")
    assert configured.event_source.lookback == 2
    assert configured.event_source.event_bar_seconds == 300
    assert configured.labels.policy_version == "abshodeh-level-outcome-v1"
    assert configured.labels.maximum_horizon_bars == 12
    assert configured.labels.maximum_horizon_seconds == 3600
    assert configured.labels.reentry_close_atr == Decimal("0.00")
    assert configured.session.timezone == "Asia/Tehran"
    assert configured.session.timestamp_period_semantics == "PERIOD_START"
    assert configured.session.evidence_status.value == "HYPOTHESIS"
    assert configured.features.event_bar_seconds == 300
    assert configured.features.htf_bar_seconds == 3600


def test_event_id_is_stable_and_sensitive_to_every_material_source_dimension() -> None:
    event = synthetic_event(policy(), direction=policy_direction())
    material = event.identity_material()

    assert build_event_id(material) == event.event_id
    assert MarketEventIdentity.create(**material) == event
    without_default = dict(material)
    without_default.pop("schema_version")
    assert MarketEventIdentity.create(**without_default) == event

    mutations = {
        "market": "OTHER_MARKET",
        "timeframe": "M15",
        "source_sha256": "b" * 64,
        "level_price": "101.0",
        "event_policy_version": "different-policy-v2",
    }
    for field, value in mutations.items():
        changed = dict(material)
        changed[field] = value
        assert build_event_id(changed) != event.event_id


def policy_direction():
    from pipelines.historical_labeling.contracts import EventDirection

    return EventDirection.ABOVE


def test_event_rejects_noncanonical_id_and_invalid_temporal_order() -> None:
    event = synthetic_event(policy(), policy_direction())
    payload = event.model_dump(mode="python")
    payload["event_id"] = f"evt_{'f' * 64}"
    with pytest.raises(ValidationError, match="event_id does not match"):
        MarketEventIdentity.model_validate(payload)

    material = event.identity_material()
    material["confirmation_or_availability_timestamp"] = material[
        "level_origin_timestamp"
    ]
    material["observation_timestamp"] = event.first_feature_eligible_timestamp
    with pytest.raises(ValidationError, match="origin <= observation"):
        MarketEventIdentity.create(**material)


def test_feature_and_label_contracts_are_structurally_separate() -> None:
    feature_fields = set(AsOfFeatureSnapshot.model_fields)
    label_fields = set(HistoricalOutcomeLabel.model_fields)

    assert "outcome_class" not in feature_fields
    assert "mfe_atr" not in feature_fields
    assert "approach_velocity_atr" not in label_fields
    assert "prior_touch_count" not in label_fields
    assert feature_fields & label_fields == {"event_id", "schema_version"}


def test_label_contract_rejects_inconsistent_outcome_state() -> None:
    event = synthetic_event(policy(), policy_direction())
    result = label_historical_outcome(
        synthetic_outcome_frame(event, OutcomeClass.DIRECT_CONTINUATION),
        event,
        synthetic_snapshot(policy(), event),
        label_policy=policy().labels,
        session_policy=policy().session,
    )
    payload = result.label.model_dump(mode="python")
    payload["horizon_status"] = "CENSORED"

    with pytest.raises(ValidationError, match="complete horizon"):
        HistoricalOutcomeLabel.model_validate(payload)


def test_contracts_are_immutable_and_serialization_has_no_environment_identity() -> None:
    event = synthetic_event(policy(), policy_direction())
    first = event.to_json_bytes()
    second = event.model_copy(deep=True).to_json_bytes()

    assert first == second
    decoded = first.decode("ascii")
    for forbidden in (
        "C:\\",
        "hostname",
        "username",
        "generated_at",
        "current_time",
    ):
        assert forbidden not in decoded
    with pytest.raises((ValidationError, TypeError, FrozenInstanceError)):
        event.market = "MUTATED"
