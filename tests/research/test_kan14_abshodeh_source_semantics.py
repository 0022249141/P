from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_abshodeh_source_semantics import main


pytestmark = pytest.mark.research


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_ARTIFACT = (
    REPOSITORY_ROOT
    / "docs"
    / "audits"
    / "artifacts"
    / "KAN-14-abshodeh-source-semantics.json"
)


def test_real_abshodeh_semantics_and_pilot_are_reproducible(tmp_path: Path) -> None:
    output = tmp_path / "kan14-source-semantics.json"

    assert (
        main(
            [
                "--research",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert output.read_bytes() == COMMITTED_ARTIFACT.read_bytes()
    payload = json.loads(output.read_text(encoding="ascii"))

    candidates = {
        item["period_semantics"]: item for item in payload["period_candidates"]
    }
    assert candidates["PERIOD_START"]["disposition"] == "PROMOTED"
    assert candidates["PERIOD_START"]["common_count"] == 12317
    assert candidates["PERIOD_START"]["exact_ohlcv_count"] == 12317
    assert candidates["PERIOD_END"]["disposition"] == "REJECTED"
    assert payload["excluded_out_of_session_row_count"] == 38
    assert set(payload["g0_g5_status"].values()) == {"PASS"}
    assert payload["pilot_summary"]["status"] == "ELIGIBLE"
    assert payload["pilot_summary"]["eligible_event_count"] == 451
    assert payload["pilot_summary"]["eligible_feature_count"] == 451
    assert payload["pilot_summary"]["eligible_label_count"] == 451
    assert payload["feature_ineligible_event_count"] > 0
    assert sum(payload["feature_ineligibility_reasons"].values()) == (
        payload["feature_ineligible_event_count"]
    )
    assert payload["censored_label_count"] == 74
    assert sum(payload["label_outcome_counts"].values()) == 451
    assert (
        payload["manifest_sha256_before"]
        == payload["manifest_sha256_after"]
    )
    assert (
        payload["protected_source_hashes_before"]
        == payload["protected_source_hashes_after"]
    )
