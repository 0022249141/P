"""Versioned KAN-14 contracts for Abshodeh source-semantics evidence."""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pipelines.canonical.contracts import (
    CoverageBoundaryPolicy,
    EvidenceStatus,
    GapPolicy,
    IncompleteBinPolicy,
    OutOfSessionPolicy,
    PeriodSemantics,
    SessionEndConvention,
    VolumeAggregation,
)


SCHEMA_VERSION = "1.0.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CandidateDisposition(str, Enum):
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


class EvidenceBasis(str, Enum):
    USER_VERIFIED_PLATFORM_SETTING = "USER_VERIFIED_PLATFORM_SETTING"
    HUMAN_APPROVED_MARKET_DEFINITION = "HUMAN_APPROVED_MARKET_DEFINITION"
    DETERMINISTIC_REAL_DATA_RECONCILIATION = (
        "DETERMINISTIC_REAL_DATA_RECONCILIATION"
    )
    UNAVAILABLE = "UNAVAILABLE"


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    def to_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json", exclude_none=False)
        text = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        return f"{text}\n".encode("ascii")


class SemanticEvidence(FrozenContract):
    status: EvidenceStatus
    basis: EvidenceBasis
    references: tuple[str, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def require_consistent_basis(self) -> "SemanticEvidence":
        if self.status is EvidenceStatus.UNKNOWN:
            if self.basis is not EvidenceBasis.UNAVAILABLE:
                raise ValueError("UNKNOWN evidence requires UNAVAILABLE basis")
        elif self.basis is EvidenceBasis.UNAVAILABLE:
            raise ValueError("available evidence cannot use UNAVAILABLE basis")
        return self


class ExternalReconciliationEvidence(FrozenContract):
    archive_sha256: str
    lower_member_sha256: str
    higher_member_sha256: str
    lower_timeframe: str
    higher_timeframe: str
    lower_row_count: int = Field(gt=0)
    higher_row_count: int = Field(gt=0)
    distinct_date_count: int = Field(gt=0)
    period_start_common_count: int = Field(gt=0)
    period_start_exact_ohlc_count: int = Field(gt=0)
    period_start_exact_ohlcv_count: int = Field(gt=0)
    period_end_common_count: int = Field(gt=0)
    period_end_exact_ohlc_count: int = Field(ge=0)
    period_end_exact_ohlcv_count: int = Field(ge=0)
    volume_only_mismatch_count: int = Field(ge=0)
    maximum_volume_absolute_difference: int = Field(ge=0)

    @field_validator("archive_sha256", "lower_member_sha256", "higher_member_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("evidence hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> "ExternalReconciliationEvidence":
        if self.period_start_exact_ohlc_count > self.period_start_common_count:
            raise ValueError("period-start exact OHLC count exceeds common count")
        if self.period_start_exact_ohlcv_count > self.period_start_common_count:
            raise ValueError("period-start exact OHLCV count exceeds common count")
        if self.period_end_exact_ohlc_count > self.period_end_common_count:
            raise ValueError("period-end exact OHLC count exceeds common count")
        if self.period_end_exact_ohlcv_count > self.period_end_common_count:
            raise ValueError("period-end exact OHLCV count exceeds common count")
        return self


class SourceSemanticsPolicy(FrozenContract):
    schema_version: str = SCHEMA_VERSION
    policy_version: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    market: str = "ABSHODEH"
    symbol: str = Field(min_length=1)
    manifest_path: str
    historical_policy_path: str
    m1_dataset_path: str
    native_m5_dataset_path: str
    source_timezone: str
    timezone_evidence: SemanticEvidence
    period_semantics: PeriodSemantics
    period_evidence: SemanticEvidence
    session_start: str
    session_end: str
    session_end_convention: SessionEndConvention
    session_evidence: SemanticEvidence
    out_of_session_policy: OutOfSessionPolicy
    source_gap_policy: GapPolicy
    coverage_boundary_policy: CoverageBoundaryPolicy
    incomplete_bin_policy: IncompleteBinPolicy
    volume_aggregation: VolumeAggregation
    holiday_calendar_evidence: SemanticEvidence
    minimum_distinct_dates: int = Field(ge=3)
    external_reconciliation: ExternalReconciliationEvidence
    limitations: tuple[str, ...] = Field(min_length=1, max_length=20)

    @field_validator(
        "manifest_path",
        "historical_policy_path",
        "m1_dataset_path",
        "native_m5_dataset_path",
    )
    @classmethod
    def validate_repository_path(cls, value: str) -> str:
        candidate = PurePosixPath(value)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or "\\" in value
            or ":" in value
        ):
            raise ValueError("source-semantics paths must be repository-relative")
        return value

    @model_validator(mode="after")
    def preserve_approved_abshodeh_contract(self) -> "SourceSemanticsPolicy":
        if self.source_timezone != "Asia/Tehran":
            raise ValueError("KAN-14 promotes only the verified Asia/Tehran setting")
        if self.period_semantics is not PeriodSemantics.PERIOD_START:
            raise ValueError("KAN-14 promotes only the reconciled PERIOD_START convention")
        if (self.session_start, self.session_end) != ("09:00:00", "22:00:00"):
            raise ValueError("KAN-14 approved analytical session is 09:00-22:00")
        if self.session_end_convention is not SessionEndConvention.EXCLUSIVE:
            raise ValueError("Abshodeh analytical session end must be exclusive")
        if self.out_of_session_policy is not OutOfSessionPolicy.EXCLUDE_AND_REPORT:
            raise ValueError("out-of-session source prints must be retained and reported")
        if self.source_gap_policy is GapPolicy.REJECT:
            raise ValueError("sparse Faraz source rows require explicit non-reject reporting")
        if self.coverage_boundary_policy is not CoverageBoundaryPolicy.DROP_PARTIAL_FIRST:
            raise ValueError("partial global coverage boundary must be excluded")
        if self.incomplete_bin_policy is not IncompleteBinPolicy.KEEP:
            raise ValueError("sparse source target bins must be retained")
        if self.volume_aggregation is not VolumeAggregation.SUM:
            raise ValueError("reviewed M1-to-M5 source volume aggregation is SUM")
        if self.timezone_evidence.status is not EvidenceStatus.DECLARED:
            raise ValueError("timezone evidence must remain DECLARED")
        if self.period_evidence.status is not EvidenceStatus.DERIVED:
            raise ValueError("period semantics evidence must remain DERIVED")
        if self.session_evidence.status is not EvidenceStatus.DECLARED:
            raise ValueError("session evidence must remain DECLARED")
        if self.holiday_calendar_evidence.status is not EvidenceStatus.UNKNOWN:
            raise ValueError("holiday completeness remains UNKNOWN in KAN-14")
        return self


class DailyReconciliationEvidence(FrozenContract):
    session_date: str
    common_count: int = Field(ge=0)
    exact_ohlc_count: int = Field(ge=0)
    exact_ohlcv_count: int = Field(ge=0)
    generated_only_count: int = Field(ge=0)
    supplied_only_count: int = Field(ge=0)


class ReconciliationCandidateEvidence(FrozenContract):
    period_semantics: PeriodSemantics
    disposition: CandidateDisposition
    generated_count: int = Field(ge=0)
    supplied_count: int = Field(ge=0)
    common_count: int = Field(ge=0)
    exact_ohlc_count: int = Field(ge=0)
    exact_ohlcv_count: int = Field(ge=0)
    generated_only_count: int = Field(ge=0)
    supplied_only_count: int = Field(ge=0)
    volume_only_mismatch_count: int = Field(ge=0)
    maximum_volume_absolute_difference: str
    distinct_date_count: int = Field(ge=0)
    dropped_coverage_boundary_count: int = Field(ge=0)
    daily_evidence: tuple[DailyReconciliationEvidence, ...]

    @model_validator(mode="after")
    def validate_candidate_counts(self) -> "ReconciliationCandidateEvidence":
        for count in (self.exact_ohlc_count, self.exact_ohlcv_count):
            if count > self.common_count:
                raise ValueError("exact match count exceeds common candidate bars")
        if self.distinct_date_count != len(self.daily_evidence):
            raise ValueError("distinct date count does not match daily evidence")
        return self


class SourceSemanticsArtifact(FrozenContract):
    artifact_id: str = "KAN-14-abshodeh-source-semantics"
    jira_key: str = "KAN-14"
    schema_version: str = SCHEMA_VERSION
    policy_version: str
    policy_sha256: str
    manifest_sha256_before: str
    manifest_sha256_after: str
    protected_source_hashes_before: dict[str, str]
    protected_source_hashes_after: dict[str, str]
    timezone_candidate_matrix: tuple[dict[str, Any], ...]
    period_candidates: tuple[ReconciliationCandidateEvidence, ...]
    promoted_semantics: dict[str, str]
    canonical_source_row_count: int = Field(ge=0)
    analytical_source_row_count: int = Field(ge=0)
    excluded_out_of_session_row_count: int = Field(ge=0)
    excluded_out_of_session_examples: tuple[str, ...] = Field(max_length=10)
    generated_m5_count: int = Field(ge=0)
    native_m5_overlap_count: int = Field(ge=0)
    feature_ineligible_event_count: int = Field(ge=0)
    feature_ineligibility_reasons: dict[str, int]
    censored_label_count: int = Field(ge=0)
    label_outcome_counts: dict[str, int]
    g0_g5_status: dict[str, str]
    pilot_summary: dict[str, Any]
    external_reconciliation: ExternalReconciliationEvidence
    unresolved_evidence: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "policy_sha256",
        "manifest_sha256_before",
        "manifest_sha256_after",
    )
    @classmethod
    def validate_artifact_hash(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("artifact hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def require_protected_immutability(self) -> "SourceSemanticsArtifact":
        if self.manifest_sha256_before != self.manifest_sha256_after:
            raise ValueError("committed manifest changed during KAN-14 execution")
        if self.protected_source_hashes_before != self.protected_source_hashes_after:
            raise ValueError("protected source hashes changed during KAN-14 execution")
        promoted = [
            item
            for item in self.period_candidates
            if item.disposition is CandidateDisposition.PROMOTED
        ]
        if len(promoted) != 1 or promoted[0].period_semantics is not PeriodSemantics.PERIOD_START:
            raise ValueError("exactly one PERIOD_START candidate must be promoted")
        return self


__all__ = [
    "CandidateDisposition",
    "DailyReconciliationEvidence",
    "EvidenceBasis",
    "ExternalReconciliationEvidence",
    "ReconciliationCandidateEvidence",
    "SCHEMA_VERSION",
    "SemanticEvidence",
    "SourceSemanticsArtifact",
    "SourceSemanticsPolicy",
]
