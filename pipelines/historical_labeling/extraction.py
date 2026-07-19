"""Deterministic eligible historical extraction after KAN-10 G0-G5 pass."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipelines.historical_labeling.contracts import (
    CalendarSemanticsEvidence,
    EligibilityEvidenceState,
    GateAudit,
    HistoricalExtractionResult,
    LabelingEvidence,
)
from pipelines.historical_labeling.event_source import generate_confirmed_swing_events
from pipelines.historical_labeling.features import build_asof_feature_snapshot
from pipelines.historical_labeling.labels import label_historical_outcome
from pipelines.historical_labeling.policies import ResearchPolicyBundle


def extract_eligible_historical(
    event_frame: pd.DataFrame,
    *,
    repository_root: Path,
    policy: ResearchPolicyBundle,
    source_sha256: str,
    gate_audit: tuple[GateAudit, ...],
    eligibility_profile: str,
    calendar_evidence: CalendarSemanticsEvidence,
) -> HistoricalExtractionResult:
    """Execute the swing, feature, and bounded-label path on eligible M5 bars."""

    labeling_evidence = LabelingEvidence(
        source_status=EligibilityEvidenceState.PASS,
        source_profile=eligibility_profile,
        source_reason_code="KAN10_G0_G5_PASS",
        calendar_status=calendar_evidence.status,
        calendar_policy_version=calendar_evidence.policy_version,
        calendar_reason_code=calendar_evidence.reason_code,
    )
    events = generate_confirmed_swing_events(
        event_frame,
        repository_root=repository_root,
        policy=policy.event_source,
        market=policy.dataset.market,
        symbol=policy.dataset.symbol,
        timeframe=policy.dataset.event_timeframe,
        source_timeframe=policy.dataset.source_timeframe,
        source_dataset_id=policy.dataset.dataset_id,
        source_sha256=source_sha256,
    )
    features = []
    labels = []
    censoring = []
    for event in events:
        snapshot = build_asof_feature_snapshot(
            event_frame,
            event,
            feature_policy=policy.features,
            session_policy=policy.session,
        )
        labeled = label_historical_outcome(
            event_frame,
            event,
            snapshot,
            label_policy=policy.labels,
            session_policy=policy.session,
            evidence=labeling_evidence,
        )
        features.append(snapshot)
        labels.append(labeled.label)
        if labeled.censoring is not None:
            censoring.append(labeled.censoring)

    return HistoricalExtractionResult.create(
        source_dataset_id=policy.dataset.dataset_id,
        source_sha256=source_sha256,
        policy_bundle_version=policy.bundle_version,
        policy_sha256=policy.policy_sha256(),
        eligibility_profile=eligibility_profile,
        gate_audit=gate_audit,
        labeling_evidence=labeling_evidence,
        events=events,
        features=tuple(features),
        labels=tuple(labels),
        censoring=tuple(censoring),
        catalog_generated=True,
    )


__all__ = ["extract_eligible_historical"]
