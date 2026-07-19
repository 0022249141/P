from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_historical_labeling import main


pytestmark = pytest.mark.research


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_SUMMARY = (
    REPOSITORY_ROOT
    / "docs"
    / "audits"
    / "artifacts"
    / "KAN-13-abshodeh-pilot-summary.json"
)


def test_full_abshodeh_pilot_is_blocked_before_catalog_generation(tmp_path) -> None:
    summary = tmp_path / "summary.json"
    catalog = tmp_path / "historical-events.jsonl"
    result = main(
        [
            "--research",
            "--dataset",
            "data_clean/abshodeNaghdi-1.csv",
            "--summary-output",
            str(summary),
        ]
    )

    assert result == 0
    assert summary.read_bytes() == COMMITTED_SUMMARY.read_bytes()
    assert not catalog.exists()
    payload = json.loads(summary.read_text(encoding="ascii"))
    assert payload["status"] == "BLOCKED_BY_SOURCE_SEMANTICS"
    assert payload["catalog_generated"] is False
    assert payload["eligible_event_count"] == 0
    assert payload["eligible_feature_count"] == 0
    assert payload["eligible_label_count"] == 0
    gates = {item["gate_id"]: item for item in payload["gate_audit"]}
    assert gates["G2_TEMPORAL_INTEGRITY"]["status"] == "BLOCKED"
    assert gates["G4_CALENDAR_COVERAGE"]["status"] == "BLOCKED"
    assert set(payload["g6_g9_status"].values()) == {"NOT_EVALUATED"}
