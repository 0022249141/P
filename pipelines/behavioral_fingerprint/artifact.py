"""Compact committed audit derived from the uncommitted fingerprint catalog."""

from __future__ import annotations

from collections import Counter
import hashlib
from typing import Any

from pydantic import Field, model_validator

from pipelines.behavioral_fingerprint.contracts import (
    BehavioralFingerprintArtifact,
    CellBucket,
    EvidenceClassification,
    FREQUENCY_SEMANTICS,
    FingerprintGateAudit,
    ViewCoverage,
)
from pipelines.behavioral_fingerprint.policies import BehavioralFingerprintPolicy
from pipelines.historical_labeling.contracts import (
    FrozenContract,
    HistoricalExtractionResult,
    canonical_hash,
)
from pipelines.source_semantics import SourceSemanticsArtifact


AUDIT_SCHEMA_VERSION = "1.0.0"


class FingerprintCellAuditSample(FrozenContract):
    cell_id: str = Field(pattern=r"^fpc_[0-9a-f]{64}$")
    view_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    neutral_session_bucket: str = Field(min_length=1)
    feature_buckets: tuple[CellBucket, ...]
    eligible_event_count: int = Field(gt=0)
    resolved_label_count: int = Field(ge=0)
    censored_label_count: int = Field(ge=0)
    evidence_classification: EvidenceClassification


class BehavioralFingerprintAudit(FrozenContract):
    audit_id: str = Field(pattern=r"^bfpa_[0-9a-f]{64}$")
    schema_version: str = AUDIT_SCHEMA_VERSION
    jira_key: str = "KAN-15"
    fingerprint_id: str = Field(pattern=r"^bfp_[0-9a-f]{64}$")
    full_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    full_catalog_policy: str = "RESEARCH_ONLY_UNCOMMITTED"
    policy_version: str = Field(min_length=1)
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_revision: str = Field(min_length=1)
    source_extraction_id: str = Field(pattern=r"^xtr_[0-9a-f]{64}$")
    source_dataset_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    unique_eligible_event_count: int = Field(ge=0)
    unique_resolved_label_count: int = Field(ge=0)
    unique_censored_label_count: int = Field(ge=0)
    unassigned_feature_ineligible_count: int = Field(ge=0)
    feature_ineligibility_reasons: dict[str, int]
    cell_assignment_missing_semantics_count: int = Field(ge=0)
    label_outcome_counts: dict[str, int]
    cell_count: int = Field(ge=0)
    heuristic_only_cell_count: int = Field(ge=0)
    not_statistically_eligible_cell_count: int = Field(ge=0)
    view_coverage: tuple[ViewCoverage, ...]
    gate_audit: tuple[FingerprintGateAudit, ...]
    support_policy: dict[str, Any]
    descriptive_frequency_semantics: str
    bounded_cell_sample: tuple[FingerprintCellAuditSample, ...]
    protected_source_hashes_before: dict[str, str]
    protected_source_hashes_after: dict[str, str]
    manifest_sha256_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256_after: str = Field(pattern=r"^[0-9a-f]{64}$")
    prohibited_outputs: tuple[str, ...]
    limitations: tuple[str, ...] = Field(min_length=1)

    def identity_material(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude={"audit_id"})

    @model_validator(mode="after")
    def validate_audit(self) -> "BehavioralFingerprintAudit":
        if self.audit_id != f"bfpa_{canonical_hash(self.identity_material())}":
            raise ValueError("audit_id does not match deterministic material")
        if self.heuristic_only_cell_count + (
            self.not_statistically_eligible_cell_count
        ) != self.cell_count:
            raise ValueError("cell classifications must conserve the catalog")
        if sum(self.feature_ineligibility_reasons.values()) != (
            self.unassigned_feature_ineligible_count
        ):
            raise ValueError(
                "feature-ineligibility reasons must conserve unassigned events"
            )
        if (
            self.protected_source_hashes_before
            != self.protected_source_hashes_after
        ):
            raise ValueError("protected source hashes changed during KAN-15")
        if self.manifest_sha256_before != self.manifest_sha256_after:
            raise ValueError("committed manifest changed during KAN-15")
        if len(self.bounded_cell_sample) > 12:
            raise ValueError("committed audit sample must remain bounded")
        if self.descriptive_frequency_semantics != FREQUENCY_SEMANTICS:
            raise ValueError(
                "compact audit frequencies must remain descriptive and in-sample"
            )
        return self

    @classmethod
    def create(cls, **material: Any) -> "BehavioralFingerprintAudit":
        material.setdefault("schema_version", AUDIT_SCHEMA_VERSION)
        material.setdefault("jira_key", "KAN-15")
        material.setdefault("full_catalog_policy", "RESEARCH_ONLY_UNCOMMITTED")
        audit_id = f"bfpa_{canonical_hash(material)}"
        return cls(audit_id=audit_id, **material)


