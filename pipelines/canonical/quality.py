"""Composition of provenance, canonical, calendar, and placeholder gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from core.dataset_manifest import (
    MANIFEST_SCHEMA_VERSION,
    PARSER_SCHEMA_VERSION,
    RECORD_KEYS,
)

from .contracts import (
    MAX_EXAMPLES,
    CalendarBehavior,
    CanonicalizationPolicy,
    DatasetIdentity,
    GateFinding,
    GateId,
    GateReport,
    GateResult,
    GateStatus,
    GapPolicy,
    PeriodSemantics,
)
from .normalization import CanonicalInput, CanonicalizationResult, canonicalize


@dataclass(frozen=True)
class QualityEvaluation:
    """Canonicalization output paired with a stable G0-G9 report."""

    canonicalization: CanonicalizationResult
    report: GateReport


def evaluate_quality(
    value: pd.DataFrame | CanonicalInput,
    *,
    dataset: DatasetIdentity,
    policy: CanonicalizationPolicy,
    manifest: Mapping[str, Any] | None = None,
    reconciliation_gate: GateResult | None = None,
) -> QualityEvaluation:
    """Evaluate G0-G4 and compose explicit G5-G9 states."""

    normalized = canonicalize(value, policy)
    g0 = evaluate_provenance(dataset, manifest)
    g1, g2, g3 = normalized.gate_results
    g4 = evaluate_calendar_coverage(normalized.frame, policy)
    if reconciliation_gate is None:
        g5 = not_evaluated_gate(
            GateId.G5_MTF_RECONCILIATION,
            "No supplied higher-timeframe bars were provided for reconciliation.",
        )
    elif reconciliation_gate.gate_id is not GateId.G5_MTF_RECONCILIATION:
        raise ValueError("reconciliation_gate must be G5_MTF_RECONCILIATION")
    else:
        g5 = reconciliation_gate
    placeholders = tuple(
        not_evaluated_gate(gate_id, "KAN-10 defines the contract but no evaluator is implemented.")
        for gate_id in (
            GateId.G6_FEATURE_REPRODUCTION,
            GateId.G7_ANALYTICAL_ELIGIBILITY,
            GateId.G8_STATISTICAL_ELIGIBILITY,
            GateId.G9_EXECUTION_BACKTEST_ELIGIBILITY,
        )
    )
    report = GateReport(
        dataset=dataset,
        results=(g0, g1, g2, g3, g4, g5, *placeholders),
        limitations=(
            "G6-G9 are not evaluated in KAN-10.",
            "No analytical, statistical, backtest, or live engine is wired to this report.",
        ),
    )
    return QualityEvaluation(normalized, report)


def evaluate_provenance(
    dataset: DatasetIdentity,
    manifest: Mapping[str, Any] | None,
) -> GateResult:
    """Evaluate G0 against the in-memory KAN-9 manifest contract."""

    findings: list[GateFinding] = []
    missing_identity = [
        field
        for field in (
            "path",
            "source_sha256",
            "byte_size",
            "parser_decision",
            "parser_schema_version",
            "manifest_schema_version",
        )
        if getattr(dataset, field) is None
    ]
    if missing_identity:
        findings.append(
            _finding(
                "PROVENANCE_FIELDS_MISSING",
                "Dataset identity lacks required provenance fields.",
                missing_identity,
            )
        )
    if manifest is None:
        findings.append(
            _finding(
                "MANIFEST_EVIDENCE_UNAVAILABLE",
                "Committed manifest evidence was not supplied.",
                (),
                affected=1,
            )
        )
        return _provenance_result(dataset, findings, GateStatus.BLOCKED)

    if manifest.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        findings.append(
            _finding(
                "MANIFEST_SCHEMA_VERSION_MISMATCH",
                "Manifest schema version does not match the KAN-9 contract.",
                [manifest.get("manifest_schema_version")],
            )
        )
    if manifest.get("parser_schema_version") != PARSER_SCHEMA_VERSION:
        findings.append(
            _finding(
                "MANIFEST_PARSER_VERSION_MISMATCH",
                "Manifest parser version does not match the KAN-9 contract.",
                [manifest.get("parser_schema_version")],
            )
        )
    if (
        dataset.manifest_schema_version is not None
        and dataset.manifest_schema_version != manifest.get("manifest_schema_version")
    ):
        findings.append(
            _finding(
                "DATASET_MANIFEST_VERSION_MISMATCH",
                "Dataset manifest schema evidence does not match the supplied manifest.",
                [dataset.manifest_schema_version, manifest.get("manifest_schema_version")],
            )
        )
    records = manifest.get("datasets")
    if not isinstance(records, list):
        findings.append(
            _finding("MANIFEST_RECORDS_INVALID", "Manifest datasets must be a list.", (), affected=1)
        )
        return _provenance_result(dataset, findings, GateStatus.FAIL)

    matches = [record for record in records if isinstance(record, dict) and record.get("path") == dataset.path]
    if not matches:
        findings.append(
            _finding(
                "MANIFEST_RECORD_MISSING",
                "No manifest record matches the dataset path.",
                [dataset.path],
            )
        )
    elif len(matches) > 1:
        findings.append(
            _finding(
                "MANIFEST_RECORD_DUPLICATE",
                "Multiple manifest records match the dataset path.",
                [dataset.path],
                affected=len(matches),
            )
        )
    else:
        record = matches[0]
        missing_record_fields = sorted(RECORD_KEYS - set(record))
        if missing_record_fields:
            findings.append(
                _finding(
                    "MANIFEST_REQUIRED_FIELDS_MISSING",
                    "Manifest record is incomplete under the KAN-9 contract.",
                    missing_record_fields,
                )
            )
        empty_record_fields = [
            field
            for field in ("path", "sha256", "parser_schema_version", "parser_decision")
            if record.get(field) in (None, "", {})
        ]
        if empty_record_fields:
            findings.append(
                _finding(
                    "MANIFEST_REQUIRED_VALUES_EMPTY",
                    "Manifest record contains empty required provenance values.",
                    empty_record_fields,
                )
            )
        comparisons = (
            ("sha256", dataset.source_sha256, record.get("sha256")),
            ("bytes", dataset.byte_size, record.get("bytes")),
            ("parser_schema_version", dataset.parser_schema_version, record.get("parser_schema_version")),
        )
        for field, supplied, expected in comparisons:
            if supplied is not None and supplied != expected:
                findings.append(
                    _finding(
                        "PROVENANCE_VALUE_MISMATCH",
                        f"Dataset {field} does not match manifest evidence.",
                        [field],
                    )
                )
        parser_decision = record.get("parser_decision")
        manifest_parser = (
            parser_decision.get("value") if isinstance(parser_decision, dict) else parser_decision
        )
        if dataset.parser_decision is not None and dataset.parser_decision != manifest_parser:
            findings.append(
                _finding(
                    "PARSER_DECISION_MISMATCH",
                    "Dataset parser decision does not match manifest evidence.",
                    [dataset.parser_decision, manifest_parser],
                )
            )
    status = GateStatus.BLOCKED if missing_identity else GateStatus.FAIL if findings else GateStatus.PASS
    return _provenance_result(dataset, findings, status)


def evaluate_calendar_coverage(
    frame: pd.DataFrame | None,
    policy: CanonicalizationPolicy,
) -> GateResult:
    """Evaluate explicit interval, coverage, and optional session diagnostics."""

    if frame is None:
        return GateResult(
            gate_id=GateId.G4_CALENDAR_COVERAGE,
            status=GateStatus.BLOCKED,
            reason_code="G4_CANONICAL_DEPENDENCY_BLOCKED",
            message="Calendar checks require valid canonical rows.",
            checked_record_count=0,
            affected_record_count=0,
            limitations=("G1-G3 did not produce canonical UTC rows.",),
            remediation_guidance=("Resolve earlier gate failures before G4 evaluation.",),
        )
    calendar = policy.calendar
    if calendar is None:
        return GateResult(
            gate_id=GateId.G4_CALENDAR_COVERAGE,
            status=GateStatus.BLOCKED,
            reason_code="G4_CALENDAR_POLICY_MISSING",
            message="Expected intervals and calendar behavior require explicit configuration.",
            checked_record_count=len(frame),
            affected_record_count=len(frame),
            limitations=("No interval, calendar version, or session policy was supplied.",),
            remediation_guidance=("Supply a versioned CalendarPolicy.",),
        )

    findings: list[GateFinding] = []
    limitations: list[str] = []
    timestamps = pd.DatetimeIndex(frame["timestamp"])
    expected = calendar.expected_interval_seconds
    epoch_ns = timestamps.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    deltas = np.diff(epoch_ns) / 1_000_000_000 if len(timestamps) > 1 else np.array([])
    duplicate_positions = np.flatnonzero(deltas == 0) + 1
    if len(duplicate_positions):
        findings.append(
            _finding(
                "UNEXPECTED_DUPLICATE_INTERVAL",
                "Duplicate timestamp intervals were detected.",
                duplicate_positions,
            )
        )
    missing_examples: list[str] = []
    missing_count = 0
    irregular_positions: list[int] = []
    for position, delta in enumerate(deltas, start=1):
        if delta == expected:
            continue
        if delta > expected and delta % expected == 0:
            missing_count += int(delta // expected) - 1
            missing_examples.append(
                f"{timestamps[position - 1].isoformat()}->{timestamps[position].isoformat()}"
            )
        elif delta != 0:
            irregular_positions.append(position)
    if missing_count:
        findings.append(
            _finding(
                "MISSING_INTERVALS",
                "Expected timestamp intervals are missing.",
                missing_examples,
                affected=missing_count,
            )
        )
    if irregular_positions:
        findings.append(
            _finding(
                "IRREGULAR_INTERVALS",
                "Observed deltas are not multiples of the expected interval.",
                irregular_positions,
            )
        )

    evidence = [
        f"calendar:{calendar.policy_version}",
        f"coverage-start:{timestamps[0].isoformat()}" if len(timestamps) else "coverage-start:EMPTY",
        f"coverage-end:{timestamps[-1].isoformat()}" if len(timestamps) else "coverage-end:EMPTY",
    ]
    if calendar.behavior is CalendarBehavior.VERSIONED_SESSION:
        try:
            local = timestamps.tz_convert(ZoneInfo(calendar.timezone))
        except ZoneInfoNotFoundError:
            findings.append(
                _finding(
                    "CALENDAR_TIMEZONE_INVALID",
                    "Session calendar timezone is unavailable.",
                    [calendar.timezone],
                )
            )
        else:
            start = time.fromisoformat(calendar.session_start or "00:00:00")
            end = time.fromisoformat(calendar.session_end or "00:00:00")
            out_of_session = [
                index
                for index, timestamp in enumerate(local)
                if not _time_in_session(timestamp.time(), start, end)
            ]
            if out_of_session:
                findings.append(
                    _finding(
                        "OUT_OF_SESSION_BARS",
                        "Bars fall outside the supplied versioned session.",
                        out_of_session,
                    )
                )
    else:
        limitations.append("Continuous calendar declared; exchange/session boundaries were not evaluated.")

    if calendar.coverage_end_utc is not None and len(timestamps):
        coverage_end = pd.Timestamp(calendar.coverage_end_utc).tz_convert("UTC")
        if policy.timestamp.period_semantics is PeriodSemantics.PERIOD_START:
            expected_end = timestamps[-1] + timedelta(seconds=expected)
            incomplete = expected_end > coverage_end
        else:
            incomplete = timestamps[-1] > coverage_end
        if incomplete:
            findings.append(
                _finding(
                    "INCOMPLETE_FINAL_BAR",
                    "Final bar is incomplete relative to declared coverage end.",
                    [timestamps[-1].isoformat()],
                )
            )
    else:
        limitations.append("Incomplete final bar was not evaluated without coverage_end_utc.")

    hard_failure_codes = {
        "UNEXPECTED_DUPLICATE_INTERVAL",
        "OUT_OF_SESSION_BARS",
        "CALENDAR_TIMEZONE_INVALID",
        "INCOMPLETE_FINAL_BAR",
    }
    gap_findings = {"MISSING_INTERVALS", "IRREGULAR_INTERVALS"}
    codes = {finding.reason_code for finding in findings}
    hard_failure = bool(codes & hard_failure_codes)
    gap_failure = bool(codes & gap_findings) and policy.gap_policy is GapPolicy.REJECT
    status = GateStatus.FAIL if hard_failure or gap_failure else GateStatus.PASS
    if findings and status is GateStatus.PASS:
        reason = "G4_DIAGNOSTICS_REPORTED"
        message = "Calendar diagnostics were reported under a non-reject gap policy."
    elif findings:
        reason = "G4_CALENDAR_COVERAGE_FAILED"
        message = "Calendar, interval, or coverage violations were detected."
    else:
        reason = "G4_CALENDAR_COVERAGE_OK"
        message = "Configured interval and calendar checks passed."
    examples = tuple(example for finding in findings for example in finding.examples)[:MAX_EXAMPLES]
    return GateResult(
        gate_id=GateId.G4_CALENDAR_COVERAGE,
        status=status,
        reason_code=reason,
        message=message,
        checked_record_count=len(frame),
        affected_record_count=sum(finding.affected_record_count for finding in findings),
        examples=examples,
        evidence_references=tuple(evidence),
        limitations=tuple(limitations),
        remediation_guidance=(
            (
                "Correct gaps/session violations or revise only explicitly versioned calendar policy."
                if findings
                else "No remediation required."
            ),
        ),
        findings=tuple(findings),
    )


def not_evaluated_gate(gate_id: GateId, limitation: str) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        status=GateStatus.NOT_EVALUATED,
        reason_code=f"{gate_id.value}_NOT_EVALUATED",
        message="No evaluator result is available.",
        checked_record_count=0,
        affected_record_count=0,
        limitations=(limitation,),
        remediation_guidance=("Provide an approved evaluator and versioned evidence.",),
    )


def _provenance_result(
    dataset: DatasetIdentity,
    findings: list[GateFinding],
    status: GateStatus,
) -> GateResult:
    if status is GateStatus.PASS:
        reason = "G0_PROVENANCE_OK"
        message = "Dataset identity matches one complete manifest record."
    elif status is GateStatus.BLOCKED:
        reason = "G0_PROVENANCE_BLOCKED"
        message = "Required provenance evidence is unavailable."
    else:
        reason = "G0_PROVENANCE_FAILED"
        message = "Provenance evidence is inconsistent or invalid."
    examples = tuple(example for finding in findings for example in finding.examples)[:MAX_EXAMPLES]
    return GateResult(
        gate_id=GateId.G0_PROVENANCE,
        status=status,
        reason_code=reason,
        message=message,
        checked_record_count=1,
        affected_record_count=sum(finding.affected_record_count for finding in findings),
        examples=examples,
        evidence_references=(f"dataset:{dataset.dataset_id}",),
        limitations=() if status is GateStatus.PASS else ("G0 does not open source files.",),
        remediation_guidance=(
            (
                "Supply one complete matching KAN-9 manifest record and identity evidence."
                if findings
                else "No remediation required."
            ),
        ),
        findings=tuple(findings),
    )


def _finding(
    reason_code: str,
    message: str,
    examples: Iterable[object],
    *,
    affected: int | None = None,
) -> GateFinding:
    stable = tuple(str(example) for example in examples)
    return GateFinding(
        reason_code=reason_code,
        message=message,
        affected_record_count=len(stable) if affected is None else affected,
        examples=stable[:MAX_EXAMPLES],
    )


def _time_in_session(value: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= value <= end
    return value >= start or value <= end
