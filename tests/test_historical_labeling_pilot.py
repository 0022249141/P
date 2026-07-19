from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from core.dataset_manifest import MANIFEST_SCHEMA_VERSION, PARSER_SCHEMA_VERSION, RECORD_KEYS
from pipelines.canonical import (
    CanonicalizationPolicy,
    GateStatus,
    ReconciliationTolerance,
    reconcile_bars,
)
from pipelines.historical_labeling import pilot as pilot_module
from pipelines.historical_labeling.contracts import (
    CalendarSemanticsEvidence,
    EligibilityEvidenceState,
    PilotStatus,
)
from pipelines.historical_labeling.fixtures import (
    synthetic_calendar_evidence,
    synthetic_canonical_policy,
    synthetic_eligible_m1_frame,
    synthetic_eligible_m5_frame,
    synthetic_eligible_manifest,
    synthetic_eligible_policy,
    synthetic_resampling_policy,
)
from pipelines.historical_labeling.pilot import run_gated_pilot
from scripts.run_historical_labeling import main
from tests.historical_labeling_helpers import REPOSITORY_ROOT, policy


def _table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": ["2025-01-01 09:00:00", "2025-01-01 09:01:00"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1.0, 1.0],
        }
    )


def _manifest():
    record = {key: "evidence" for key in RECORD_KEYS}
    record.update(
        {
            "path": policy().dataset.dataset_path,
            "sha256": "a" * 64,
            "bytes": 123,
            "row_count": 2,
            "first_timestamp": "2025-01-01 09:00:00",
            "last_timestamp": "2025-01-01 09:01:00",
            "parser_schema_version": PARSER_SCHEMA_VERSION,
            "parser_decision": {
                "value": "PYTHON_CSV_EXCEL_DIALECT_WITH_HEADER",
                "evidence_status": "DECLARED",
            },
        }
    )
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "datasets": [record],
    }
    return manifest, record


def _unknown_calendar() -> CalendarSemanticsEvidence:
    return CalendarSemanticsEvidence(
        status=EligibilityEvidenceState.NOT_EVALUATED,
        policy_version=policy().session.policy_version,
        reason_code="CALENDAR_EVIDENCE_NOT_EVALUATED",
    )


def _blocked_pilot(monkeypatch):
    manifest, record = _manifest()
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("analytical extraction must not execute")

    monkeypatch.setattr(pilot_module, "extract_eligible_historical", forbidden)
    execution = run_gated_pilot(
        _table(),
        reconciliation_table=None,
        manifest=manifest,
        manifest_record=record,
        policy=policy(),
        canonical_policy=CanonicalizationPolicy(),
        resampling_policy=None,
        reconciliation_tolerance=ReconciliationTolerance(),
        repository_root=REPOSITORY_ROOT,
        calendar_evidence=_unknown_calendar(),
    )
    return execution, calls


def _eligible_pilot(*, reconciliation: pd.DataFrame | None):
    configured = synthetic_eligible_policy(policy())
    manifest, record = synthetic_eligible_manifest(configured)
    return run_gated_pilot(
        synthetic_eligible_m1_frame(),
        reconciliation_table=reconciliation,
        manifest=manifest,
        manifest_record=record,
        policy=configured,
        canonical_policy=synthetic_canonical_policy(),
        resampling_policy=synthetic_resampling_policy(),
        reconciliation_tolerance=ReconciliationTolerance(),
        repository_root=REPOSITORY_ROOT,
        calendar_evidence=synthetic_calendar_evidence(),
    )


def test_historical_command_requires_explicit_research_opt_in(capsys) -> None:
    assert main([]) == 2
    assert "requires explicit --research" in capsys.readouterr().err


def test_kan10_ineligible_source_blocks_before_analytical_extraction(monkeypatch) -> None:
    execution, calls = _blocked_pilot(monkeypatch)

    assert calls == 0
    assert execution.eligible_output is None
    assert execution.summary.status is PilotStatus.BLOCKED_BY_SOURCE_SEMANTICS
    assert execution.summary.catalog_generated is False
    assert execution.summary.eligible_event_count == 0
    assert execution.summary.eligible_feature_count == 0
    assert execution.summary.eligible_label_count == 0
    gates = {gate.gate_id: gate for gate in execution.summary.gate_audit}
    assert gates["G2_TEMPORAL_INTEGRITY"].status == "BLOCKED"
    assert gates["G2_TEMPORAL_INTEGRITY"].reason_code == "G2_TEMPORAL_EVIDENCE_BLOCKED"
    assert gates["G4_CALENDAR_COVERAGE"].status == "BLOCKED"
    assert gates["G4_CALENDAR_COVERAGE"].reason_code == "G4_CANONICAL_DEPENDENCY_BLOCKED"
    assert gates["G5_MTF_RECONCILIATION"].status == "NOT_EVALUATED"
    assert set(execution.summary.g6_g9_status.values()) == {"NOT_EVALUATED"}


