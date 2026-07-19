"""Deterministic synthetic fixture artifact for KAN-13 contracts and labels."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import Field

from pipelines.historical_labeling.contracts import (
    AsOfFeatureSnapshot,
    CensorReason,
    CensoringRecord,
    EventDirection,
    FrozenContract,
    HistoricalOutcomeLabel,
    LineageRecord,
    MarketEventIdentity,
    OutcomeClass,
    SCHEMA_VERSION,
    canonical_hash,
)
from pipelines.historical_labeling.fixtures import (
    synthetic_censor_frame,
    synthetic_event,
    synthetic_outcome_frame,
    synthetic_snapshot,
)
from pipelines.historical_labeling.labels import label_historical_outcome
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


class HistoricalLabelingFixtureArtifact(FrozenContract):
    artifact_id: str = "KAN-13-market-event-labeling-fixture"
    jira_key: str = "KAN-13"
    schema_version: str = SCHEMA_VERSION
    fixture_scope: str = "SYNTHETIC_ONLY"
    policy_bundle_version: str
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_evidence: tuple[SchemaEvidence, ...]
    fixture_results: tuple[FixtureResult, ...]
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
        kwargs = {}
        if reason is CensorReason.FAILED_ELIGIBILITY:
            kwargs["source_eligible"] = False
        elif reason is CensorReason.UNAVAILABLE_CALENDAR_SEMANTICS:
            kwargs["calendar_semantics_available"] = False
        elif reason is CensorReason.OTHER:
            kwargs["upstream_censor_reason"] = CensorReason.OTHER
        labeled = label_historical_outcome(
            frame,
            event,
            snapshot,
            label_policy=policy.labels,
            session_policy=policy.session,
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

    return HistoricalLabelingFixtureArtifact(
        policy_bundle_version=policy.bundle_version,
        policy_sha256=policy.policy_sha256(),
        schema_evidence=_schema_evidence(),
        fixture_results=tuple(sorted(results, key=lambda result: result.fixture_id)),
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
    "HistoricalLabelingFixtureArtifact",
    "SchemaEvidence",
    "build_fixture_artifact",
]
