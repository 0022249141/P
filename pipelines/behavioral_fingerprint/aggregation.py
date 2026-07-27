"""Deterministic aggregation of label-free cells and retrospective outcomes."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal

from pipelines.behavioral_fingerprint.assignment import (
    FeatureCellAssignment,
    assignment_source_sha256,
    build_feature_assignments,
)
from pipelines.behavioral_fingerprint.contracts import (
    BehavioralFingerprintArtifact,
    ChronologicalPartitionDiagnostic,
    DescriptiveFrequency,
    EvidenceClassification,
    FingerprintCell,
    FingerprintGateAudit,
    RobustSummary,
    ViewCoverage,
)
from pipelines.behavioral_fingerprint.policies import BehavioralFingerprintPolicy
from pipelines.historical_labeling.contracts import (
    HistoricalExtractionResult,
    HistoricalOutcomeLabel,
    OutcomeClass,
    canonical_hash,
)


_RESOLVED_OUTCOMES = tuple(
    outcome for outcome in OutcomeClass if outcome is not OutcomeClass.CENSORED
)
_METRIC_FIELDS = (
    "penetration_depth_atr",
    "pullback_depth_atr",
    "mae_atr",
    "mfe_atr",
    "time_to_destination_seconds",
    "seconds_outside_level",
)


def _decimal(value: Decimal | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(value)


def _quantile(values: tuple[Decimal, ...], fraction: Decimal) -> Decimal:
    ordered = tuple(sorted(values))
    if len(ordered) == 1:
        return ordered[0]
    position = Decimal(len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - Decimal(lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _summary(values: list[Decimal]) -> RobustSummary | None:
    if not values:
        return None
    ordered = tuple(sorted(values))
    return RobustSummary(
        eligible_count=len(ordered),
        minimum=ordered[0],
        q25=_quantile(ordered, Decimal("0.25")),
        median=_quantile(ordered, Decimal("0.50")),
        q75=_quantile(ordered, Decimal("0.75")),
        maximum=ordered[-1],
    )


def _frequencies(
    labels: tuple[HistoricalOutcomeLabel, ...],
) -> tuple[DescriptiveFrequency, ...]:
    resolved = tuple(
        label for label in labels if label.outcome_class is not OutcomeClass.CENSORED
    )
    counts = Counter(label.outcome_class for label in resolved)
    denominator = len(resolved)
    return tuple(
        DescriptiveFrequency(
            outcome_class=outcome,
            count=counts[outcome],
            resolved_denominator=denominator,
            value=(
                None
                if denominator == 0
                else Decimal(counts[outcome]) / Decimal(denominator)
            ),
        )
        for outcome in _RESOLVED_OUTCOMES
    )


def _partition_map(
    extraction: HistoricalExtractionResult,
    partition_count: int,
) -> tuple[dict[str, int], tuple[tuple[datetime | None, datetime | None], ...]]:
    events = sorted(
        extraction.events,
        key=lambda item: (
            item.first_feature_eligible_timestamp,
            item.event_id,
        ),
    )
    by_event: dict[str, int] = {}
    timestamps: list[list[datetime]] = [[] for _ in range(partition_count)]
    total = len(events)
    for index, event in enumerate(events):
        partition = min(index * partition_count // total, partition_count - 1)
        by_event[event.event_id] = partition
        timestamps[partition].append(event.first_feature_eligible_timestamp)
    bounds = tuple(
        (
            min(items) if items else None,
            max(items) if items else None,
        )
        for items in timestamps
    )
    return by_event, bounds


def _partition_diagnostics(
    assignments: tuple[FeatureCellAssignment, ...],
    labels: dict[str, HistoricalOutcomeLabel],
    partition_by_event: dict[str, int],
    bounds: tuple[tuple[datetime | None, datetime | None], ...],
) -> tuple[ChronologicalPartitionDiagnostic, ...]:
    grouped: dict[int, list[HistoricalOutcomeLabel]] = defaultdict(list)
    for assignment in assignments:
        grouped[partition_by_event[assignment.event_id]].append(
            labels[assignment.event_id]
        )
    diagnostics = []
    for index, (start, end) in enumerate(bounds):
        partition_labels = tuple(grouped[index])
        censored = sum(
            label.outcome_class is OutcomeClass.CENSORED
            for label in partition_labels
        )
        diagnostics.append(
            ChronologicalPartitionDiagnostic(
                partition_index=index,
                start_timestamp=start,
                end_timestamp=end,
                eligible_event_count=len(partition_labels),
                resolved_label_count=len(partition_labels) - censored,
                censored_label_count=censored,
                outcome_frequencies=_frequencies(partition_labels),
            )
        )
    return tuple(diagnostics)


def _maximum_frequency_range(
    partitions: tuple[ChronologicalPartitionDiagnostic, ...],
) -> Decimal | None:
    if any(partition.resolved_label_count == 0 for partition in partitions):
        return None
    maximum = Decimal(0)
    for outcome in _RESOLVED_OUTCOMES:
        values = [
            next(
                item.value
                for item in partition.outcome_frequencies
                if item.outcome_class is outcome
            )
            for partition in partitions
        ]
        if any(value is None for value in values):
            return None
        typed = [value for value in values if value is not None]
        maximum = max(maximum, max(typed) - min(typed))
    return maximum


def _validate_upstream(
    extraction: HistoricalExtractionResult,
    policy: BehavioralFingerprintPolicy,
) -> None:
    statuses = {gate.gate_id: gate.status for gate in extraction.gate_audit}
    for required in policy.required_upstream_gates:
        matches = [
            status
            for gate_id, status in statuses.items()
            if gate_id.startswith(required)
        ]
        if matches != ["PASS"]:
            raise ValueError(f"upstream gate is not uniquely PASS: {required}")


def _normalized_extraction_id(
    extraction: HistoricalExtractionResult,
) -> str:
    """Canonicalize collection order without weakening upstream validation."""

    material = extraction.model_dump(
        mode="python",
        exclude={"extraction_id"},
        exclude_none=False,
    )
    for field_name in (
        "events",
        "features",
        "labels",
        "censoring",
        "feature_ineligibility",
    ):
        material[field_name] = sorted(
            material[field_name],
            key=lambda item: (
                item["event_id"],
                canonical_hash(item),
            ),
        )
    material["gate_audit"] = sorted(
        material["gate_audit"],
        key=lambda item: item["gate_id"],
    )
    return f"xtr_{canonical_hash(material)}"


def build_behavioral_fingerprint(
    extraction: HistoricalExtractionResult,
    *,
    policy: BehavioralFingerprintPolicy,
    code_revision: str,
) -> BehavioralFingerprintArtifact:
    """Build descriptive cells after label-free assignments are frozen."""

    _validate_upstream(extraction, policy)
    assignments = build_feature_assignments(
        extraction.events,
        extraction.features,
        policy=policy,
        code_revision=code_revision,
    )
    reproduced = build_feature_assignments(
        tuple(reversed(extraction.events)),
        tuple(reversed(extraction.features)),
        policy=policy,
        code_revision=code_revision,
    )
    if assignments != reproduced:
        raise ValueError("G6 feature assignment reproduction failed")

    source = assignment_source_sha256(extraction.events, extraction.features)
    by_label = {label.event_id: label for label in extraction.labels}
    if len(by_label) != len(extraction.labels):
        raise ValueError("historical labels must be unique")
    partition_by_event, bounds = _partition_map(
        extraction,
        policy.chronological_partitions.partition_count,
    )
    by_cell: dict[str, list[FeatureCellAssignment]] = defaultdict(list)
    for assignment in assignments:
        by_cell[assignment.cell_id].append(assignment)

    events_by_id = {event.event_id: event for event in extraction.events}
    features_by_id = {feature.event_id: feature for feature in extraction.features}
    first_event = min(extraction.events, key=lambda item: item.event_id)
    first_feature = features_by_id[first_event.event_id]
    if {
        (event.market, event.symbol, event.source_dataset_id, event.source_sha256)
        for event in extraction.events
    } != {
        (
            first_event.market,
            first_event.symbol,
            extraction.source_dataset_id,
            extraction.source_sha256,
        )
    }:
        raise ValueError("fingerprint input requires one consistent market source")
    feature_versions = {
        feature.feature_policy_version for feature in extraction.features
    }
    if feature_versions != {first_feature.feature_policy_version}:
        raise ValueError("fingerprint input requires one feature policy version")
    label_versions = {label.label_policy_version for label in extraction.labels}
    if len(label_versions) != 1:
        raise ValueError("fingerprint input requires one label policy version")
    label_policy_version = next(iter(label_versions))
    cells: list[FingerprintCell] = []
    policy_sha = policy.policy_sha256()
    for cell_id, cell_assignments_list in by_cell.items():
        cell_assignments = tuple(
            sorted(cell_assignments_list, key=lambda item: item.assignment_id)
        )
        cell_labels = tuple(by_label[item.event_id] for item in cell_assignments)
        first = cell_assignments[0]
        censored_count = sum(
            label.outcome_class is OutcomeClass.CENSORED for label in cell_labels
        )
        resolved_count = len(cell_labels) - censored_count
        counts = Counter(label.outcome_class.value for label in cell_labels)
        outcome_counts = {
            outcome.value: counts[outcome.value] for outcome in OutcomeClass
        }
        metric_summaries: dict[str, RobustSummary] = {}
        resolved_labels = tuple(
            label
            for label in cell_labels
            if label.outcome_class is not OutcomeClass.CENSORED
        )
        for field_name in _METRIC_FIELDS:
            values = [
                _decimal(value)
                for label in resolved_labels
                if (value := getattr(label, field_name)) is not None
            ]
            summary = _summary(values)
            if summary is not None:
                metric_summaries[field_name] = summary
        partitions = _partition_diagnostics(
            cell_assignments,
            by_label,
            partition_by_event,
            bounds,
        )
        maximum_range = _maximum_frequency_range(partitions)
        support = policy.support
        supported = (
            len(cell_labels) >= support.minimum_cell_events
            and resolved_count >= support.minimum_resolved_labels
            and all(
                item.resolved_label_count
                >= support.minimum_resolved_per_partition
                for item in partitions
            )
            and maximum_range is not None
            and maximum_range <= support.maximum_descriptive_frequency_range
        )
        classification = (
            EvidenceClassification.HEURISTIC_ONLY
            if supported
            else EvidenceClassification.NOT_STATISTICALLY_ELIGIBLE
        )
        timestamps = [
            events_by_id[item.event_id].first_feature_eligible_timestamp
            for item in cell_assignments
        ]
        cells.append(
            FingerprintCell(
                cell_id=cell_id,
                policy_version=policy.policy_version,
                policy_sha256=policy_sha,
                assignment_source_sha256=source,
                source_dataset_id=extraction.source_dataset_id,
                source_sha256=extraction.source_sha256,
                code_revision=code_revision,
                market=first_event.market,
                symbol=first_event.symbol,
                feature_policy_version=first_feature.feature_policy_version,
                label_policy_version=label_policy_version,
                view_id=first.view_id,
                event_type=first.event_type,
                direction=first.direction,
                neutral_session_bucket=first.neutral_session_bucket,
                feature_buckets=first.feature_buckets,
                feature_bucket_definition_sha256=(
                    first.feature_bucket_definition_sha256
                ),
                eligibility_start_timestamp=min(timestamps),
                eligibility_end_timestamp=max(timestamps),
                eligible_event_count=len(cell_labels),
                resolved_label_count=resolved_count,
                censored_label_count=censored_count,
                feature_ineligible_count=0,
                missing_semantics_count=0,
                outcome_counts=outcome_counts,
                outcome_frequencies=_frequencies(cell_labels),
                metric_summaries=dict(sorted(metric_summaries.items())),
                chronological_partitions=partitions,
                maximum_descriptive_frequency_range=maximum_range,
                evidence_classification=classification,
                evidence_labels=(
                    "DERIVED_AS_OF_BUCKET_ASSIGNMENT",
                    "RETROSPECTIVE_DESCRIPTIVE_LABEL_SUMMARY",
                    classification.value,
                ),
                limitations=(
                    "Descriptive in-sample evidence is not a calibrated probability.",
                    "Chronological ranges are diagnostics, not out-of-sample validation.",
                ),
            )
        )
    ordered_cells = tuple(sorted(cells, key=lambda item: item.cell_id))
    coverage = []
    for view in policy.views:
        selected = tuple(cell for cell in ordered_cells if cell.view_id == view.view_id)
        coverage.append(
            ViewCoverage(
                view_id=view.view_id,
                cell_count=len(selected),
                assigned_event_count=sum(
                    cell.eligible_event_count for cell in selected
                ),
                heuristic_only_cell_count=sum(
                    cell.evidence_classification
                    is EvidenceClassification.HEURISTIC_ONLY
                    for cell in selected
                ),
                not_statistically_eligible_cell_count=sum(
                    cell.evidence_classification
                    is EvidenceClassification.NOT_STATISTICALLY_ELIGIBLE
                    for cell in selected
                ),
            )
        )
    unique_censored = sum(
        label.outcome_class is OutcomeClass.CENSORED for label in extraction.labels
    )
    ineligibility_reasons = Counter(
        record.reason_code for record in extraction.feature_ineligibility
    )
    return BehavioralFingerprintArtifact.create(
        policy_version=policy.policy_version,
        policy_sha256=policy_sha,
        source_extraction_id=_normalized_extraction_id(extraction),
        assignment_source_sha256=source,
        source_dataset_id=extraction.source_dataset_id,
        source_sha256=extraction.source_sha256,
        code_revision=code_revision,
        unique_eligible_event_count=extraction.event_count,
        unique_resolved_label_count=extraction.label_count - unique_censored,
        unique_censored_label_count=unique_censored,
        unassigned_feature_ineligible_count=(
            extraction.feature_ineligibility_count
        ),
        feature_ineligibility_reasons={
            key: ineligibility_reasons[key]
            for key in sorted(ineligibility_reasons)
        },
        cell_assignment_missing_semantics_count=sum(
            cell.missing_semantics_count for cell in ordered_cells
        ),
        cells=ordered_cells,
        view_coverage=tuple(coverage),
        gate_audit=(
            FingerprintGateAudit(
                gate_id="G6_FEATURE_REPRODUCTION",
                status="PASS",
                reason_code="G6_LABEL_FREE_ASSIGNMENT_BYTE_EXACT",
                message=(
                    "Feature-cell assignments reproduce exactly after input permutation."
                ),
            ),
            FingerprintGateAudit(
                gate_id="G7_ANALYTICAL_ELIGIBILITY",
                status="NOT_EVALUATED",
                reason_code="G7_DEFERRED_TO_REGIME_AND_ANALOG_VALIDATION",
                message="KAN-15 does not establish downstream analytical eligibility.",
            ),
            FingerprintGateAudit(
                gate_id="G8_STATISTICAL_ELIGIBILITY",
                status="NOT_EVALUATED",
                reason_code="G8_NO_OUT_OF_SAMPLE_OR_PURGED_VALIDATION",
                message="Descriptive in-sample cells are not statistical validation.",
            ),
            FingerprintGateAudit(
                gate_id="G9_EXECUTION_BACKTEST_ELIGIBILITY",
                status="NOT_EVALUATED",
                reason_code="G9_NO_EXECUTION_OR_BACKTEST_POLICY",
                message="Execution and backtest eligibility are outside KAN-15.",
            ),
        ),
        prohibited_outputs=(
            "CALIBRATED_PROBABILITY",
            "EXPECTED_RETURN",
            "TRADE_DIRECTION",
            "ENTRY",
            "INVALIDATION",
            "TARGET",
            "PROFITABILITY",
            "LIVE_READINESS",
        ),
        limitations=policy.limitations,
    )


__all__ = ["build_behavioral_fingerprint"]
