"""Versioned policy contracts for KAN-13 research labeling."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from pipelines.historical_labeling.contracts import (
    EvidenceStatus,
    FrozenContract,
    canonical_hash,
)


EVENT_POLICY_VERSION = "layer2-confirmed-swings-v1"
FEATURE_POLICY_VERSION = "asof-features-v1"
LABEL_POLICY_VERSION = "abshodeh-level-outcome-v1"
SESSION_POLICY_VERSION = "abshodeh-research-session-v1"
CANONICAL_REQUEST_VERSION = "abshodeh-canonical-request-v1"


class EventSourcePolicy(FrozenContract):
    policy_version: str = EVENT_POLICY_VERSION
    implementation_identifier: str = "layer2-structure"
    repository_path: str = "src/layer2_structural_engine.py"
    source_sha256: str
    event_bar_seconds: int = Field(gt=0)
    min_strength: Decimal = Decimal("0.6")
    lookback: int = 2
    allowed_event_types: tuple[str, ...] = ("SWING_HIGH", "SWING_LOW")

    @model_validator(mode="after")
    def preserve_approved_source(self) -> "EventSourcePolicy":
        if self.min_strength != Decimal("0.6") or self.lookback != 2:
            raise ValueError("KAN-13 must preserve approved layer-2 source parameters")
        if self.allowed_event_types != ("SWING_HIGH", "SWING_LOW"):
            raise ValueError("KAN-13 event source is limited to confirmed swings")
        return self

    def parameter_strings(self) -> tuple[str, ...]:
        return (
            f"event_bar_seconds={self.event_bar_seconds}",
            f"lookback={self.lookback}",
            f"min_strength={format(self.min_strength, 'f')}",
        )

    def parameter_sha256(self) -> str:
        return canonical_hash({"parameters": self.parameter_strings()})


class FeaturePolicy(FrozenContract):
    policy_version: str = FEATURE_POLICY_VERSION
    atr_lookback_bars: int = 14
    prior_touch_lookback_bars: int = 50
    prior_touch_tolerance_atr: Decimal = Decimal("0.10")
    approach_lookback_bars: int = 3
    compression_lookback_bars: int = 5
    event_bar_seconds: int = Field(gt=0)
    range_expansion_lookback_bars: int = 14
    htf_timeframe: str = "H1"
    htf_bar_seconds: int = Field(gt=0)


class LabelPolicy(FrozenContract):
    policy_version: str = LABEL_POLICY_VERSION
    penetration_atr: Decimal
    reentry_close_atr: Decimal = Field(ge=0)
    qualifying_pullback_atr: Decimal
    continuation_atr: Decimal
    reversal_atr: Decimal
    acceptance_close_atr: Decimal
    acceptance_consecutive_closes: int = Field(gt=0)
    maximum_horizon_bars: int = Field(gt=0)
    maximum_horizon_seconds: int = Field(gt=0)
    expected_bar_seconds: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_symmetric_thresholds(self) -> "LabelPolicy":
        for value in (
            self.penetration_atr,
            self.qualifying_pullback_atr,
            self.continuation_atr,
            self.reversal_atr,
            self.acceptance_close_atr,
        ):
            if value <= 0:
                raise ValueError("label thresholds must be positive magnitudes")
        if self.maximum_horizon_seconds != (
            self.maximum_horizon_bars * self.expected_bar_seconds
        ):
            raise ValueError("bar and elapsed-time horizons must agree")
        return self


class SessionPolicy(FrozenContract):
    policy_version: str = SESSION_POLICY_VERSION
    timezone: str
    timestamp_period_semantics: str
    session_start: str
    session_end: str
    evidence_status: EvidenceStatus
    holiday_calendar_status: EvidenceStatus
    allow_cross_session_outcomes: bool = False
    neutral_buckets: tuple[str, ...]

    @model_validator(mode="after")
    def preserve_research_boundary(self) -> "SessionPolicy":
        if self.timezone != "Asia/Tehran":
            raise ValueError("KAN-13 pilot timezone request is Asia/Tehran")
        if self.timestamp_period_semantics != "PERIOD_START":
            raise ValueError("KAN-13 pilot requests PERIOD_START semantics")
        if self.session_start != "09:00:00" or self.session_end != "22:00:00":
            raise ValueError("KAN-13 pilot session request is 09:00-22:00")
        if self.evidence_status is not EvidenceStatus.HYPOTHESIS:
            raise ValueError("requested source semantics remain a hypothesis")
        if self.holiday_calendar_status not in {
            EvidenceStatus.UNKNOWN,
            EvidenceStatus.NOT_EVALUATED,
        }:
            raise ValueError("holiday completeness cannot be promoted in KAN-13")
        if self.allow_cross_session_outcomes:
            raise ValueError("KAN-13 does not permit cross-session outcomes")
        return self


class PilotDatasetPolicy(FrozenContract):
    dataset_id: str
    dataset_path: str
    source_timeframe: str = "M1"
    event_timeframe: str = "M5"
    reconciliation_path: str
    diagnostic_timeframe: str = "H1"
    market: str = "ABSHODEH"
    symbol: str = "abshodeNaghdi"
    canonical_request_version: str = CANONICAL_REQUEST_VERSION


class ResearchPolicyBundle(FrozenContract):
    bundle_version: str
    dataset: PilotDatasetPolicy
    event_source: EventSourcePolicy
    features: FeaturePolicy
    labels: LabelPolicy
    session: SessionPolicy

    def policy_sha256(self) -> str:
        return canonical_hash(self.model_dump(mode="python", exclude_none=False))


def load_policy(path: Path) -> ResearchPolicyBundle:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    return ResearchPolicyBundle.model_validate(payload)


__all__ = [
    "CANONICAL_REQUEST_VERSION",
    "EVENT_POLICY_VERSION",
    "FEATURE_POLICY_VERSION",
    "LABEL_POLICY_VERSION",
    "SESSION_POLICY_VERSION",
    "EventSourcePolicy",
    "FeaturePolicy",
    "LabelPolicy",
    "PilotDatasetPolicy",
    "ResearchPolicyBundle",
    "SessionPolicy",
    "load_policy",
]
