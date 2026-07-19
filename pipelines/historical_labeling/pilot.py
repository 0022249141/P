"""KAN-10-gated historical pilot orchestration and compact audit evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Mapping, TypeVar

import pandas as pd

from core.dataset_manifest import MANIFEST_SCHEMA_VERSION, PARSER_SCHEMA_VERSION
from pipelines.canonical import (
    CanonicalInput,
    CanonicalizationPolicy,
    DatasetIdentity,
    EligibilityRequirement,
    GateId,
    execute_if_eligible,
    evaluate_quality,
)
from pipelines.historical_labeling.contracts import (
    BlockedPilotAuditSummary,
    GateAudit,
    PilotStatus,
)
from pipelines.historical_labeling.policies import ResearchPolicyBundle


T = TypeVar("T")


@dataclass(frozen=True)
class PilotExecution(Generic[T]):
    summary: BlockedPilotAuditSummary
    eligible_output: T | None


def _gate_audit(result: Any) -> GateAudit:
    finding_codes = tuple(finding.reason_code for finding in result.findings)
    return GateAudit(
        gate_id=result.gate_id.value,
        status=result.status.value,
        reason_code=result.reason_code,
        message=result.message,
        findings=finding_codes,
        limitations=tuple(result.limitations),
    )


def run_gated_pilot(
    table: pd.DataFrame,
    *,
    manifest: Mapping[str, Any],
    manifest_record: Mapping[str, Any],
    policy: ResearchPolicyBundle,
    on_eligible: Callable[[], T],
) -> PilotExecution[T]:
    """Stop before analytical execution unless KAN-10 G0-G4 all pass."""

    parser = manifest_record["parser_decision"]
    parser_decision = parser["value"] if isinstance(parser, dict) else str(parser)
    identity = DatasetIdentity(
        dataset_id=policy.dataset.dataset_id,
        path=policy.dataset.dataset_path,
        source_sha256=str(manifest_record["sha256"]),
        byte_size=int(manifest_record["bytes"]),
        parser_decision=parser_decision,
        parser_schema_version=str(
            manifest_record.get("parser_schema_version", PARSER_SCHEMA_VERSION)
        ),
        manifest_schema_version=str(
            manifest.get("manifest_schema_version", MANIFEST_SCHEMA_VERSION)
        ),
    )

    # Manifest semantics are deliberately not replaced by the requested hypothesis.
    evaluation = evaluate_quality(
        CanonicalInput(table, parser_decision=parser_decision),
        dataset=identity,
        policy=CanonicalizationPolicy(),
        manifest=manifest,
    )
    requirement = EligibilityRequirement(
        profile="KAN13_HISTORICAL_SOURCE_V1",
        required_gates=(
            GateId.G0_PROVENANCE,
            GateId.G1_SCHEMA_PARSING,
            GateId.G2_TEMPORAL_INTEGRITY,
            GateId.G3_OHLC_NUMERIC,
            GateId.G4_CALENDAR_COVERAGE,
        ),
    )
    guarded = execute_if_eligible(evaluation.report, requirement, on_eligible)
    status = (
        PilotStatus.ELIGIBLE
        if guarded.decision.eligible
        else PilotStatus.BLOCKED_BY_SOURCE_SEMANTICS
    )
    gate_audit = tuple(_gate_audit(result) for result in evaluation.report.results)
    by_gate = {item.gate_id: item for item in gate_audit}
    g6_g9 = {
        gate.value: by_gate[gate.value].status
        for gate in (
            GateId.G6_FEATURE_REPRODUCTION,
            GateId.G7_ANALYTICAL_ELIGIBILITY,
            GateId.G8_STATISTICAL_ELIGIBILITY,
            GateId.G9_EXECUTION_BACKTEST_ELIGIBILITY,
        )
    }
    requested = {
        "bundle_version": policy.bundle_version,
        "calendar_evidence": policy.session.holiday_calendar_status.value,
        "canonical_request_version": policy.dataset.canonical_request_version,
        "diagnostic_timeframe": policy.dataset.diagnostic_timeframe,
        "event_timeframe": policy.dataset.event_timeframe,
        "event_policy_version": policy.event_source.policy_version,
        "feature_policy_version": policy.features.policy_version,
        "label_policy_version": policy.labels.policy_version,
        "policy_sha256": policy.policy_sha256(),
        "reconciliation_path": policy.dataset.reconciliation_path,
        "session": f"{policy.session.session_start}-{policy.session.session_end}",
        "session_policy_version": policy.session.policy_version,
        "source_timeframe": policy.dataset.source_timeframe,
        "timestamp_period_semantics": policy.session.timestamp_period_semantics,
        "timezone": policy.session.timezone,
        "timezone_period_evidence": policy.session.evidence_status.value,
    }
    summary = BlockedPilotAuditSummary(
        status=status,
        dataset_id=policy.dataset.dataset_id,
        dataset_path=policy.dataset.dataset_path,
        source_sha256=str(manifest_record["sha256"]),
        byte_size=int(manifest_record["bytes"]),
        row_count=int(manifest_record["row_count"]),
        coverage_start=str(manifest_record["first_timestamp"]),
        coverage_end=str(manifest_record["last_timestamp"]),
        requested_configuration=requested,
        gate_audit=gate_audit,
        unresolved_evidence=(
            "source timezone evidence is UNKNOWN in the committed manifest",
            "source timestamp-period semantics are UNKNOWN in the committed manifest",
            "holiday and trading-day completeness lacks an authoritative calendar",
            "requested Asia/Tehran PERIOD_START semantics remain HYPOTHESIS",
        ),
        catalog_generated=False,
        eligible_event_count=0,
        eligible_feature_count=0,
        eligible_label_count=0,
        g6_g9_status=g6_g9,
        limitations=(
            "KAN-10 G2 and G4 block the selected source.",
            "No historical engine, feature, or label execution occurred.",
            "The pilot demonstrates the acceptance boundary, not statistical sufficiency.",
            "Behavioral Fingerprint modeling is outside KAN-13.",
        ),
    )
    return PilotExecution(summary=summary, eligible_output=guarded.output)


__all__ = ["PilotExecution", "run_gated_pilot"]
