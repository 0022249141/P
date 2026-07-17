"""Versioned contracts for canonical market-data quality evaluation."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CONTRACT_SCHEMA_VERSION = "1.0.0"
EVALUATOR_VERSION = "1.0.0"
MAX_EXAMPLES = 10
MAX_FINDINGS = 50
CANONICAL_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


class EvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    DECLARED = "DECLARED"
    INFERRED = "INFERRED"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class PeriodSemantics(str, Enum):
    PERIOD_START = "PERIOD_START"
    PERIOD_END = "PERIOD_END"
    UNKNOWN = "UNKNOWN"


class VolumeMeaning(str, Enum):
    TICK = "TICK"
    REAL = "REAL"
    PROXY = "PROXY"
    UNKNOWN = "UNKNOWN"


class VolumeAggregation(str, Enum):
    SUM = "SUM"
    FIRST = "FIRST"
    LAST = "LAST"
    UNKNOWN = "UNKNOWN"


class DuplicatePolicy(str, Enum):
    REJECT = "REJECT"
    KEEP_FIRST = "KEEP_FIRST"
    KEEP_LAST = "KEEP_LAST"
    AGGREGATE = "AGGREGATE"
    CUSTOM = "CUSTOM"


class GapPolicy(str, Enum):
    REJECT = "REJECT"
    REPORT = "REPORT"
    ALLOW = "ALLOW"


class ValidationMode(str, Enum):
    VALIDATE_ONLY = "VALIDATE_ONLY"
    REPAIR = "REPAIR"


class DSTAmbiguousPolicy(str, Enum):
    RAISE = "RAISE"
    INFER = "INFER"
    EARLIEST = "EARLIEST"
    LATEST = "LATEST"
    NAT = "NAT"


class DSTNonexistentPolicy(str, Enum):
    RAISE = "RAISE"
    SHIFT_FORWARD = "SHIFT_FORWARD"
    SHIFT_BACKWARD = "SHIFT_BACKWARD"
    NAT = "NAT"


class BoundaryConvention(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class IncompleteBinPolicy(str, Enum):
    REJECT = "REJECT"
    DROP = "DROP"
    KEEP = "KEEP"


class CalendarBehavior(str, Enum):
    CONTINUOUS = "CONTINUOUS"
    VERSIONED_SESSION = "VERSIONED_SESSION"


class GateId(str, Enum):
    G0_PROVENANCE = "G0_PROVENANCE"
    G1_SCHEMA_PARSING = "G1_SCHEMA_PARSING"
    G2_TEMPORAL_INTEGRITY = "G2_TEMPORAL_INTEGRITY"
    G3_OHLC_NUMERIC = "G3_OHLC_NUMERIC"
    G4_CALENDAR_COVERAGE = "G4_CALENDAR_COVERAGE"
    G5_MTF_RECONCILIATION = "G5_MTF_RECONCILIATION"
    G6_FEATURE_REPRODUCTION = "G6_FEATURE_REPRODUCTION"
    G7_ANALYTICAL_ELIGIBILITY = "G7_ANALYTICAL_ELIGIBILITY"
    G8_STATISTICAL_ELIGIBILITY = "G8_STATISTICAL_ELIGIBILITY"
    G9_EXECUTION_BACKTEST_ELIGIBILITY = "G9_EXECUTION_BACKTEST_ELIGIBILITY"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_EVALUATED = "NOT_EVALUATED"


class FrozenContract(BaseModel):
    """Strict immutable base with canonical JSON serialization."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    def to_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json", exclude_none=False)
        text = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return f"{text}\n".encode("utf-8")


class DatasetIdentity(FrozenContract):
    dataset_id: str = Field(min_length=1)
    path: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    byte_size: int | None = Field(default=None, ge=0)
    parser_decision: str | None = Field(default=None, min_length=1)
    parser_schema_version: str | None = Field(default=None, min_length=1)
    manifest_schema_version: str | None = Field(default=None, min_length=1)

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value:
            raise ValueError("dataset path cannot be empty")
        candidate = PurePosixPath(value)
        if candidate.is_absolute() or ".." in candidate.parts or "\\" in value:
            raise ValueError("dataset path must be normalized and repository-relative")
        if ":" in value:
            raise ValueError("dataset path cannot contain a drive or URI scheme")
        return value


class CanonicalBarSchema(FrozenContract):
    schema_version: str = CONTRACT_SCHEMA_VERSION
    columns: tuple[str, ...] = CANONICAL_COLUMNS

    @model_validator(mode="after")
    def require_canonical_columns(self) -> "CanonicalBarSchema":
        if self.columns != CANONICAL_COLUMNS:
            raise ValueError("canonical columns and order are versioned")
        return self


