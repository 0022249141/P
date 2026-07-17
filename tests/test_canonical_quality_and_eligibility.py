from __future__ import annotations

import copy

import pandas as pd

from core.dataset_manifest import MANIFEST_SCHEMA_VERSION, PARSER_SCHEMA_VERSION, RECORD_KEYS
from pipelines.canonical import (
    CalendarBehavior,
    CalendarPolicy,
    CanonicalizationPolicy,
    DatasetIdentity,
    EligibilityRequirement,
    EvidenceStatus,
    GapPolicy,
    GateId,
    GateReport,
    GateStatus,
    PeriodSemantics,
    TimestampSemantics,
    evaluate_eligibility,
    evaluate_quality,
    execute_if_eligible,
)


SOURCE_SHA = "a" * 64


def _bars(timestamps: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0 + index for index in range(len(timestamps))],
            "high": [102.0 + index for index in range(len(timestamps))],
            "low": [99.0 + index for index in range(len(timestamps))],
            "close": [101.0 + index for index in range(len(timestamps))],
            "volume": [10.0 + index for index in range(len(timestamps))],
        }
    )


def _identity() -> DatasetIdentity:
    return DatasetIdentity(
        dataset_id="synthetic-m1",
        path="fixtures/synthetic-m1.csv",
        source_sha256=SOURCE_SHA,
        byte_size=123,
        parser_decision="IN_MEMORY_DATAFRAME",
        parser_schema_version=PARSER_SCHEMA_VERSION,
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
    )


def _manifest() -> dict[str, object]:
    record = {key: "evidence" for key in RECORD_KEYS}
    record.update(
        {
            "path": "fixtures/synthetic-m1.csv",
            "sha256": SOURCE_SHA,
            "bytes": 123,
            "parser_schema_version": PARSER_SCHEMA_VERSION,
            "parser_decision": {
                "value": "IN_MEMORY_DATAFRAME",
                "evidence_status": "DECLARED",
            },
        }
    )
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "datasets": [record],
    }


def _policy(*, gap_policy: GapPolicy = GapPolicy.REJECT) -> CanonicalizationPolicy:
    return CanonicalizationPolicy(
        timestamp=TimestampSemantics(
            timezone="UTC",
            timezone_evidence=EvidenceStatus.DECLARED,
            period_semantics=PeriodSemantics.PERIOD_START,
            period_evidence=EvidenceStatus.DECLARED,
        ),
        gap_policy=gap_policy,
        calendar=CalendarPolicy(
            policy_version="continuous-utc-v1",
            behavior=CalendarBehavior.CONTINUOUS,
            expected_interval_seconds=60,
        ),
    )


def _session_policy(
    session_start: str,
    session_end: str,
    *,
    timezone: str = "UTC",
) -> CanonicalizationPolicy:
    base = _policy()
    return CanonicalizationPolicy(
        timestamp=base.timestamp,
        calendar=CalendarPolicy(
            policy_version="explicit-daily-session-v1",
            behavior=CalendarBehavior.VERSIONED_SESSION,
            expected_interval_seconds=60,
            timezone=timezone,
            session_start=session_start,
            session_end=session_end,
        ),
    )


def _evaluation(timestamps: list[str] | None = None):
    values = timestamps if timestamps is not None else [
        "2024-01-01T00:00:00Z",
        "2024-01-01T00:01:00Z",
        "2024-01-01T00:02:00Z",
    ]
    return evaluate_quality(
        _bars(values),
        dataset=_identity(),
        policy=_policy(),
        manifest=_manifest(),
    )


def test_g0_to_g4_pass_with_complete_explicit_evidence() -> None:
    evaluation = _evaluation()
    by_gate = {result.gate_id: result for result in evaluation.report.results}

    for gate_id in (
        GateId.G0_PROVENANCE,
        GateId.G1_SCHEMA_PARSING,
        GateId.G2_TEMPORAL_INTEGRITY,
        GateId.G3_OHLC_NUMERIC,
        GateId.G4_CALENDAR_COVERAGE,
    ):
        assert by_gate[gate_id].status is GateStatus.PASS
    for gate_id in (
        GateId.G6_FEATURE_REPRODUCTION,
        GateId.G7_ANALYTICAL_ELIGIBILITY,
        GateId.G8_STATISTICAL_ELIGIBILITY,
        GateId.G9_EXECUTION_BACKTEST_ELIGIBILITY,
    ):
        assert by_gate[gate_id].status is GateStatus.NOT_EVALUATED


def test_empty_quality_input_blocks_g1_to_g4_and_downstream_callback() -> None:
    evaluation = _evaluation([])
    by_gate = {result.gate_id: result for result in evaluation.report.results}

    assert by_gate[GateId.G1_SCHEMA_PARSING].status is GateStatus.FAIL
    for gate_id in (
        GateId.G2_TEMPORAL_INTEGRITY,
        GateId.G3_OHLC_NUMERIC,
        GateId.G4_CALENDAR_COVERAGE,
    ):
        assert by_gate[gate_id].status is GateStatus.BLOCKED

    called = False

    def downstream() -> str:
        nonlocal called
        called = True
        return "should-not-run"

    guarded = execute_if_eligible(
        evaluation.report,
        EligibilityRequirement(
            profile="provenance-only-still-requires-data",
            required_gates=(GateId.G0_PROVENANCE,),
        ),
        downstream,
    )

    assert guarded.decision.eligible is False
    assert guarded.decision.blocking_gates[0].reason_code == "EMPTY_DATASET"
    assert guarded.output is None
    assert called is False


