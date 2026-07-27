from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipelines.behavioral_fingerprint.artifact import BehavioralFingerprintAudit
from pipelines.behavioral_fingerprint.contracts import (
    BehavioralFingerprintArtifact,
)
from scripts.run_behavioral_fingerprint import main


pytestmark = pytest.mark.research


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_AUDIT = (
    REPOSITORY_ROOT
    / "docs"
    / "audits"
    / "artifacts"
    / "KAN-15-abshodeh-behavioral-fingerprint.json"
)


def test_real_behavioral_fingerprint_is_reproducible(tmp_path: Path) -> None:
    catalog = tmp_path / "kan15-catalog.json"
    audit_path = tmp_path / "kan15-audit.json"
    arguments = [
        "--research",
        "--output",
        str(catalog),
        "--audit-output",
        str(audit_path),
    ]

    assert main(arguments) == 0
    catalog_bytes = catalog.read_bytes()
    audit_bytes = audit_path.read_bytes()
    assert main([*arguments, "--check"]) == 0
    assert catalog.read_bytes() == catalog_bytes
    assert audit_path.read_bytes() == audit_bytes

    fingerprint = BehavioralFingerprintArtifact.model_validate_json(catalog_bytes)
    audit = BehavioralFingerprintAudit.model_validate_json(audit_bytes)
    assert fingerprint.unique_eligible_event_count == 451
    assert fingerprint.unique_resolved_label_count == 382
    assert fingerprint.unique_censored_label_count == 69
    assert fingerprint.unassigned_feature_ineligible_count == 2
    assert fingerprint.feature_ineligibility_reasons == {
        "INSUFFICIENT_PAST_ONLY_HISTORY": 1,
        "NON_POSITIVE_RANGE_FEATURE": 1,
    }
    assert fingerprint.cell_assignment_missing_semantics_count == 0
    assert fingerprint.cell_count == 177
    assert all(
        coverage.assigned_event_count == 451
        for coverage in fingerprint.view_coverage
    )
    assert {
        gate.gate_id: gate.status for gate in fingerprint.gate_audit
    } == {
        "G6_FEATURE_REPRODUCTION": "PASS",
        "G7_ANALYTICAL_ELIGIBILITY": "NOT_EVALUATED",
        "G8_STATISTICAL_ELIGIBILITY": "NOT_EVALUATED",
        "G9_EXECUTION_BACKTEST_ELIGIBILITY": "NOT_EVALUATED",
    }
    assert audit.heuristic_only_cell_count == 54
    assert audit.not_statistically_eligible_cell_count == 123
    assert audit.protected_source_hashes_before == (
        audit.protected_source_hashes_after
    )
    assert audit.manifest_sha256_before == audit.manifest_sha256_after
    assert audit.full_catalog_policy == "RESEARCH_ONLY_UNCOMMITTED"
    assert len(audit.bounded_cell_sample) <= 12
    assert json.loads(COMMITTED_AUDIT.read_text(encoding="ascii")) == json.loads(
        audit_path.read_text(encoding="ascii")
    )