class TimestampSemantics(FrozenContract):
    timezone: str = "UNKNOWN"
    timezone_evidence: EvidenceStatus = EvidenceStatus.UNKNOWN
    period_semantics: PeriodSemantics = PeriodSemantics.UNKNOWN
    period_evidence: EvidenceStatus = EvidenceStatus.UNKNOWN
    ambiguous_policy: DSTAmbiguousPolicy = DSTAmbiguousPolicy.RAISE
    nonexistent_policy: DSTNonexistentPolicy = DSTNonexistentPolicy.RAISE


class VolumeSemantics(FrozenContract):
    meaning: VolumeMeaning = VolumeMeaning.UNKNOWN
    evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN
    aggregation: VolumeAggregation = VolumeAggregation.UNKNOWN

    @model_validator(mode="after")
    def require_volume_evidence(self) -> "VolumeSemantics":
        if self.meaning is not VolumeMeaning.UNKNOWN and self.evidence_status is EvidenceStatus.UNKNOWN:
            raise ValueError("non-unknown volume meaning requires explicit evidence")
        return self


class PriceUnitDeclaration(FrozenContract):
    unit: str = "UNKNOWN"
    evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN
    strictly_positive: bool = False

    @model_validator(mode="after")
    def require_price_evidence(self) -> "PriceUnitDeclaration":
        has_unit_evidence = self.unit != "UNKNOWN" and self.evidence_status is not EvidenceStatus.UNKNOWN
        if self.unit != "UNKNOWN" and not has_unit_evidence:
            raise ValueError("non-unknown price unit requires explicit evidence")
        if self.strictly_positive and not has_unit_evidence:
            raise ValueError("strictly positive prices require an evidenced price unit")
        return self


class CalendarPolicy(FrozenContract):
    policy_version: str = Field(min_length=1)
    behavior: CalendarBehavior
    expected_interval_seconds: int = Field(gt=0)
    timezone: str = "UTC"
    session_start: str | None = None
    session_end: str | None = None
    coverage_end_utc: datetime | None = None

    @model_validator(mode="after")
    def validate_session_contract(self) -> "CalendarPolicy":
        has_start = self.session_start is not None
        has_end = self.session_end is not None
        if has_start != has_end:
            raise ValueError("session_start and session_end must be declared together")
        if self.behavior is CalendarBehavior.VERSIONED_SESSION and not has_start:
            raise ValueError("versioned session behavior requires explicit session bounds")
        for value in (self.session_start, self.session_end):
            if value is not None:
                try:
                    datetime.strptime(value, "%H:%M:%S")
                except ValueError as exc:
                    raise ValueError("session bounds must use HH:MM:SS") from exc
        if self.coverage_end_utc is not None and self.coverage_end_utc.tzinfo is None:
            raise ValueError("coverage_end_utc must be timezone-aware")
        return self


class CanonicalizationPolicy(FrozenContract):
    canonical_schema: CanonicalBarSchema = Field(default_factory=CanonicalBarSchema)
    timestamp: TimestampSemantics = Field(default_factory=TimestampSemantics)
    volume: VolumeSemantics = Field(default_factory=VolumeSemantics)
    price_unit: PriceUnitDeclaration = Field(default_factory=PriceUnitDeclaration)
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.REJECT
    gap_policy: GapPolicy = GapPolicy.REJECT
    validation_mode: ValidationMode = ValidationMode.VALIDATE_ONLY
    strict_columns: bool = True
    supported_parser_decisions: tuple[str, ...] = (
        "IN_MEMORY_DATAFRAME",
        "PYTHON_CSV_EXCEL_DIALECT_WITH_HEADER",
    )
    calendar: CalendarPolicy | None = None

    @model_validator(mode="after")
    def require_explicit_repair(self) -> "CanonicalizationPolicy":
        if (
            self.duplicate_policy is not DuplicatePolicy.REJECT
            and self.validation_mode is not ValidationMode.REPAIR
        ):
            raise ValueError("non-reject duplicate policy requires explicit REPAIR mode")
        return self


