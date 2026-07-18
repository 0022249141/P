"""Deterministic contracts for structure and liquidity characterization."""

from __future__ import annotations

import json
import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "1.0.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    NONE = "NONE"


class EligibilityClassification(str, Enum):
    REALTIME_ELIGIBLE = "REALTIME_ELIGIBLE"
    POST_CONFIRMATION = "POST_CONFIRMATION"
    INELIGIBLE = "INELIGIBLE"


class ComparisonClassification(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    EQUIVALENT_WITH_PARAMETER_MAPPING = "EQUIVALENT_WITH_PARAMETER_MAPPING"
    INTENTIONALLY_DIVERGENT = "INTENTIONALLY_DIVERGENT"
    FUTURE_DERIVED_UNSAFE = "FUTURE_DERIVED_UNSAFE"
    BLOCKED_BY_MISSING_SEMANTICS = "BLOCKED_BY_MISSING_SEMANTICS"


class CapabilityStatus(str, Enum):
    OBSERVED = "OBSERVED"
    NOT_EXPOSED = "NOT_EXPOSED"
    BLOCKED = "BLOCKED"


class TemporalCheckStatus(str, Enum):
    DETECTED = "DETECTED"
    NOT_DETECTED = "NOT_DETECTED"
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


def _parse_utc(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    candidate = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field_name} must be UTC and offset-aware")
    return parsed


class FixtureEvidence(FrozenContract):
    fixture_id: str = Field(min_length=1)
    fixture_sha256: str
    row_count: int = Field(ge=1)
    first_timestamp: str
    last_timestamp: str
    purpose: str = Field(min_length=1)

    @field_validator("fixture_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("fixture_sha256 must be a lowercase SHA-256")
        return value

    @field_validator("first_timestamp", "last_timestamp")
    @classmethod
    def validate_timestamps(cls, value: str, info: Any) -> str:
        _parse_utc(value, info.field_name)
        return value


class EventObservation(FrozenContract):
    implementation_identifier: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    direction: Direction
    origin_or_pivot_timestamp: str
    observation_timestamp: str
    confirmation_or_availability_timestamp: str
    first_downstream_eligible_timestamp: str | None
    observed_price_or_level: float
    eligibility_classification: EligibilityClassification
    temporal_evidence: tuple[str, ...] = Field(min_length=1)
    source_fixture: str = Field(min_length=1)
    fixture_sha256: str
    source_parameters: tuple[str, ...] = ()
    raw_observation: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )

    @field_validator("fixture_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("fixture_sha256 must be a lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_temporal_order(self) -> "EventObservation":
        origin = _parse_utc(
            self.origin_or_pivot_timestamp, "origin_or_pivot_timestamp"
        )
        observed = _parse_utc(self.observation_timestamp, "observation_timestamp")
        confirmation = _parse_utc(
            self.confirmation_or_availability_timestamp,
            "confirmation_or_availability_timestamp",
        )
        eligible = _parse_utc(
            self.first_downstream_eligible_timestamp,
            "first_downstream_eligible_timestamp",
        )
        assert origin is not None and observed is not None and confirmation is not None
        if observed < origin:
            raise ValueError("observation_timestamp cannot precede the origin")
        if confirmation < origin:
            raise ValueError("confirmation cannot precede the origin")
        if confirmation < observed:
            raise ValueError("confirmation cannot precede observation")
        if self.eligibility_classification is EligibilityClassification.INELIGIBLE:
            if eligible is not None:
                raise ValueError("ineligible events cannot declare downstream eligibility")
        elif eligible is None or eligible < observed or eligible < confirmation:
            raise ValueError(
                "eligible events require a timestamp at or after both observation "
                "and confirmation"
            )
        return self


class CapabilityObservation(FrozenContract):
    capability: str = Field(min_length=1)
    status: CapabilityStatus
    evidence: str = Field(min_length=1)
    fixture_ids: tuple[str, ...] = ()


class TemporalCheck(FrozenContract):
    check: str = Field(min_length=1)
    status: TemporalCheckStatus
    evidence: str = Field(min_length=1)
    source_lines: tuple[int, ...] = ()
    fixture_ids: tuple[str, ...] = ()


class ImplementationSnapshot(FrozenContract):
    implementation_identifier: str = Field(min_length=1)
    repository_path: str = Field(min_length=1)
    source_sha256: str
    domain: str = Field(pattern=r"^(STRUCTURE|LIQUIDITY)$")
    events: tuple[EventObservation, ...] = ()
    capabilities: tuple[CapabilityObservation, ...] = ()
    temporal_checks: tuple[TemporalCheck, ...] = ()

    @field_validator("repository_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized != value or value.startswith("/") or ":" in value or ".." in value.split("/"):
            raise ValueError("repository_path must be normalized and repository-relative")
        return value

    @field_validator("source_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("source_sha256 must be a lowercase SHA-256")
        return value


class Comparison(FrozenContract):
    comparison_id: str = Field(min_length=1)
    left_implementation: str = Field(min_length=1)
    right_implementation: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    classification: ComparisonClassification
    evidence: str = Field(min_length=1)
    fixture_ids: tuple[str, ...] = ()
    parameter_mapping: tuple[str, ...] = ()


class Artifact(FrozenContract):
    artifact_id: str = "KAN-11-structure-liquidity-comparison"
    jira_key: str = "KAN-11"
    schema_version: str = SCHEMA_VERSION
    fixture_scope: str = "SYNTHETIC_ONLY"
    fixtures: tuple[FixtureEvidence, ...]
    implementation_snapshots: tuple[ImplementationSnapshot, ...]
    comparisons: tuple[Comparison, ...]
    limitations: tuple[str, ...]

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