def build_compact_audit(
    fingerprint: BehavioralFingerprintArtifact,
    *,
    extraction: HistoricalExtractionResult,
    source_semantics: SourceSemanticsArtifact,
    policy: BehavioralFingerprintPolicy,
) -> BehavioralFingerprintAudit:
    selected = sorted(
        fingerprint.cells,
        key=lambda cell: (-cell.eligible_event_count, cell.cell_id),
    )[:12]
    sample = tuple(
        FingerprintCellAuditSample(
            cell_id=cell.cell_id,
            view_id=cell.view_id,
            event_type=cell.event_type.value,
            direction=cell.direction.value,
            neutral_session_bucket=cell.neutral_session_bucket,
            feature_buckets=cell.feature_buckets,
            eligible_event_count=cell.eligible_event_count,
            resolved_label_count=cell.resolved_label_count,
            censored_label_count=cell.censored_label_count,
            evidence_classification=cell.evidence_classification,
        )
        for cell in selected
    )
    classifications = Counter(
        cell.evidence_classification for cell in fingerprint.cells
    )
    outcomes = Counter(label.outcome_class.value for label in extraction.labels)
    return BehavioralFingerprintAudit.create(
        fingerprint_id=fingerprint.fingerprint_id,
        full_catalog_sha256=hashlib.sha256(
            fingerprint.to_json_bytes()
        ).hexdigest(),
        policy_version=fingerprint.policy_version,
        policy_sha256=fingerprint.policy_sha256,
        implementation_revision=fingerprint.code_revision,
        source_extraction_id=fingerprint.source_extraction_id,
        source_dataset_id=fingerprint.source_dataset_id,
        source_sha256=fingerprint.source_sha256,
        unique_eligible_event_count=fingerprint.unique_eligible_event_count,
        unique_resolved_label_count=fingerprint.unique_resolved_label_count,
        unique_censored_label_count=fingerprint.unique_censored_label_count,
        unassigned_feature_ineligible_count=(
            fingerprint.unassigned_feature_ineligible_count
        ),
        feature_ineligibility_reasons=(
            fingerprint.feature_ineligibility_reasons
        ),
        cell_assignment_missing_semantics_count=(
            fingerprint.cell_assignment_missing_semantics_count
        ),
        label_outcome_counts={
            key: outcomes[key] for key in sorted(outcomes)
        },
        cell_count=fingerprint.cell_count,
        heuristic_only_cell_count=classifications[
            EvidenceClassification.HEURISTIC_ONLY
        ],
        not_statistically_eligible_cell_count=classifications[
            EvidenceClassification.NOT_STATISTICALLY_ELIGIBLE
        ],
        view_coverage=fingerprint.view_coverage,
        gate_audit=fingerprint.gate_audit,
        support_policy=policy.support.model_dump(
            mode="json",
            exclude_none=False,
        ),
        descriptive_frequency_semantics=(
            policy.descriptive_frequency_semantics
        ),
        bounded_cell_sample=sample,
        protected_source_hashes_before=(
            source_semantics.protected_source_hashes_before
        ),
        protected_source_hashes_after=(
            source_semantics.protected_source_hashes_after
        ),
        manifest_sha256_before=source_semantics.manifest_sha256_before,
        manifest_sha256_after=source_semantics.manifest_sha256_after,
        prohibited_outputs=fingerprint.prohibited_outputs,
        limitations=fingerprint.limitations,
    )


__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "BehavioralFingerprintAudit",
    "FingerprintCellAuditSample",
    "build_compact_audit",
]
