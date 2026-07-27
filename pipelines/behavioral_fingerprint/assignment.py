"""Label-free assignment of as-of features to preregistered cells."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from pipelines.behavioral_fingerprint.contracts import CellBucket
from pipelines.behavioral_fingerprint.policies import (
    BehavioralFingerprintPolicy,
    BucketDimensionPolicy,
    FeatureDimension,
    FingerprintViewPolicy,
)
from pipelines.historical_labeling.contracts import (
    AsOfFeatureSnapshot,
    EventDirection,
    EventType,
    FrozenContract,
    MarketEventIdentity,
    canonical_hash,
)


class FeatureCellAssignment(FrozenContract):
    assignment_id: str = Field(pattern=r"^fpa_[0-9a-f]{64}$")
    event_id: str = Field(pattern=r"^evt_[0-9a-f]{64}$")
    cell_id: str = Field(pattern=r"^fpc_[0-9a-f]{64}$")
    view_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    event_type: EventType
    direction: EventDirection
    neutral_session_bucket: str = Field(min_length=1)
    feature_buckets: tuple[CellBucket, ...]
    feature_bucket_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligibility_timestamp: datetime

    @model_validator(mode="after")
    def validate_assignment_id(self) -> "FeatureCellAssignment":
        material = self.model_dump(mode="python", exclude={"assignment_id"})
        if self.assignment_id != f"fpa_{canonical_hash(material)}":
            raise ValueError("assignment_id does not match deterministic material")
        return self

    @classmethod
    def create(cls, **material: object) -> "FeatureCellAssignment":
        assignment_id = f"fpa_{canonical_hash(material)}"
        return cls(assignment_id=assignment_id, **material)


def _format_decimal(value: Decimal) -> str:
    rendered = format(value.normalize(), "f")
    return "0" if rendered in {"-0", ""} else rendered


def _bucket_label(value: Decimal, policy: BucketDimensionPolicy) -> str:
    edges = policy.edges
    if value < edges[0]:
        return f"LT_{_format_decimal(edges[0])}"
    for lower, upper in zip(edges, edges[1:], strict=False):
        if lower <= value < upper:
            return (
                f"GE_{_format_decimal(lower)}"
                f"_LT_{_format_decimal(upper)}"
            )
    return f"GE_{_format_decimal(edges[-1])}"


def _feature_value(
    feature: AsOfFeatureSnapshot,
    dimension: FeatureDimension,
) -> Decimal:
    raw = getattr(feature, dimension.value)
    if raw is None:
        raise ValueError(
            f"configured feature dimension is unavailable: {dimension.value}"
        )
    if isinstance(raw, Decimal):
        return raw
    return Decimal(raw)


def _definition_sha256(
    view: FingerprintViewPolicy,
    policy: BehavioralFingerprintPolicy,
) -> str:
    dimensions = policy.dimension_map()
    return canonical_hash(
        {
            "view_id": view.view_id,
            "base_dimensions": (
                "event_type",
                "direction",
                "neutral_session_bucket",
            ),
            "feature_dimensions": [
                dimensions[item].model_dump(mode="python", exclude_none=False)
                for item in view.dimensions
            ],
        }
    )


def assignment_source_sha256(
    events: tuple[MarketEventIdentity, ...],
    features: tuple[AsOfFeatureSnapshot, ...],
) -> str:
    return canonical_hash(
        {
            "events": [
                event.model_dump(mode="python", exclude_none=False)
                for event in sorted(events, key=lambda item: item.event_id)
            ],
            "features": [
                feature.model_dump(mode="python", exclude_none=False)
                for feature in sorted(features, key=lambda item: item.event_id)
            ],
        }
    )


def build_feature_assignments(
    events: tuple[MarketEventIdentity, ...],
    features: tuple[AsOfFeatureSnapshot, ...],
    *,
    policy: BehavioralFingerprintPolicy,
    code_revision: str,
) -> tuple[FeatureCellAssignment, ...]:
    """Assign cells without accepting or reading any retrospective label."""

    event_ids = {event.event_id for event in events}
    if len(event_ids) != len(events):
        raise ValueError("events must be unique")
    by_feature = {feature.event_id: feature for feature in features}
    if len(by_feature) != len(features) or set(by_feature) != event_ids:
        raise ValueError("every unique event requires exactly one as-of feature")
    if not code_revision:
        raise ValueError("code revision is required")
    if not events:
        raise ValueError("at least one eligible event is required")

    source = assignment_source_sha256(events, features)
    policy_sha = policy.policy_sha256()
    dimensions = policy.dimension_map()
    assignments: list[FeatureCellAssignment] = []
    ordered_events = sorted(
        events,
        key=lambda item: (
            item.first_feature_eligible_timestamp,
            item.event_id,
        ),
    )
    for event in ordered_events:
        feature = by_feature[event.event_id]
        if feature.snapshot_timestamp != event.first_feature_eligible_timestamp:
            raise ValueError("feature snapshot must equal first eligibility timestamp")
        for view in policy.views:
            buckets = tuple(
                CellBucket(
                    dimension=dimension.value,
                    bucket=_bucket_label(
                        _feature_value(feature, dimension),
                        dimensions[dimension],
                    ),
                )
                for dimension in view.dimensions
            )
            definition_sha = _definition_sha256(view, policy)
            cell_material = {
                "schema_version": "1.0.0",
                "policy_version": policy.policy_version,
                "policy_sha256": policy_sha,
                "assignment_source_sha256": source,
                "source_dataset_id": event.source_dataset_id,
                "source_sha256": event.source_sha256,
                "code_revision": code_revision,
                "market": event.market,
                "symbol": event.symbol,
                "feature_policy_version": feature.feature_policy_version,
                "view_id": view.view_id,
                "event_type": event.event_type,
                "direction": event.direction,
                "neutral_session_bucket": feature.neutral_session_bucket,
                "feature_buckets": buckets,
                "feature_bucket_definition_sha256": definition_sha,
            }
            cell_id = f"fpc_{canonical_hash(cell_material)}"
            assignments.append(
                FeatureCellAssignment.create(
                    event_id=event.event_id,
                    cell_id=cell_id,
                    view_id=view.view_id,
                    event_type=event.event_type,
                    direction=event.direction,
                    neutral_session_bucket=feature.neutral_session_bucket,
                    feature_buckets=buckets,
                    feature_bucket_definition_sha256=definition_sha,
                    eligibility_timestamp=event.first_feature_eligible_timestamp,
                )
            )
    return tuple(sorted(assignments, key=lambda item: item.assignment_id))


__all__ = [
    "FeatureCellAssignment",
    "assignment_source_sha256",
    "build_feature_assignments",
]
