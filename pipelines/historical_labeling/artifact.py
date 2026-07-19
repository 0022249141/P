"""Deterministic synthetic fixture artifact for KAN-13 contracts and labels."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field

from pipelines.canonical import ReconciliationTolerance
from pipelines.historical_labeling.contracts import (
    AsOfFeatureSnapshot,
    CalendarSemanticsEvidence,
    CensorReason,
    CensoringRecord,
    EventDirection,
    EligibilityEvidenceState,
    FrozenContract,
    HistoricalExtractionResult,
    HistoricalOutcomeLabel,
    LabelingEvidence,
    LineageRecord,
    MarketEventIdentity,
    OutcomeClass,
    SCHEMA_VERSION,
    canonical_hash,
)
from pipelines.historical_labeling.fixtures import (
    synthetic_censor_frame,
    synthetic_calendar_evidence,
    synthetic_canonical_policy,
    synthetic_eligible_m1_frame,
    synthetic_eligible_m5_frame,
    synthetic_eligible_manifest,
    synthetic_eligible_policy,
    synthetic_event,
    synthetic_labeling_evidence,
    synthetic_outcome_frame,
    synthetic_resampling_policy,
    synthetic_snapshot,
)
from pipelines.historical_labeling.labels import label_historical_outcome
from pipelines.historical_labeling.pilot import run_gated_pilot
from pipelines.historical_labeling.policies import ResearchPolicyBundle


class SchemaEvidence(FrozenContract):
    contract_name: str = Field(min_length=1)
    json_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FixtureResult(FrozenContract):
    fixture_id: str = Field(min_length=1)
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    direction: EventDirection
    expected_outcome: OutcomeClass
    observed_outcome: OutcomeClass
    expected_censor_reason: CensorReason | None = None
    observed_censor_reason: CensorReason | None = None
    event_id: str = Field(pattern=r"^evt_[0-9a-f]{64}$")


class EligibleExtractionEvidence(FrozenContract):
    extraction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_count: int = Field(gt=0)
    feature_count: int = Field(gt=0)
    label_count: int = Field(gt=0)
    censoring_count: int = Field(ge=0)
    gate_statuses: tuple[str, ...]
    outcome_classes: tuple[OutcomeClass, ...]


class HistoricalLabelingFixtureArtifact(FrozenContract):
    artifact_id: str = "KAN-13-market-event-labeling-fixture"
    jira_key: str = "KAN-13"
    schema_version: str = SCHEMA_VERSION
    fixture_scope: str = "SYNTHETIC_ONLY"
    policy_bundle_version: str
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_evidence: tuple[SchemaEvidence, ...]
    fixture_results: tuple[FixtureResult, ...]
    eligible_extraction: EligibleExtractionEvidence
    limitations: tuple[str, ...] = Field(min_length=1)


def _frame_hash(frame) -> str:
    records = []
    for row in frame.itertuples(index=False):
        records.append(
            {
                "timestamp": row.timestamp.isoformat().replace("+00:00", "Z"),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
            }
        )
    return canonical_hash({"records": records})


def _schema_evidence() -> tuple[SchemaEvidence, ...]:
    contracts = (
        MarketEventIdentity,
        AsOfFeatureSnapshot,
        HistoricalOutcomeLabel,
        CensoringRecord,
        LineageRecord,
        HistoricalExtractionResult,
        LabelingEvidence,
        CalendarSemanticsEvidence,
    )
    return tuple(
        SchemaEvidence(
            contract_name=contract.__name__,
            json_schema_sha256=canonical_hash(contract.model_json_schema()),
        )
        for contract in contracts
    )


def build_fixture_artifact(
    policy: ResearchPolicyBundle,
    repository_root: Path,
) -> HistoricalLabelingFixtureArtifact:
    results: list[FixtureResult] = []
    resolved = (
        OutcomeClass.DIRECT_CONTINUATION,
        OutcomeClass.SWEEP_PULLBACK_CONTINUATION,
        OutcomeClass.FALSE_BREAK_REENTRY,
        OutcomeClass.ACCEPTANCE_THEN_EXPANSION,
        OutcomeClass.FULL_RANGE_REVERSAL,
        OutcomeClass.NO_RESOLUTION,
    )
    for direction in EventDirection:
        for outcome in resolved:
            event = synthetic_event(policy, direction)
            snapshot = synthetic_snapshot(policy, event)
            frame = synthetic_outcome_frame(event, outcome)
            labeled = label_historical_outcome(
                frame,
                event,
                snapshot,
                label_policy=policy.labels,
                session_policy=policy.session,
                evidence=synthetic_labeling_evidence(),
            )
            results.append(
                FixtureResult(
                    fixture_id=f"{direction.value.lower()}-{outcome.value.lower()}-v1",
                    fixture_sha256=_frame_hash(frame),
                    direction=direction,
                    expected_outcome=outcome,
                    observed_outcome=labeled.label.outcome_class,
                    event_id=event.event_id,
                )
            )

    for reason in CensorReason:
        cutoff = None
        if reason is CensorReason.SESSION_BOUNDARY:
            cutoff = datetime(2025, 1, 6, 18, 25, tzinfo=timezone.utc)
        event = synthetic_event(policy, EventDirection.ABOVE, cutoff=cutoff)
        snapshot = synthetic_snapshot(policy, event)
        if reason is CensorReason.SESSION_BOUNDARY:
            frame = synthetic_outcome_frame(event, OutcomeClass.NO_RESOLUTION)
        else:
            frame = synthetic_censor_frame(event, reason)
        evidence = synthetic_labeling_evidence()
        kwargs = {}
        if reason is CensorReason.FAILED_ELIGIBILITY:
            evidence = synthetic_labeling_evidence(
                source_status=EligibilityEvidenceState.BLOCKED
            )
        elif reason is CensorReason.UNAVAILABLE_CALENDAR_SEMANTICS:
            evidence = synthetic_labeling_evidence(
                calendar_status=EligibilityEvidenceState.NOT_EVALUATED
            )
        elif reason is CensorReason.OTHER:
            kwargs["upstream_censor_reason"] = CensorReason.OTHER
        labeled = label_historical_outcome(
            frame,
            event,
            snapshot,
            label_policy=policy.labels,
            session_policy=policy.session,
            evidence=evidence,
            **kwargs,
        )
        observed_reason = (
            None if labeled.censoring is None else labeled.censoring.primary_reason
        )
        results.append(
            FixtureResult(
                fixture_id=f"censor-{reason.value.lower()}-v1",
                fixture_sha256=_frame_hash(frame),
                direction=EventDirection.ABOVE,
                expected_outcome=OutcomeClass.CENSORED,
                observed_outcome=labeled.label.outcome_class,
                expected_censor_reason=reason,
                observed_censor_reason=observed_reason,
                event_id=event.event_id,
            )
        )

    eligible_policy = synthetic_eligible_policy(policy)
    manifest, manifest_record = synthetic_eligible_manifest(eligible_policy)
    extraction = run_gated_pilot(
        synthetic_eligible_m1_frame(),
        reconciliation_table=synthetic_eligible_m5_frame(),
        manifest=manifest,
        manifest_record=manifest_record,
        policy=eligible_policy,
        canonical_policy=synthetic_canonical_policy(),
        resampling_policy=synthetic_resampling_policy(),
        reconciliation_tolerance=ReconciliationTolerance(),
        repository_root=repository_root,
        calendar_evidence=synthetic_calendar_evidence(),
    )
    if extraction.eligible_output is None:
        raise AssertionError("synthetic eligible extraction did not execute")
    extracted = extraction.eligible_output

    return HistoricalLabelingFixtureArtifact(
        policy_bundle_version=policy.bundle_version,
        policy_sha256=policy.policy_sha256(),
        schema_evidence=_schema_evidence(),
        fixture_results=tuple(sorted(results, key=lambda result: result.fixture_id)),
        eligible_extraction=EligibleExtractionEvidence(
            extraction_sha256=hashlib.sha256(extracted.to_json_bytes()).hexdigest(),
            event_count=extracted.event_count,
            feature_count=extracted.feature_count,
            label_count=extracted.label_count,
            censoring_count=extracted.censoring_count,
            gate_statuses=tuple(
                f"{gate.gate_id}:{gate.status}" for gate in extracted.gate_audit
            ),
            outcome_classes=tuple(label.outcome_class for label in extracted.labels),
        ),
        limitations=(
            "Fixtures prove deterministic policy implementation, not market validity.",
            "Thresholds are provisional research parameters and are not optimized.",
            "Herat and XAUUSD are NOT_EVALUATED.",
            "G6-G9 remain NOT_EVALUATED.",
            "No probability, model, entry, invalidation, target, or trading decision is emitted.",
        ),
    )


__all__ = [
    "FixtureResult",
    "EligibleExtractionEvidence",
    "HistoricalLabelingFixtureArtifact",
    "SchemaEvidence",
    "build_fixture_artifact",
]
