"""Frozen output contracts for descriptive Behavioral Fingerprints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field, field_validator, model_validator

from pipelines.historical_labeling.contracts import (
    EventDirection,
    EventType,
    FrozenContract,
    OutcomeClass,
    canonical_hash,
)


FINGERPRINT_SCHEMA_VERSION = "1.0.0"
FREQUENCY_SEMANTICS = "DESCRIPTIVE_IN_SAMPLE_EMPIRICAL_FREQUENCY"


class EvidenceClassification(str, Enum):
    HEURISTIC_ONLY = "HEURISTIC_ONLY"
    NOT_STATISTICALLY_ELIGIBLE = "NOT_STATISTICALLY_ELIGIBLE"


class CellBucket(FrozenContract):
    dimension: str = Field(min_length=1)
    bucket: str = Field(min_length=1)


class DescriptiveFrequency(FrozenContract):
    outcome_class: OutcomeClass
    count: int = Field(ge=0)
    resolved_denominator: int = Field(ge=0)
    value: Decimal | None = Field(default=None, ge=0, le=1)
    semantics: str = FREQUENCY_SEMANTICS

    @model_validator(mode="after")
    def validate_frequency(self) -> "DescriptiveFrequency":
        if self.outcome_class is OutcomeClass.CENSORED:
            raise ValueError("censoring is coverage, not a resolved outcome frequency")
        if self.resolved_denominator == 0:
            if self.count != 0 or self.value is not None:
                raise ValueError("zero denominator requires zero count and null value")
        else:
            expected = Decimal(self.count) / Decimal(self.resolved_denominator)
            if self.value != expected:
                raise ValueError("descriptive frequency does not match its denominator")
        if self.semantics != FREQUENCY_SEMANTICS:
            raise ValueError("frequency must remain explicitly descriptive and in-sample")
        return self


class RobustSummary(FrozenContract):
    eligible_count: int = Field(gt=0)
    minimum: Decimal
    q25: Decimal
    median: Decimal
    q75: Decimal
    maximum: Decimal
    quantile_method: str = "DECIMAL_LINEAR_TYPE7"

    @field_validator("minimum", "q25", "median", "q75", "maximum")
    @classmethod
    def validate_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("robust summary values must be finite")
        return value

    @model_validator(mode="after")
    def validate_order(self) -> "RobustSummary":
        if not (
            self.minimum
            <= self.q25
            <= self.median
            <= self.q75
            <= self.maximum
        ):
            raise ValueError("robust summary order is invalid")
        if self.quantile_method != "DECIMAL_LINEAR_TYPE7":
            raise ValueError("unexpected quantile method")
        return self


class ChronologicalPartitionDiagnostic(FrozenContract):
    partition_index: int = Field(ge=0)
    start_timestamp: datetime | None
    end_timestamp: datetime | None
    eligible_event_count: int = Field(ge=0)
    resolved_label_count: int = Field(ge=0)
    censored_label_count: int = Field(ge=0)
    outcome_frequencies: tuple[DescriptiveFrequency, ...]

    @field_validator("start_timestamp", "end_timestamp")
    @classmethod
    def validate_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("partition timestamps must be timezone-aware")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("partition timestamps must be UTC")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> "ChronologicalPartitionDiagnostic":
        if self.resolved_label_count + self.censored_label_count != (
            self.eligible_event_count
        ):
            raise ValueError("partition label coverage must conserve eligible events")
        if (self.start_timestamp is None) != (self.end_timestamp is None):
            raise ValueError("partition boundaries must be both present or both absent")
        if (
            self.start_timestamp is not None
            and self.end_timestamp is not None
            and self.end_timestamp < self.start_timestamp
        ):
            raise ValueError("partition end cannot precede its start")
        expected = set(_resolved_outcome_values())
        observed = {
            frequency.outcome_class.value
            for frequency in self.outcome_frequencies
        }
        if observed != expected or len(observed) != len(self.outcome_frequencies):
            raise ValueError(
                "partition frequencies require every resolved outcome exactly once"
            )
        for frequency in self.outcome_frequencies:
            if frequency.resolved_denominator != self.resolved_label_count:
                raise ValueError(
                    "partition frequency denominator must match resolved labels"
                )
        return self


class FingerprintGateAudit(FrozenContract):
    gate_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class FingerprintCell(FrozenContract):
    cell_id: str = Field(pattern=r"^fpc_[0-9a-f]{64}$")
    schema_version: str = FINGERPRINT_SCHEMA_VERSION
    policy_version: str = Field(min_length=1)
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assignment_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_dataset_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_revision: str = Field(min_length=1)
    market: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    feature_policy_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    view_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    event_type: EventType
    direction: EventDirection
    neutral_session_bucket: str = Field(min_length=1)
    feature_buckets: tuple[CellBucket, ...]
    feature_bucket_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligibility_start_timestamp: datetime
    eligibility_end_timestamp: datetime
    eligible_event_count: int = Field(gt=0)
    resolved_label_count: int = Field(ge=0)
    censored_label_count: int = Field(ge=0)
    feature_ineligible_count: int = Field(ge=0)
    missing_semantics_count: int = Field(ge=0)
    outcome_counts: dict[str, int]
    outcome_frequencies: tuple[DescriptiveFrequency, ...]
    metric_summaries: dict[str, RobustSummary]
    chronological_partitions: tuple[ChronologicalPartitionDiagnostic, ...]
    maximum_descriptive_frequency_range: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    evidence_classification: EvidenceClassification
    evidence_labels: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @field_validator("eligibility_start_timestamp", "eligibility_end_timestamp")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("eligibility timestamps must be timezone-aware")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("eligibility timestamps must be UTC")
        return value

    def identity_material(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "policy_sha256": self.policy_sha256,
            "assignment_source_sha256": self.assignment_source_sha256,
            "source_dataset_id": self.source_dataset_id,
            "source_sha256": self.source_sha256,
            "code_revision": self.code_revision,
            "market": self.market,
            "symbol": self.symbol,
            "feature_policy_version": self.feature_policy_version,
            "view_id": self.view_id,
            "event_type": self.event_type,
            "direction": self.direction,
            "neutral_session_bucket": self.neutral_session_bucket,
            "feature_buckets": self.feature_buckets,
            "feature_bucket_definition_sha256": (
                self.feature_bucket_definition_sha256
            ),
        }

    @model_validator(mode="after")
    def validate_cell(self) -> "FingerprintCell":
        if self.cell_id != f"fpc_{canonical_hash(self.identity_material())}":
            raise ValueError("cell_id does not match label-free cell material")
        if self.resolved_label_count + self.censored_label_count != (
            self.eligible_event_count
        ):
            raise ValueError("cell label coverage must conserve eligible events")
        if self.eligibility_end_timestamp < self.eligibility_start_timestamp:
            raise ValueError("cell eligibility range is invalid")
        expected_outcomes = {outcome.value for outcome in OutcomeClass}
        if set(self.outcome_counts) != expected_outcomes:
            raise ValueError("outcome counts require every outcome class exactly once")
        if any(count < 0 for count in self.outcome_counts.values()):
            raise ValueError("outcome counts cannot be negative")
        if sum(self.outcome_counts.values()) != self.eligible_event_count:
            raise ValueError("outcome counts must conserve eligible events")
        if self.outcome_counts.get(OutcomeClass.CENSORED.value, 0) != (
            self.censored_label_count
        ):
            raise ValueError("censored outcome count must match cell coverage")
        if len(self.chronological_partitions) < 2:
            raise ValueError("chronological diagnostics require at least two partitions")
        if sum(
            item.eligible_event_count for item in self.chronological_partitions
        ) != self.eligible_event_count:
            raise ValueError("partition counts must conserve cell events")
        expected_resolved = set(_resolved_outcome_values())
        observed_resolved = {
            frequency.outcome_class.value
            for frequency in self.outcome_frequencies
        }
        if (
            observed_resolved != expected_resolved
            or len(observed_resolved) != len(self.outcome_frequencies)
        ):
            raise ValueError(
                "cell frequencies require every resolved outcome exactly once"
            )
        for frequency in self.outcome_frequencies:
            if frequency.resolved_denominator != self.resolved_label_count:
                raise ValueError(
                    "cell frequency denominator must match resolved labels"
                )
            if frequency.count != self.outcome_counts[frequency.outcome_class.value]:
                raise ValueError(
                    "cell frequency count must match the outcome count"
                )
        return self


class ViewCoverage(FrozenContract):
    view_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    cell_count: int = Field(ge=0)
    assigned_event_count: int = Field(ge=0)
    heuristic_only_cell_count: int = Field(ge=0)
    not_statistically_eligible_cell_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_classification_counts(self) -> "ViewCoverage":
        if self.heuristic_only_cell_count + (
            self.not_statistically_eligible_cell_count
        ) != self.cell_count:
            raise ValueError("view classifications must conserve its cells")
        return self


class BehavioralFingerprintArtifact(FrozenContract):
    fingerprint_id: str = Field(pattern=r"^bfp_[0-9a-f]{64}$")
    schema_version: str = FINGERPRINT_SCHEMA_VERSION
    jira_key: str = "KAN-15"
    policy_version: str = Field(min_length=1)
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_extraction_id: str = Field(pattern=r"^xtr_[0-9a-f]{64}$")
    assignment_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_dataset_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_revision: str = Field(min_length=1)
    unique_eligible_event_count: int = Field(ge=0)
    unique_resolved_label_count: int = Field(ge=0)
    unique_censored_label_count: int = Field(ge=0)
    unassigned_feature_ineligible_count: int = Field(ge=0)
    feature_ineligibility_reasons: dict[str, int]
    cell_assignment_missing_semantics_count: int = Field(ge=0)
    cell_count: int = Field(ge=0)
    cells: tuple[FingerprintCell, ...]
    view_coverage: tuple[ViewCoverage, ...]
    gate_audit: tuple[FingerprintGateAudit, ...]
    prohibited_outputs: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    def identity_material(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude={"fingerprint_id"})

    @model_validator(mode="after")
    def validate_artifact(self) -> "BehavioralFingerprintArtifact":
        if self.fingerprint_id != f"bfp_{canonical_hash(self.identity_material())}":
            raise ValueError("fingerprint_id does not match deterministic material")
        if self.cell_count != len(self.cells):
            raise ValueError("cell_count does not match cells")
        if self.unique_resolved_label_count + self.unique_censored_label_count != (
            self.unique_eligible_event_count
        ):
            raise ValueError("artifact label coverage must conserve eligible events")
        if sum(self.feature_ineligibility_reasons.values()) != (
            self.unassigned_feature_ineligible_count
        ):
            raise ValueError(
                "feature-ineligibility reasons must conserve unassigned events"
            )
        if sum(cell.missing_semantics_count for cell in self.cells) != (
            self.cell_assignment_missing_semantics_count
        ):
            raise ValueError(
                "missing-semantics assignments must be explicit and conserved"
            )
        cell_ids = [cell.cell_id for cell in self.cells]
        if cell_ids != sorted(cell_ids) or len(cell_ids) != len(set(cell_ids)):
            raise ValueError("fingerprint cells must be unique and sorted")
        view_ids = [view.view_id for view in self.view_coverage]
        if len(view_ids) != len(set(view_ids)):
            raise ValueError("view coverage IDs must be unique")
        if sum(view.cell_count for view in self.view_coverage) != self.cell_count:
            raise ValueError("view coverage must conserve fingerprint cells")
        by_view = {
            view_id: sum(
                cell.eligible_event_count
                for cell in self.cells
                if cell.view_id == view_id
            )
            for view_id in view_ids
        }
        if any(
            view.assigned_event_count != by_view[view.view_id]
            for view in self.view_coverage
        ):
            raise ValueError("view coverage must conserve assigned events")
        gates = {gate.gate_id: gate.status for gate in self.gate_audit}
        if gates.get("G6_FEATURE_REPRODUCTION") != "PASS":
            raise ValueError("Behavioral Fingerprint output requires G6 PASS")
        for gate_id in (
            "G7_ANALYTICAL_ELIGIBILITY",
            "G8_STATISTICAL_ELIGIBILITY",
            "G9_EXECUTION_BACKTEST_ELIGIBILITY",
        ):
            if gates.get(gate_id) != "NOT_EVALUATED":
                raise ValueError(f"{gate_id} must remain NOT_EVALUATED")
        return self

    @classmethod
    def create(cls, **material: Any) -> "BehavioralFingerprintArtifact":
        material.setdefault("schema_version", FINGERPRINT_SCHEMA_VERSION)
        material.setdefault("jira_key", "KAN-15")
        material["cells"] = tuple(material.get("cells", ()))
        material["view_coverage"] = tuple(material.get("view_coverage", ()))
        material["gate_audit"] = tuple(material.get("gate_audit", ()))
        material["cell_count"] = len(material["cells"])
        fingerprint_id = f"bfp_{canonical_hash(material)}"
        return cls(fingerprint_id=fingerprint_id, **material)


def _resolved_outcome_values() -> tuple[str, ...]:
    return tuple(
        outcome.value
        for outcome in OutcomeClass
        if outcome is not OutcomeClass.CENSORED
    )


__all__ = [
    "BehavioralFingerprintArtifact",
    "CellBucket",
    "ChronologicalPartitionDiagnostic",
    "DescriptiveFrequency",
    "EvidenceClassification",
    "FINGERPRINT_SCHEMA_VERSION",
    "FREQUENCY_SEMANTICS",
    "FingerprintCell",
    "FingerprintGateAudit",
    "RobustSummary",
    "ViewCoverage",
]
