"""Immutable contracts for leakage-controlled historical market-event research."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "1.0.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"
    NOT_EVALUATED = "NOT_EVALUATED"


class EligibilityEvidenceState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    NOT_EVALUATED = "NOT_EVALUATED"


class EventDirection(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"


class EventType(str, Enum):
    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"


class OutcomeClass(str, Enum):
    DIRECT_CONTINUATION = "DIRECT_CONTINUATION"
    SWEEP_PULLBACK_CONTINUATION = "SWEEP_PULLBACK_CONTINUATION"
    FALSE_BREAK_REENTRY = "FALSE_BREAK_REENTRY"
    ACCEPTANCE_THEN_EXPANSION = "ACCEPTANCE_THEN_EXPANSION"
    FULL_RANGE_REVERSAL = "FULL_RANGE_REVERSAL"
    NO_RESOLUTION = "NO_RESOLUTION"
    CENSORED = "CENSORED"


class HorizonStatus(str, Enum):
    COMPLETE = "COMPLETE"
    CENSORED = "CENSORED"
    INSUFFICIENT_HORIZON = "INSUFFICIENT_HORIZON"


class MetricScope(str, Enum):
    PRE_TERMINAL_INCLUSIVE = "PRE_TERMINAL_INCLUSIVE"
    COMPLETE_HORIZON_NO_TERMINAL = "COMPLETE_HORIZON_NO_TERMINAL"
    NOT_EVALUATED = "NOT_EVALUATED"


class CensorReason(str, Enum):
    INSUFFICIENT_FUTURE_HORIZON = "INSUFFICIENT_FUTURE_HORIZON"
    SESSION_BOUNDARY = "SESSION_BOUNDARY"
    DATASET_END = "DATASET_END"
    MISSING_BARS = "MISSING_BARS"
    FAILED_ELIGIBILITY = "FAILED_ELIGIBILITY"
    UNAVAILABLE_CALENDAR_SEMANTICS = "UNAVAILABLE_CALENDAR_SEMANTICS"
    INTRABAR_PATH_AMBIGUOUS = "INTRABAR_PATH_AMBIGUOUS"
    OTHER = "OTHER"


class DestinationClass(str, Enum):
    OUTWARD_BARRIER = "OUTWARD_BARRIER"
    INWARD_BARRIER = "INWARD_BARRIER"
    NONE = "NONE"
    CENSORED = "CENSORED"


class PilotStatus(str, Enum):
    BLOCKED_BY_SOURCE_SEMANTICS = "BLOCKED_BY_SOURCE_SEMANTICS"
    BLOCKED_BY_CANONICAL_GATES = "BLOCKED_BY_CANONICAL_GATES"
    BLOCKED_BY_RECONCILIATION = "BLOCKED_BY_RECONCILIATION"
    ELIGIBLE = "ELIGIBLE"


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    def to_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json", exclude_none=False)
        rendered = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        return f"{rendered}\n".encode("ascii")


class CalendarSemanticsEvidence(FrozenContract):
    status: EligibilityEvidenceState
    policy_version: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)


class LabelingEvidence(FrozenContract):
    source_status: EligibilityEvidenceState
    source_profile: str = Field(min_length=1)
    source_reason_code: str = Field(min_length=1)
    calendar_status: EligibilityEvidenceState
    calendar_policy_version: str = Field(min_length=1)
    calendar_reason_code: str = Field(min_length=1)


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field_name} must be UTC")
    return value


def _normalized(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalized(value.model_dump(mode="python", exclude_none=False))
    if isinstance(value, dict):
        return {str(key): _normalized(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    if isinstance(value, datetime):
        parsed = _utc(value, "event ID timestamp")
        return parsed.isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        _normalized(payload),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def build_event_id(material: dict[str, Any]) -> str:
    return f"evt_{canonical_hash(material)}"


class MarketEventIdentity(FrozenContract):
    event_id: str = Field(pattern=r"^evt_[0-9a-f]{64}$")
    schema_version: str = SCHEMA_VERSION
    event_policy_version: str = Field(min_length=1)
    market: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    source_timeframe: str = Field(min_length=1)
    source_dataset_id: str = Field(min_length=1)
    source_sha256: str
    implementation_identifier: str = Field(min_length=1)
    source_parameters: tuple[str, ...] = Field(min_length=1)
    source_parameter_sha256: str
    event_type: EventType
    direction: EventDirection
    level_type: str = Field(min_length=1)
    level_price: Decimal
    level_origin_timestamp: datetime
    observation_timestamp: datetime
    confirmation_or_availability_timestamp: datetime
    first_feature_eligible_timestamp: datetime

    @field_validator("source_sha256", "source_parameter_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("hashes must be lowercase SHA-256")
        return value

    @field_validator(
        "level_origin_timestamp",
        "observation_timestamp",
        "confirmation_or_availability_timestamp",
        "first_feature_eligible_timestamp",
    )
    @classmethod
    def validate_utc(cls, value: datetime, info: Any) -> datetime:
        return _utc(value, info.field_name)

    def identity_material(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude={"event_id"}, exclude_none=False)

    @model_validator(mode="after")
    def validate_identity(self) -> "MarketEventIdentity":
        if not (
            self.level_origin_timestamp
            <= self.observation_timestamp
            <= self.confirmation_or_availability_timestamp
            <= self.first_feature_eligible_timestamp
        ):
            raise ValueError(
                "event timestamps must satisfy origin <= observation <= confirmation <= eligibility"
            )
        expected_direction = (
            EventDirection.ABOVE
            if self.event_type is EventType.SWING_HIGH
            else EventDirection.BELOW
        )
        if self.direction is not expected_direction:
            raise ValueError("swing event direction must match its high/low level side")
        if self.event_id != build_event_id(self.identity_material()):
            raise ValueError("event_id does not match canonical material inputs")
        return self

    @classmethod
    def create(cls, **material: Any) -> "MarketEventIdentity":
        material.setdefault("schema_version", SCHEMA_VERSION)
        event_id = build_event_id(material)
        return cls(event_id=event_id, **material)


class AsOfFeatureSnapshot(FrozenContract):
    event_id: str = Field(pattern=r"^evt_[0-9a-f]{64}$")
    schema_version: str = SCHEMA_VERSION
    feature_policy_version: str = Field(min_length=1)
    snapshot_timestamp: datetime
    feature_status: EvidenceStatus = EvidenceStatus.DERIVED
    atr_value: Decimal = Field(gt=0)
    atr_lookback_bars: int = Field(gt=1)
    prior_touch_count: int = Field(ge=0)
    prior_touch_lookback_bars: int = Field(gt=0)
    level_age_seconds: int = Field(ge=0)
    approach_velocity_atr: Decimal
    approach_lookback_bars: int = Field(gt=0)
    approach_overlap_ratio: Decimal = Field(ge=0, le=1)
    compression_lookback_bars: int = Field(gt=1)
    range_expansion_ratio: Decimal = Field(ge=0)
    range_expansion_lookback_bars: int = Field(gt=1)
    body_ratio: Decimal = Field(ge=0, le=1)
    upper_wick_ratio: Decimal = Field(ge=0, le=1)
    lower_wick_ratio: Decimal = Field(ge=0, le=1)
    penetration_at_snapshot_atr: Decimal
    session_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    neutral_session_bucket: str = Field(min_length=1)
    htf_location: Decimal | None = None
    htf_location_status: EvidenceStatus = EvidenceStatus.NOT_EVALUATED
    herat_status: EvidenceStatus = EvidenceStatus.NOT_EVALUATED
    xauusd_status: EvidenceStatus = EvidenceStatus.NOT_EVALUATED
    source_bar_count: int = Field(gt=0)

    @field_validator("snapshot_timestamp")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _utc(value, "snapshot_timestamp")

    @model_validator(mode="after")
    def validate_unknown_features(self) -> "AsOfFeatureSnapshot":
        if self.htf_location is None and self.htf_location_status not in {
            EvidenceStatus.UNKNOWN,
            EvidenceStatus.NOT_EVALUATED,
        }:
            raise ValueError("missing HTF location requires UNKNOWN or NOT_EVALUATED")
        if self.herat_status is not EvidenceStatus.NOT_EVALUATED:
            raise ValueError("Herat must remain NOT_EVALUATED in KAN-13")
        if self.xauusd_status is not EvidenceStatus.NOT_EVALUATED:
            raise ValueError("XAUUSD must remain NOT_EVALUATED in KAN-13")
        return self


class HistoricalOutcomeLabel(FrozenContract):
    event_id: str = Field(pattern=r"^evt_[0-9a-f]{64}$")
    schema_version: str = SCHEMA_VERSION
    label_policy_version: str = Field(min_length=1)
    horizon_start_timestamp: datetime
    horizon_end_timestamp: datetime | None
    maximum_horizon_bars: int = Field(gt=0)
    maximum_horizon_seconds: int = Field(gt=0)
    outcome_class: OutcomeClass
    metric_scope: MetricScope
    metric_end_timestamp: datetime | None
    metric_bar_count: int = Field(ge=0)
    penetration_depth_atr: Decimal | None = Field(
        description="Maximum outward wick distance through the metric end, inclusive."
    )
    pullback_depth_atr: Decimal | None = Field(
        description="Maximum inward close distance through the metric end, inclusive."
    )
    mae_atr: Decimal | None = Field(
        description="Maximum inward wick excursion through the metric end, inclusive."
    )
    mfe_atr: Decimal | None = Field(
        description="Maximum outward wick excursion through the metric end, inclusive."
    )
    bars_outside_level: int = Field(
        ge=0,
        description="Completed closes outside the level through the metric end, inclusive.",
    )
    seconds_outside_level: int = Field(
        ge=0,
        description="Outside-bar count times the declared bar duration within metric scope.",
    )
    reentry_timestamp: datetime | None
    acceptance_timestamp: datetime | None
    time_to_destination_seconds: int | None = Field(default=None, ge=0)
    final_destination_class: DestinationClass
    horizon_status: HorizonStatus
    conflict_status: str = Field(min_length=1)

    @field_validator(
        "horizon_start_timestamp",
        "horizon_end_timestamp",
        "metric_end_timestamp",
        "reentry_timestamp",
        "acceptance_timestamp",
    )
    @classmethod
    def validate_optional_utc(cls, value: datetime | None, info: Any) -> datetime | None:
        return None if value is None else _utc(value, info.field_name)

    @model_validator(mode="after")
    def validate_outcome_state(self) -> "HistoricalOutcomeLabel":
        if (
            self.horizon_end_timestamp is not None
            and self.horizon_end_timestamp < self.horizon_start_timestamp
        ):
            raise ValueError("label horizon end cannot precede its start")
        for field_name in ("reentry_timestamp", "acceptance_timestamp"):
            timestamp = getattr(self, field_name)
            if timestamp is None:
                continue
            if timestamp < self.horizon_start_timestamp:
                raise ValueError(f"{field_name} cannot precede the horizon")
            if (
                self.horizon_end_timestamp is not None
                and timestamp > self.horizon_end_timestamp
            ):
                raise ValueError(f"{field_name} cannot follow the horizon")
        if self.outcome_class is OutcomeClass.CENSORED:
            if self.final_destination_class is not DestinationClass.CENSORED:
                raise ValueError("censored labels require a censored destination")
            if self.horizon_status is HorizonStatus.COMPLETE:
                raise ValueError("censored labels cannot have a complete horizon")
            if (
                self.metric_scope is not MetricScope.NOT_EVALUATED
                or self.metric_end_timestamp is not None
                or self.metric_bar_count != 0
            ):
                raise ValueError("censored labels cannot claim evaluated metrics")
        else:
            if self.horizon_end_timestamp is None:
                raise ValueError("resolved labels require a horizon end")
            if self.horizon_status is not HorizonStatus.COMPLETE:
                raise ValueError("resolved labels require a complete horizon")
            if self.final_destination_class is DestinationClass.CENSORED:
                raise ValueError("resolved labels cannot have a censored destination")
            if self.metric_end_timestamp != self.horizon_end_timestamp:
                raise ValueError("resolved label metrics must end with outcome evidence")
            if self.metric_bar_count <= 0:
                raise ValueError("resolved labels require at least one metric bar")
            if self.outcome_class is OutcomeClass.NO_RESOLUTION:
                if self.metric_scope is not MetricScope.COMPLETE_HORIZON_NO_TERMINAL:
                    raise ValueError("no-resolution metrics require the complete horizon")
            elif self.metric_scope is not MetricScope.PRE_TERMINAL_INCLUSIVE:
                raise ValueError("terminal outcomes require pre-terminal-inclusive metrics")
        return self


class CensoringRecord(FrozenContract):
    event_id: str = Field(pattern=r"^evt_[0-9a-f]{64}$")
    schema_version: str = SCHEMA_VERSION
    label_policy_version: str = Field(min_length=1)
    primary_reason: CensorReason
    secondary_reasons: tuple[CensorReason, ...] = ()
    evidence_start_timestamp: datetime
    evidence_end_timestamp: datetime | None
    detail: str = Field(min_length=1)

    @field_validator("evidence_start_timestamp", "evidence_end_timestamp")
    @classmethod
    def validate_optional_utc(cls, value: datetime | None, info: Any) -> datetime | None:
        return None if value is None else _utc(value, info.field_name)

    @model_validator(mode="after")
    def validate_evidence_order(self) -> "CensoringRecord":
        if (
            self.evidence_end_timestamp is not None
            and self.evidence_end_timestamp < self.evidence_start_timestamp
        ):
            raise ValueError("censoring evidence end cannot precede its start")
        return self


class LineageRecord(FrozenContract):
    scope_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    source_dataset_ids: tuple[str, ...] = Field(min_length=1)
    source_sha256s: tuple[str, ...] = Field(min_length=1)
    canonical_policy_version: str = Field(min_length=1)
    event_policy_version: str = Field(min_length=1)
    feature_policy_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    session_policy_version: str = Field(min_length=1)
    analytical_source_path: str = Field(min_length=1)
    analytical_source_sha256: str
    analytical_source_parameters: tuple[str, ...] = Field(min_length=1)
    code_revision: str = Field(min_length=1)
    dirty_tree: bool
    diff_sha256: str | None = None
    python_version: str = Field(min_length=1)
    pandas_version: str = Field(min_length=1)
    numpy_version: str = Field(min_length=1)

    @field_validator("source_sha256s")
    @classmethod
    def validate_source_hashes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(_SHA256.fullmatch(value) is None for value in values):
            raise ValueError("source hashes must be lowercase SHA-256")
        return values

    @field_validator("analytical_source_sha256", "diff_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is not None and _SHA256.fullmatch(value) is None:
            raise ValueError("hash must be lowercase SHA-256")
        return value

    @field_validator("analytical_source_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if "\\" in value or value.startswith("/") or ":" in value or ".." in value.split("/"):
            raise ValueError("analytical source path must be repository-relative")
        return value

    @model_validator(mode="after")
    def validate_dirty_lineage(self) -> "LineageRecord":
        if self.dirty_tree != (self.diff_sha256 is not None):
            raise ValueError("dirty lineage requires exactly one diff hash")
        return self


class GateAudit(FrozenContract):
    gate_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    findings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class HistoricalExtractionResult(FrozenContract):
    extraction_id: str = Field(pattern=r"^xtr_[0-9a-f]{64}$")
    schema_version: str = SCHEMA_VERSION
    source_dataset_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_bundle_version: str = Field(min_length=1)
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligibility_profile: str = Field(min_length=1)
    gate_audit: tuple[GateAudit, ...]
    labeling_evidence: LabelingEvidence
    events: tuple[MarketEventIdentity, ...]
    features: tuple[AsOfFeatureSnapshot, ...]
    labels: tuple[HistoricalOutcomeLabel, ...]
    censoring: tuple[CensoringRecord, ...]
    catalog_generated: bool = True
    event_count: int = Field(ge=0)
    feature_count: int = Field(ge=0)
    label_count: int = Field(ge=0)
    censoring_count: int = Field(ge=0)

    def identity_material(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude={"extraction_id"})

    @model_validator(mode="after")
    def validate_extraction(self) -> "HistoricalExtractionResult":
        if self.extraction_id != f"xtr_{canonical_hash(self.identity_material())}":
            raise ValueError("extraction_id does not match deterministic result material")
        if not self.catalog_generated:
            raise ValueError("an extraction result represents a generated in-memory catalog")
        if self.event_count != len(self.events):
            raise ValueError("event_count does not match events")
        if self.feature_count != len(self.features):
            raise ValueError("feature_count does not match features")
        if self.label_count != len(self.labels):
            raise ValueError("label_count does not match labels")
        if self.censoring_count != len(self.censoring):
            raise ValueError("censoring_count does not match censoring")
        event_ids = {event.event_id for event in self.events}
        if len(event_ids) != len(self.events):
            raise ValueError("historical extraction events must be unique")
        if len(self.features) != len(self.events):
            raise ValueError("every event requires exactly one feature snapshot")
        if event_ids != {feature.event_id for feature in self.features}:
            raise ValueError("every event requires exactly one feature snapshot")
        if len(self.labels) != len(self.events):
            raise ValueError("every event requires exactly one historical label")
        if event_ids != {label.event_id for label in self.labels}:
            raise ValueError("every event requires exactly one historical label")
        censored_ids = {
            label.event_id
            for label in self.labels
            if label.outcome_class is OutcomeClass.CENSORED
        }
        if censored_ids != {record.event_id for record in self.censoring}:
            raise ValueError("censoring records must match censored labels")
        if len(self.censoring) != len(censored_ids):
            raise ValueError("every censored label requires exactly one censoring record")
        by_gate = {gate.gate_id: gate.status for gate in self.gate_audit}
        required = tuple(f"G{index}_" for index in range(6))
        for prefix in required:
            matches = [status for gate_id, status in by_gate.items() if gate_id.startswith(prefix)]
            if matches != ["PASS"]:
                raise ValueError("historical extraction requires one PASS for every G0-G5 gate")
        return self

    @classmethod
    def create(cls, **material: Any) -> "HistoricalExtractionResult":
        material.setdefault("schema_version", SCHEMA_VERSION)
        material["events"] = tuple(material.get("events", ()))
        material["features"] = tuple(material.get("features", ()))
        material["labels"] = tuple(material.get("labels", ()))
        material["censoring"] = tuple(material.get("censoring", ()))
        material["event_count"] = len(material["events"])
        material["feature_count"] = len(material["features"])
        material["label_count"] = len(material["labels"])
        material["censoring_count"] = len(material["censoring"])
        extraction_id = f"xtr_{canonical_hash(material)}"
        return cls(extraction_id=extraction_id, **material)


class BlockedPilotAuditSummary(FrozenContract):
    artifact_id: str = "KAN-13-abshodeh-pilot-summary"
    jira_key: str = "KAN-13"
    schema_version: str = SCHEMA_VERSION
    status: PilotStatus
    dataset_id: str = Field(min_length=1)
    dataset_path: str = Field(min_length=1)
    source_sha256: str
    byte_size: int = Field(ge=0)
    row_count: int = Field(ge=0)
    coverage_start: str = Field(min_length=1)
    coverage_end: str = Field(min_length=1)
    requested_configuration: dict[str, str]
    gate_audit: tuple[GateAudit, ...]
    unresolved_evidence: tuple[str, ...] = ()
    catalog_generated: bool = False
    eligible_event_count: int = 0
    eligible_feature_count: int = 0
    eligible_label_count: int = 0
    g6_g9_status: dict[str, str]
    herat_status: EvidenceStatus = EvidenceStatus.NOT_EVALUATED
    xauusd_status: EvidenceStatus = EvidenceStatus.NOT_EVALUATED
    limitations: tuple[str, ...] = Field(min_length=1)

    @field_validator("source_sha256")
    @classmethod
    def validate_source_hash(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("source hash must be lowercase SHA-256")
        return value

    @field_validator("dataset_path")
    @classmethod
    def validate_dataset_path(cls, value: str) -> str:
        if "\\" in value or value.startswith("/") or ":" in value or ".." in value.split("/"):
            raise ValueError("dataset path must be repository-relative")
        return value

    @model_validator(mode="after")
    def require_blocked_output_boundary(self) -> "BlockedPilotAuditSummary":
        if self.status is not PilotStatus.ELIGIBLE:
            if (
                self.catalog_generated
                or self.eligible_event_count
                or self.eligible_feature_count
                or self.eligible_label_count
            ):
                raise ValueError("blocked pilot cannot emit eligible historical records")
        elif not self.catalog_generated:
            raise ValueError("eligible pilot summaries require generated output")
        if self.herat_status is not EvidenceStatus.NOT_EVALUATED:
            raise ValueError("Herat remains NOT_EVALUATED")
        if self.xauusd_status is not EvidenceStatus.NOT_EVALUATED:
            raise ValueError("XAUUSD remains NOT_EVALUATED")
        return self


__all__ = [
    "AsOfFeatureSnapshot",
    "BlockedPilotAuditSummary",
    "CalendarSemanticsEvidence",
    "CensorReason",
    "CensoringRecord",
    "DestinationClass",
    "EventDirection",
    "EventType",
    "EvidenceStatus",
    "EligibilityEvidenceState",
    "GateAudit",
    "HistoricalExtractionResult",
    "HistoricalOutcomeLabel",
    "HorizonStatus",
    "LineageRecord",
    "LabelingEvidence",
    "MarketEventIdentity",
    "MetricScope",
    "OutcomeClass",
    "PilotStatus",
    "SCHEMA_VERSION",
    "build_event_id",
    "canonical_hash",
]