def test_requested_hypothesis_is_audited_but_does_not_promote_gates(monkeypatch) -> None:
    execution, _ = _blocked_pilot(monkeypatch)

    requested = execution.summary.requested_configuration
    assert requested["bundle_version"] == "abshodeh-historical-labeling-v1"
    assert requested["event_policy_version"] == "layer2-confirmed-swings-v1"
    assert requested["feature_policy_version"] == "asof-features-v1"
    assert requested["label_policy_version"] == "abshodeh-level-outcome-v1"
    assert requested["session_policy_version"] == "abshodeh-research-session-v1"
    assert requested["timezone"] == "Asia/Tehran"
    assert requested["timestamp_period_semantics"] == "PERIOD_START"
    assert requested["timezone_period_evidence"] == "HYPOTHESIS"


def test_g5_not_evaluated_blocks_analytical_extraction(monkeypatch) -> None:
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1

    monkeypatch.setattr(pilot_module, "extract_eligible_historical", forbidden)
    execution = _eligible_pilot(reconciliation=None)

    assert calls == 0
    assert execution.eligible_output is None
    assert execution.summary.status is PilotStatus.BLOCKED_BY_RECONCILIATION
    gates = {gate.gate_id: gate for gate in execution.summary.gate_audit}
    assert gates["G5_MTF_RECONCILIATION"].status == "NOT_EVALUATED"


def test_g5_failure_blocks_analytical_extraction(monkeypatch) -> None:
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1

    monkeypatch.setattr(pilot_module, "extract_eligible_historical", forbidden)
    mismatch = synthetic_eligible_m5_frame()
    mismatch.loc[0, "close"] += 0.5
    execution = _eligible_pilot(reconciliation=mismatch)

    assert calls == 0
    assert execution.eligible_output is None
    assert execution.summary.status is PilotStatus.BLOCKED_BY_RECONCILIATION
    gates = {gate.gate_id: gate for gate in execution.summary.gate_audit}
    assert gates["G5_MTF_RECONCILIATION"].status == "FAIL"
    assert gates["G5_MTF_RECONCILIATION"].reason_code == "G5_RECONCILIATION_FAILED"


def test_g5_blocked_blocks_analytical_extraction(monkeypatch) -> None:
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1

    exact = synthetic_eligible_m5_frame()
    reconciliation = reconcile_bars(exact, exact.copy(), ReconciliationTolerance())
    blocked_gate = reconciliation.gate_result.model_copy(
        update={
            "status": GateStatus.BLOCKED,
            "reason_code": "G5_SYNTHETIC_BLOCKED",
            "message": "Synthetic test blocks G5 evidence.",
        }
    )
    monkeypatch.setattr(
        pilot_module,
        "reconcile_bars",
        lambda *args, **kwargs: SimpleNamespace(gate_result=blocked_gate),
    )
    monkeypatch.setattr(pilot_module, "extract_eligible_historical", forbidden)
    execution = _eligible_pilot(reconciliation=exact)

    assert calls == 0
    assert execution.eligible_output is None
    assert execution.summary.status is PilotStatus.BLOCKED_BY_RECONCILIATION
    gates = {gate.gate_id: gate for gate in execution.summary.gate_audit}
    assert gates["G5_MTF_RECONCILIATION"].status == "BLOCKED"


def test_synthetic_g0_g5_pass_executes_deterministic_end_to_end_extraction() -> None:
    first = _eligible_pilot(reconciliation=synthetic_eligible_m5_frame())
    second = _eligible_pilot(reconciliation=synthetic_eligible_m5_frame())

    assert first.summary.status is PilotStatus.ELIGIBLE
    assert first.eligible_output is not None
    assert second.eligible_output is not None
    assert first.eligible_output.to_json_bytes() == second.eligible_output.to_json_bytes()
    result = first.eligible_output
    assert result.event_count > 0
    assert result.event_count == result.feature_count == result.label_count
    assert first.summary.catalog_generated is True
    assert first.summary.eligible_event_count == result.event_count
    assert first.summary.eligible_feature_count == result.feature_count
    assert first.summary.eligible_label_count == result.label_count
    gates = {gate.gate_id: gate.status for gate in result.gate_audit}
    assert all(gates[f"G{index}_{name}"] == "PASS" for index, name in (
        (0, "PROVENANCE"),
        (1, "SCHEMA_PARSING"),
        (2, "TEMPORAL_INTEGRITY"),
        (3, "OHLC_NUMERIC"),
        (4, "CALENDAR_COVERAGE"),
        (5, "MTF_RECONCILIATION"),
    ))
