from __future__ import annotations

import pandas as pd

from core.dataset_manifest import MANIFEST_SCHEMA_VERSION, PARSER_SCHEMA_VERSION, RECORD_KEYS
from pipelines.historical_labeling.contracts import PilotStatus
from pipelines.historical_labeling.pilot import run_gated_pilot
from scripts.run_historical_labeling import main
from tests.historical_labeling_helpers import policy


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


def test_historical_command_requires_explicit_research_opt_in(capsys) -> None:
    assert main([]) == 2
    assert "requires explicit --research" in capsys.readouterr().err


def test_kan10_ineligible_source_blocks_before_analytical_callback() -> None:
    manifest, record = _manifest()
    calls = 0

    def analytical_callback():
        nonlocal calls
        calls += 1
        return "events"

    execution = run_gated_pilot(
        _table(),
        manifest=manifest,
        manifest_record=record,
        policy=policy(),
        on_eligible=analytical_callback,
    )

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
    assert set(execution.summary.g6_g9_status.values()) == {"NOT_EVALUATED"}


def test_requested_hypothesis_is_audited_but_does_not_promote_gates() -> None:
    manifest, record = _manifest()
    execution = run_gated_pilot(
        _table(),
        manifest=manifest,
        manifest_record=record,
        policy=policy(),
        on_eligible=lambda: None,
    )

    requested = execution.summary.requested_configuration
    assert requested["bundle_version"] == "abshodeh-historical-labeling-v1"
    assert requested["event_policy_version"] == "layer2-confirmed-swings-v1"
    assert requested["feature_policy_version"] == "asof-features-v1"
    assert requested["label_policy_version"] == "abshodeh-level-outcome-v1"
    assert requested["session_policy_version"] == "abshodeh-research-session-v1"
    assert requested["timezone"] == "Asia/Tehran"
    assert requested["timestamp_period_semantics"] == "PERIOD_START"
    assert requested["timezone_period_evidence"] == "HYPOTHESIS"
    gates = {gate.gate_id: gate.status for gate in execution.summary.gate_audit}
    assert gates["G2_TEMPORAL_INTEGRITY"] == "BLOCKED"
    assert gates["G4_CALENDAR_COVERAGE"] == "BLOCKED"
