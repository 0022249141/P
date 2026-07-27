"""Versioned, preregistered policies for Behavioral Fingerprint cells."""

from __future__ import annotations

import json
from decimal import Decimal
from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from pipelines.historical_labeling.contracts import FrozenContract, canonical_hash


POLICY_SCHEMA_VERSION = "1.0.0"


class FeatureDimension(str, Enum):
    PRIOR_TOUCH_COUNT = "prior_touch_count"
    APPROACH_VELOCITY_ATR = "approach_velocity_atr"
    APPROACH_OVERLAP_RATIO = "approach_overlap_ratio"
    RANGE_EXPANSION_RATIO = "range_expansion_ratio"
    BODY_RATIO = "body_ratio"
    LEVEL_AGE_SECONDS = "level_age_seconds"
    PENETRATION_AT_SNAPSHOT_ATR = "penetration_at_snapshot_atr"


class PartitionStrategy(str, Enum):
    CONTIGUOUS_EQUAL_EVENT_COUNT = "CONTIGUOUS_EQUAL_EVENT_COUNT"


class BucketDimensionPolicy(FrozenContract):
    dimension: FeatureDimension
    edges: tuple[Decimal, ...] = Field(min_length=1)
    unit: str = Field(min_length=1)
    evidence_label: str = "DERIVED_AS_OF_FEATURE"

    @field_validator("edges")
    @classmethod
    def validate_edges(cls, values: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
        if any(not value.is_finite() for value in values):
            raise ValueError("bucket edges must be finite")
        if tuple(sorted(set(values))) != values:
            raise ValueError("bucket edges must be unique and strictly increasing")
        return values


class FingerprintViewPolicy(FrozenContract):
    view_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    dimensions: tuple[FeatureDimension, ...] = ()
    description: str = Field(min_length=1)

    @field_validator("dimensions")
    @classmethod
    def validate_unique_dimensions(
        cls,
        values: tuple[FeatureDimension, ...],
    ) -> tuple[FeatureDimension, ...]:
        if len(values) != len(set(values)):
            raise ValueError("view dimensions must be unique")
        return values


class ChronologicalPartitionPolicy(FrozenContract):
    strategy: PartitionStrategy = PartitionStrategy.CONTIGUOUS_EQUAL_EVENT_COUNT
    partition_count: int = Field(ge=2, le=10)


class SupportPolicy(FrozenContract):
    minimum_cell_events: int = Field(gt=0)
    minimum_resolved_labels: int = Field(gt=0)
    minimum_resolved_per_partition: int = Field(gt=0)
    maximum_descriptive_frequency_range: Decimal = Field(ge=0, le=1)


class BehavioralFingerprintPolicy(FrozenContract):
    schema_version: str = POLICY_SCHEMA_VERSION
    policy_version: str = Field(min_length=1)
    descriptive_frequency_semantics: str = (
        "DESCRIPTIVE_IN_SAMPLE_EMPIRICAL_FREQUENCY"
    )
    quantile_method: str = "DECIMAL_LINEAR_TYPE7"
    dimensions: tuple[BucketDimensionPolicy, ...] = Field(min_length=1)
    views: tuple[FingerprintViewPolicy, ...] = Field(min_length=1)
    chronological_partitions: ChronologicalPartitionPolicy
    support: SupportPolicy
    required_upstream_gates: tuple[str, ...] = (
        "G0_PROVENANCE",
        "G1_SCHEMA_PARSING",
        "G2_TEMPORAL_INTEGRITY",
        "G3_OHLC_NUMERIC",
        "G4_CALENDAR_COVERAGE",
        "G5_MTF_RECONCILIATION",
    )
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_policy(self) -> "BehavioralFingerprintPolicy":
        dimension_names = [item.dimension for item in self.dimensions]
        if len(dimension_names) != len(set(dimension_names)):
            raise ValueError("dimension policies must be unique")
        view_ids = [view.view_id for view in self.views]
        if len(view_ids) != len(set(view_ids)):
            raise ValueError("view IDs must be unique")
        configured = set(dimension_names)
        missing = {
            dimension
            for view in self.views
            for dimension in view.dimensions
            if dimension not in configured
        }
        if missing:
            rendered = sorted(item.value for item in missing)
            raise ValueError(
                f"views reference unconfigured dimensions: {rendered}"
            )
        if "CORE" not in view_ids:
            raise ValueError("a CORE view is required")
        core = next(view for view in self.views if view.view_id == "CORE")
        if core.dimensions:
            raise ValueError("CORE view must not add numeric feature dimensions")
        if self.descriptive_frequency_semantics != (
            "DESCRIPTIVE_IN_SAMPLE_EMPIRICAL_FREQUENCY"
        ):
            raise ValueError("frequency semantics must remain explicitly descriptive")
        if self.quantile_method != "DECIMAL_LINEAR_TYPE7":
            raise ValueError("only the preregistered deterministic quantile is allowed")
        return self

    def policy_sha256(self) -> str:
        return canonical_hash(self.model_dump(mode="python", exclude_none=False))

    def dimension_map(self) -> dict[FeatureDimension, BucketDimensionPolicy]:
        return {item.dimension: item for item in self.dimensions}


def load_policy(path: Path) -> BehavioralFingerprintPolicy:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BehavioralFingerprintPolicy.model_validate(payload)


__all__ = [
    "BehavioralFingerprintPolicy",
    "BucketDimensionPolicy",
    "ChronologicalPartitionPolicy",
    "FeatureDimension",
    "FingerprintViewPolicy",
    "POLICY_SCHEMA_VERSION",
    "PartitionStrategy",
    "SupportPolicy",
    "load_policy",
]
