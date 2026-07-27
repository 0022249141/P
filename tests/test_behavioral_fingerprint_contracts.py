from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from pydantic import ValidationError

from pipelines.behavioral_fingerprint.contracts import (
    EvidenceClassification,
    FREQUENCY_SEMANTICS,
    FingerprintCell,
    RobustSummary,
)
from pipelines.behavioral_fingerprint.policies import (
    BehavioralFingerprintPolicy,
    FeatureDimension,
    PartitionStrategy,
)
from tests.behavioral_fingerprint_helpers import artifact, fingerprint_policy


def test_policy_is_preregistered_versioned_and_non_random() -> None:
    configured = fingerprint_policy()

    assert configured.schema_version == "1.0.0"
    assert configured.policy_version == "abshodeh-behavioral-fingerprint-v1"
    assert configured.chronological_partitions.strategy is (
        PartitionStrategy.CONTIGUOUS_EQUAL_EVENT_COUNT
    )
    assert configured.chronological_partitions.partition_count == 3
    assert [view.view_id for view in configured.views] == [
        "CORE",
        "TOUCH_CONTEXT",
        "APPROACH_CONTEXT",
        "ORIGIN_BAR_CONTEXT",
        "LEVEL_AGE_CONTEXT",
        "SNAPSHOT_CONTEXT",
    ]
    assert {
        item.dimension for item in configured.dimensions
    } == set(FeatureDimension)
    assert configured.support.maximum_descriptive_frequency_range == Decimal(
        "0.35"
    )


def test_policy_rejects_unconfigured_or_outcome_bucket_dimensions() -> None:
    payload = fingerprint_policy().model_dump(mode="json")
    payload["views"][1]["dimensions"] = ["outcome_class"]

    with pytest.raises(ValidationError):
        BehavioralFingerprintPolicy.model_validate(payload)


def test_artifact_contract_is_frozen_and_has_no_decision_outputs() -> None:
    result = artifact()
    payload = result.to_json_bytes().decode("ascii")

    assert result.gate_audit[0].status == "PASS"
    assert all(
        cell.evidence_classification
        in {
            EvidenceClassification.HEURISTIC_ONLY,
            EvidenceClassification.NOT_STATISTICALLY_ELIGIBLE,
        }
        for cell in result.cells
    )
    assert all(
        frequency.semantics == FREQUENCY_SEMANTICS
        for cell in result.cells
        for frequency in cell.outcome_frequencies
    )
    for forbidden_field in (
        '"calibrated_probability"',
        '"expected_return"',
        '"entry"',
        '"invalidation"',
        '"target"',
        '"profitability"',
        '"live_ready"',
    ):
        assert forbidden_field not in payload
    with pytest.raises((ValidationError, TypeError, FrozenInstanceError)):
        result.jira_key = "MUTATED"


def test_contracts_reject_incomplete_outcomes_and_non_finite_metrics() -> None:
    payload = artifact().cells[0].model_dump(mode="python")
    payload["outcome_counts"].pop("NO_RESOLUTION")
    with pytest.raises(ValidationError, match="every outcome class"):
        FingerprintCell.model_validate(payload)

    with pytest.raises(ValidationError, match="finite"):
        RobustSummary(
            eligible_count=1,
            minimum=Decimal("Infinity"),
            q25=Decimal("Infinity"),
            median=Decimal("Infinity"),
            q75=Decimal("Infinity"),
            maximum=Decimal("Infinity"),
        )