def test_g0_fails_for_duplicate_or_mismatched_manifest_evidence() -> None:
    manifest = _manifest()
    duplicate = copy.deepcopy(manifest["datasets"][0])
    manifest["datasets"].append(duplicate)

    duplicate_evaluation = evaluate_quality(
        _bars(["2024-01-01T00:00:00Z"]),
        dataset=_identity(),
        policy=_policy(),
        manifest=manifest,
    )
    duplicate_g0 = duplicate_evaluation.report.results[0]
    assert duplicate_g0.status is GateStatus.FAIL
    assert duplicate_g0.findings[0].reason_code == "MANIFEST_RECORD_DUPLICATE"

    mismatch_manifest = _manifest()
    mismatch_manifest["datasets"][0]["sha256"] = "b" * 64
    mismatch = evaluate_quality(
        _bars(["2024-01-01T00:00:00Z"]),
        dataset=_identity(),
        policy=_policy(),
        manifest=mismatch_manifest,
    ).report.results[0]
    assert mismatch.status is GateStatus.FAIL
    assert "PROVENANCE_VALUE_MISMATCH" in {finding.reason_code for finding in mismatch.findings}


def test_g0_blocks_when_manifest_evidence_is_missing() -> None:
    evaluation = evaluate_quality(
        _bars(["2024-01-01T00:00:00Z"]),
        dataset=_identity(),
        policy=_policy(),
        manifest=None,
    )

    assert evaluation.report.results[0].status is GateStatus.BLOCKED


def test_g0_compares_dataset_manifest_schema_evidence() -> None:
    identity = _identity().model_copy(update={"manifest_schema_version": "0.0.0"})

    result = evaluate_quality(
        _bars(["2024-01-01T00:00:00Z"]),
        dataset=identity,
        policy=_policy(),
        manifest=_manifest(),
    ).report.results[0]

    assert result.status is GateStatus.FAIL
    assert "DATASET_MANIFEST_VERSION_MISMATCH" in {
        finding.reason_code for finding in result.findings
    }


def test_g4_blocks_without_explicit_calendar_policy() -> None:
    base = _policy()
    policy = CanonicalizationPolicy(timestamp=base.timestamp)

    result = evaluate_quality(
        _bars(["2024-01-01T00:00:00Z"]),
        dataset=_identity(),
        policy=policy,
        manifest=_manifest(),
    ).report.results[4]

    assert result.status is GateStatus.BLOCKED
    assert result.reason_code == "G4_CALENDAR_POLICY_MISSING"


def test_g4_reports_missing_and_irregular_intervals() -> None:
    missing = _evaluation(
        ["2024-01-01T00:00:00Z", "2024-01-01T00:02:00Z"]
    ).report.results[4]
    irregular = _evaluation(
        ["2024-01-01T00:00:00Z", "2024-01-01T00:01:30Z"]
    ).report.results[4]

    assert missing.status is GateStatus.FAIL
    assert "MISSING_INTERVALS" in {finding.reason_code for finding in missing.findings}
    assert irregular.status is GateStatus.FAIL
    assert "IRREGULAR_INTERVALS" in {finding.reason_code for finding in irregular.findings}


def test_nonreject_gap_policy_reports_without_silent_repair() -> None:
    evaluation = evaluate_quality(
        _bars(["2024-01-01T00:00:00Z", "2024-01-01T00:02:00Z"]),
        dataset=_identity(),
        policy=_policy(gap_policy=GapPolicy.REPORT),
        manifest=_manifest(),
    )

    g4 = evaluation.report.results[4]
    assert g4.status is GateStatus.PASS
    assert g4.reason_code == "G4_DIAGNOSTICS_REPORTED"
    assert len(evaluation.canonicalization.frame) == 2


def test_two_consecutive_daily_sessions_do_not_report_scheduled_closure_as_gap() -> None:
    evaluation = evaluate_quality(
        _bars(
            [
                "2024-01-01T09:00:00Z",
                "2024-01-01T09:01:00Z",
                "2024-01-02T09:00:00Z",
                "2024-01-02T09:01:00Z",
            ]
        ),
        dataset=_identity(),
        policy=_session_policy("09:00:00", "10:00:00"),
        manifest=_manifest(),
    )

    g4 = evaluation.report.results[4]
    assert g4.status is GateStatus.PASS
    assert "MISSING_INTERVALS" not in {finding.reason_code for finding in g4.findings}