class ResamplingPolicy(FrozenContract):
    policy_version: str = Field(min_length=1)
    source_timeframe: str
    target_timeframe: str
    source_period_semantics: PeriodSemantics
    timestamp_label: BoundaryConvention
    closed_boundary: BoundaryConvention
    origin: str = Field(min_length=1)
    offset: str | None = None
    timezone: str
    calendar_behavior: CalendarBehavior
    calendar_version: str = Field(min_length=1)
    incomplete_bin_policy: IncompleteBinPolicy
    volume_aggregation: VolumeAggregation

    @model_validator(mode="after")
    def validate_supported_resampling(self) -> "ResamplingPolicy":
        if self.source_timeframe != "M1":
            raise ValueError("KAN-10 resampling source must be M1")
        if self.source_period_semantics is PeriodSemantics.UNKNOWN:
            raise ValueError("source timestamp period semantics must be explicit")
        if self.target_timeframe not in {"M5", "M15", "M30", "H1", "H4", "D1"}:
            raise ValueError("unsupported KAN-10 target timeframe")
        expected_boundary = (
            BoundaryConvention.LEFT
            if self.source_period_semantics is PeriodSemantics.PERIOD_START
            else BoundaryConvention.RIGHT
        )
        if self.closed_boundary is not expected_boundary:
            raise ValueError(
                f"{self.source_period_semantics.value} source timestamps require "
                f"a {expected_boundary.value}-closed boundary"
            )
        if self.volume_aggregation is VolumeAggregation.UNKNOWN:
            raise ValueError("volume aggregation must be explicitly declared")
        return self


class ReconciliationTolerance(FrozenContract):
    price_absolute: str = "0"
    volume_absolute: str = "0"
    relative: str = "0"

    @field_validator("price_absolute", "volume_absolute", "relative")
    @classmethod
    def validate_nonnegative_decimal(cls, value: str) -> str:
        from decimal import Decimal, InvalidOperation

        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("tolerance must be a decimal string") from exc
        if not parsed.is_finite() or parsed < 0:
            raise ValueError("tolerance must be finite and non-negative")
        return value


class GateFinding(FrozenContract):
    reason_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    affected_record_count: int = Field(ge=0)
    examples: tuple[str, ...] = Field(default=(), max_length=MAX_EXAMPLES)
    evidence_references: tuple[str, ...] = Field(default=(), max_length=20)


class GateResult(FrozenContract):
    gate_id: GateId
    status: GateStatus
    reason_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    checked_record_count: int = Field(ge=0)
    affected_record_count: int = Field(ge=0)
    examples: tuple[str, ...] = Field(default=(), max_length=MAX_EXAMPLES)
    evidence_references: tuple[str, ...] = Field(default=(), max_length=20)
    limitations: tuple[str, ...] = Field(default=(), max_length=20)
    remediation_guidance: tuple[str, ...] = Field(default=(), max_length=20)
    findings: tuple[GateFinding, ...] = Field(default=(), max_length=MAX_FINDINGS)
    evaluator_version: str = EVALUATOR_VERSION
    schema_version: str = CONTRACT_SCHEMA_VERSION


class GateReport(FrozenContract):
    dataset: DatasetIdentity
    results: tuple[GateResult, ...] = Field(max_length=20)
    report_schema_version: str = CONTRACT_SCHEMA_VERSION
    evaluator_version: str = EVALUATOR_VERSION
    limitations: tuple[str, ...] = Field(default=(), max_length=20)


class RepairRecord(FrozenContract):
    action: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    source_rows: tuple[int, ...] = Field(min_length=1)
    detail: str = Field(min_length=1)


class EligibilityRequirement(FrozenContract):
    profile: str = Field(min_length=1)
    required_gates: tuple[GateId, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def reject_duplicate_requirements(self) -> "EligibilityRequirement":
        if len(self.required_gates) != len(set(self.required_gates)):
            raise ValueError("required_gates must be unique")
        return self


class EligibilityBlock(FrozenContract):
    gate_id: GateId
    status: GateStatus | None
    reason_code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class EligibilityDecision(FrozenContract):
    profile: str
    eligible: bool
    evaluated_gates: tuple[GateId, ...]
    blocking_gates: tuple[EligibilityBlock, ...] = Field(max_length=20)
    schema_version: str = CONTRACT_SCHEMA_VERSION


class FieldDifferenceCounts(FrozenContract):
    open: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)
    close: int = Field(default=0, ge=0)
    volume: int = Field(default=0, ge=0)


class ReconciliationResult(FrozenContract):
    missing_target_bars: int = Field(ge=0)
    extra_target_bars: int = Field(ge=0)
    exact_match_count: int = Field(ge=0)
    tolerance_match_count: int = Field(ge=0)
    mismatch_count: int = Field(ge=0)
    field_differences: FieldDifferenceCounts
    mismatch_examples: tuple[str, ...] = Field(default=(), max_length=MAX_EXAMPLES)
    tolerance: ReconciliationTolerance
    schema_version: str = CONTRACT_SCHEMA_VERSION


def contract_payload(value: FrozenContract) -> dict[str, Any]:
    """Return a JSON-compatible deterministic payload for composition."""

    return value.model_dump(mode="json", exclude_none=False)
