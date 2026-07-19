"""KAN-10 G0-G5-gated historical extraction and compact audit evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from core.dataset_manifest import MANIFEST_SCHEMA_VERSION, PARSER_SCHEMA_VERSION
from pipelines.canonical import (
    CanonicalInput,
    CanonicalizationPolicy,
    DatasetIdentity,
    EligibilityRequirement,
    GateId,
    GateReport,
    GateResult,
    GateStatus,
    ReconciliationTolerance,
    ResamplingPolicy,
    evaluate_eligibility,
    evaluate_quality,
    execute_if_eligible,
    reconcile_bars,
    resample_bars,
)
from pipelines.historical_labeling.contracts import (
    BlockedPilotAuditSummary,
    CalendarSemanticsEvidence,
    GateAudit,
    HistoricalExtractionResult,
    PilotStatus,
)
from pipelines.historical_labeling.extraction import extract_eligible_historical
from pipelines.historical_labeling.policies import ResearchPolicyBundle


SOURCE_PROFILE = "KAN13_HISTORICAL_SOURCE_G0_G5_V1"
PRE_RECONCILIATION_PROFILE = "KAN13_PRE_RECONCILIATION_G0_G4_V1"


@dataclass(frozen=True)
class PilotExecution:
    summary: BlockedPilotAuditSummary
    eligible_output: HistoricalExtractionResult | None


def _gate_audit(result: Any) -> GateAudit:
    return GateAudit(
        gate_id=result.gate_id.value,
        status=result.status.value,
        reason_code=result.reason_code,
        message=result.message,
        findings=tuple(finding.reason_code for finding in result.findings),
        limitations=tuple(result.limitations),
    )


def _with_reconciliation(report: GateReport, gate: GateResult) -> GateReport:
    results = tuple(
        gate if result.gate_id is GateId.G5_MTF_RECONCILIATION else result
        for result in report.results
    )
    return GateReport(
        dataset=report.dataset,
        results=results,
        report_schema_version=report.report_schema_version,
        evaluator_version=report.evaluator_version,
        limitations=report.limitations,
    )


def _status_for(gate_audit: tuple[GateAudit, ...], eligible: bool) -> PilotStatus:
    if eligible:
        return PilotStatus.ELIGIBLE
    by_gate = {gate.gate_id: gate.status for gate in gate_audit}
    g0_g4_pass = all(
        by_gate.get(gate.value) == GateStatus.PASS.value
        for gate in (
            GateId.G0_PROVENANCE,
            GateId.G1_SCHEMA_PARSING,
            GateId.G2_TEMPORAL_INTEGRITY,
            GateId.G3_OHLC_NUMERIC,
            GateId.G4_CALENDAR_COVERAGE,
        )
    )
    if g0_g4_pass:
        return PilotStatus.BLOCKED_BY_RECONCILIATION
    if by_gate.get(GateId.G2_TEMPORAL_INTEGRITY.value) == GateStatus.BLOCKED.value:
        return PilotStatus.BLOCKED_BY_SOURCE_SEMANTICS
    return PilotStatus.BLOCKED_BY_CANONICAL_GATES


def run_gated_pilot(
    table: pd.DataFrame,
    *,
    reconciliation_table: pd.DataFrame | None,
    manifest: Mapping[str, Any],
    manifest_record: Mapping[str, Any],
    policy: ResearchPolicyBundle,
    canonical_policy: CanonicalizationPolicy,
    resampling_policy: ResamplingPolicy | None,
    reconciliation_tolerance: ReconciliationTolerance,
    repository_root: Path,
    calendar_evidence: CalendarSemanticsEvidence,
) -> PilotExecution:
    """Execute analytics only after canonical G0-G5 all pass."""

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
    evaluation = evaluate_quality(
        CanonicalInput(table, parser_decision=parser_decision),
        dataset=identity,
        policy=canonical_policy,
        manifest=manifest,
    )
    pre_requirement = EligibilityRequirement(
        profile=PRE_RECONCILIATION_PROFILE,
        required_gates=(
            GateId.G0_PROVENANCE,
            GateId.G1_SCHEMA_PARSING,
            GateId.G2_TEMPORAL_INTEGRITY,
            GateId.G3_OHLC_NUMERIC,
            GateId.G4_CALENDAR_COVERAGE,
        ),
    )
    pre_decision = evaluate_eligibility(evaluation.report, pre_requirement)
    generated_m5: pd.DataFrame | None = None
    final_report = evaluation.report
    if (
        pre_decision.eligible
        and resampling_policy is not None
        and reconciliation_table is not None
    ):
        if evaluation.canonicalization.frame is None:
            raise ValueError("eligible canonical report did not provide canonical rows")
        generated_m5 = resample_bars(
            evaluation.canonicalization.frame,
            resampling_policy,
        ).frame
        reconciliation = reconcile_bars(
            generated_m5,
            reconciliation_table,
            reconciliation_tolerance,
        )
        final_report = _with_reconciliation(
            evaluation.report,
            reconciliation.gate_result,
        )

    requirement = EligibilityRequirement(
        profile=SOURCE_PROFILE,
        required_gates=(
            GateId.G0_PROVENANCE,
            GateId.G1_SCHEMA_PARSING,
            GateId.G2_TEMPORAL_INTEGRITY,
            GateId.G3_OHLC_NUMERIC,
            GateId.G4_CALENDAR_COVERAGE,
            GateId.G5_MTF_RECONCILIATION,
        ),
    )
    gate_audit = tuple(_gate_audit(result) for result in final_report.results)

    def run_extraction() -> HistoricalExtractionResult:
        if generated_m5 is None:
            raise AssertionError("G5 PASS requires generated M5 evidence")
        return extract_eligible_historical(
            generated_m5,
            repository_root=repository_root,
            policy=policy,
            source_sha256=str(manifest_record["sha256"]),
            gate_audit=gate_audit,
            eligibility_profile=SOURCE_PROFILE,
            calendar_evidence=calendar_evidence,
        )

    guarded = execute_if_eligible(final_report, requirement, run_extraction)
    output = guarded.output
    status = _status_for(gate_audit, guarded.decision.eligible)
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
    if status is PilotStatus.BLOCKED_BY_SOURCE_SEMANTICS:
        unresolved = (
            "source timezone evidence is UNKNOWN in the committed manifest",
            "source timestamp-period semantics are UNKNOWN in the committed manifest",
            "holiday and trading-day completeness lacks an authoritative calendar",
            "requested Asia/Tehran PERIOD_START semantics remain HYPOTHESIS",
        )
        limitations = (
            "KAN-10 G2 and G4 block the selected source.",
            "No historical engine, feature, or label execution occurred.",
            "The pilot demonstrates the acceptance boundary, not statistical sufficiency.",
            "Behavioral Fingerprint modeling is outside KAN-13.",
        )
    elif status is PilotStatus.ELIGIBLE:
        unresolved = (
            ()
            if calendar_evidence.status.value == "PASS"
            else (f"label calendar evidence:{calendar_evidence.status.value}",)
        )
        limitations = (
            "Eligible extraction is an in-memory deterministic result, not a committed catalog.",
            "G6-G9 remain NOT_EVALUATED.",
        )
    else:
        unresolved = tuple(
            f"{block.gate_id.value}:{block.reason_code}"
            for block in guarded.decision.blocking_gates
        )
        limitations = (
            "No analytical extraction occurred because required canonical gates did not pass.",
            "G6-G9 remain NOT_EVALUATED.",
        )

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
        unresolved_evidence=unresolved,
        catalog_generated=False if output is None else output.catalog_generated,
        eligible_event_count=0 if output is None else output.event_count,
        eligible_feature_count=0 if output is None else output.feature_count,
        eligible_label_count=0 if output is None else output.label_count,
        g6_g9_status=g6_g9,
        limitations=limitations,
    )
    return PilotExecution(summary=summary, eligible_output=output)


__all__ = ["PilotExecution", "run_gated_pilot"]