def test_overnight_session_anchors_ignore_daytime_closure() -> None:
    evaluation = evaluate_quality(
        _bars(
            [
                "2024-01-02T01:59:00Z",
                "2024-01-02T02:00:00Z",
                "2024-01-02T22:00:00Z",
                "2024-01-02T22:01:00Z",
            ]
        ),
        dataset=_identity(),
        policy=_session_policy("22:00:00", "02:00:00"),
        manifest=_manifest(),
    )

    g4 = evaluation.report.results[4]
    assert g4.status is GateStatus.PASS
    assert "MISSING_INTERVALS" not in {finding.reason_code for finding in g4.findings}


def test_within_session_missing_bar_still_fails_g4() -> None:
    evaluation = evaluate_quality(
        _bars(["2024-01-01T09:00:00Z", "2024-01-01T09:02:00Z"]),
        dataset=_identity(),
        policy=_session_policy("09:00:00", "10:00:00"),
        manifest=_manifest(),
    )

    g4 = evaluation.report.results[4]
    assert g4.status is GateStatus.FAIL
    assert "MISSING_INTERVALS" in {finding.reason_code for finding in g4.findings}


def test_versioned_session_flags_out_of_session_bars() -> None:
    evaluation = evaluate_quality(
        _bars(["2024-01-01T08:00:00Z"]),
        dataset=_identity(),
        policy=_session_policy("09:00:00", "10:00:00"),
        manifest=_manifest(),
    )

    g4 = evaluation.report.results[4]
    assert g4.status is GateStatus.FAIL
    assert "OUT_OF_SESSION_BARS" in {finding.reason_code for finding in g4.findings}


def test_versioned_session_discloses_missing_holiday_and_trading_day_evidence() -> None:
    evaluation = evaluate_quality(
        _bars(["2024-01-01T09:00:00Z"]),
        dataset=_identity(),
        policy=_session_policy("09:00:00", "10:00:00"),
        manifest=_manifest(),
    )

    g4 = evaluation.report.results[4]
    assert any("trading-day calendar evidence" in limitation for limitation in g4.limitations)


def test_incomplete_final_bar_requires_explicit_coverage_end() -> None:
    base = _policy()
    policy = CanonicalizationPolicy(
        timestamp=base.timestamp,
        calendar=CalendarPolicy(
            policy_version="coverage-v1",
            behavior=CalendarBehavior.CONTINUOUS,
            expected_interval_seconds=60,
            coverage_end_utc=pd.Timestamp("2024-01-01T00:00:30Z").to_pydatetime(),
        ),
    )
    evaluation = evaluate_quality(
        _bars(["2024-01-01T00:00:00Z"]),
        dataset=_identity(),
        policy=policy,
        manifest=_manifest(),
    )

    g4 = evaluation.report.results[4]
    assert g4.status is GateStatus.FAIL
    assert "INCOMPLETE_FINAL_BAR" in {finding.reason_code for finding in g4.findings}


def test_gate_report_serialization_is_byte_identical() -> None:
    first = _evaluation().report.to_json_bytes()
    second = _evaluation().report.to_json_bytes()

    assert first == second
    assert b"username" not in first
    assert b"generated_at" not in first


def test_eligibility_blocks_missing_not_evaluated_and_duplicate_gates() -> None:
    report = _evaluation().report
    base_requirement = EligibilityRequirement(
        profile="canonical-only",
        required_gates=(
            GateId.G0_PROVENANCE,
            GateId.G1_SCHEMA_PARSING,
            GateId.G2_TEMPORAL_INTEGRITY,
            GateId.G3_OHLC_NUMERIC,
            GateId.G4_CALENDAR_COVERAGE,
        ),
    )
    assert evaluate_eligibility(report, base_requirement).eligible is True

    not_evaluated = evaluate_eligibility(
        report,
        EligibilityRequirement(
            profile="feature-required",
            required_gates=(GateId.G6_FEATURE_REPRODUCTION,),
        ),
    )
    assert not_evaluated.eligible is False
    assert not_evaluated.blocking_gates[0].status is GateStatus.NOT_EVALUATED

    missing_report = GateReport(dataset=report.dataset, results=report.results[:2])
    missing = evaluate_eligibility(
        missing_report,
        EligibilityRequirement(
            profile="missing-gate",
            required_gates=(GateId.G2_TEMPORAL_INTEGRITY,),
        ),
    )
    assert missing.blocking_gates[0].reason_code == "MISSING_GATE_RESULT"

    duplicate_report = GateReport(
        dataset=report.dataset,
        results=(report.results[0], report.results[0]),
    )
    duplicate = evaluate_eligibility(
        duplicate_report,
        EligibilityRequirement(
            profile="duplicate-gate",
            required_gates=(GateId.G0_PROVENANCE,),
        ),
    )
    assert duplicate.blocking_gates[0].reason_code == "DUPLICATE_GATE_RESULT"


def test_failed_gate_prevents_downstream_callback_invocation() -> None:
    called = False

    def downstream() -> str:
        nonlocal called
        called = True
        return "should-not-run"

    guarded = execute_if_eligible(
        _evaluation().report,
        EligibilityRequirement(
            profile="requires-g6",
            required_gates=(GateId.G6_FEATURE_REPRODUCTION,),
        ),
        downstream,
    )

    assert guarded.decision.eligible is False
    assert guarded.output is None
    assert called is False
