from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from core.dataset_manifest import MANIFEST_SCHEMA_VERSION, PARSER_SCHEMA_VERSION, RECORD_KEYS
from pipelines.canonical import (
    DatasetIdentity,
    GateStatus,
    PeriodSemantics,
    evaluate_quality,
    resample_bars,
)
from pipelines.historical_labeling.contracts import EvidenceStatus as HistoricalEvidenceStatus
from pipelines.historical_labeling.policies import load_policy as load_historical_policy
from pipelines.source_semantics import (
    CandidateDisposition,
    build_canonical_policy,
    build_m1_to_m5_policy,
    evaluate_period_candidates,
    load_policy,
)
from scripts.run_abshodeh_source_semantics import main


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = (
    REPOSITORY_ROOT
    / "configs"
    / "research"
    / "abshodeh-source-semantics-v1.json"
)


def _policy():
    return load_policy(POLICY_PATH)


def _bars(timestamps: list[str]) -> pd.DataFrame:
    values = [100.0 + index for index in range(len(timestamps))]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": values,
            "high": [value + 2.0 for value in values],
            "low": [value - 1.0 for value in values],
            "close": [value + 1.0 for value in values],
            "volume": [float(index + 1) for index in range(len(timestamps))],
        }
    )


def _native_m5(lower: pd.DataFrame) -> pd.DataFrame:
    indexed = lower.copy(deep=True)
    indexed["timestamp"] = pd.to_datetime(indexed["timestamp"])
    return (
        indexed.set_index("timestamp")
        .groupby(
            pd.Grouper(
                freq="5min",
                label="left",
                closed="left",
                origin="start_day",
            )
        )
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna()
        .reset_index()
    )


def _manifest(path: str, row_count: int) -> tuple[dict[str, object], DatasetIdentity]:
    record = {key: "evidence" for key in RECORD_KEYS}
    record.update(
        {
            "path": path,
            "sha256": "a" * 64,
            "bytes": 123,
            "row_count": row_count,
            "parser_schema_version": PARSER_SCHEMA_VERSION,
            "parser_decision": {
                "value": "IN_MEMORY_DATAFRAME",
                "evidence_status": "DECLARED",
            },
        }
    )
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "datasets": [record],
    }
    identity = DatasetIdentity(
        dataset_id="tiny-abshodeh",
        path=path,
        source_sha256="a" * 64,
        byte_size=123,
        parser_decision="IN_MEMORY_DATAFRAME",
        parser_schema_version=PARSER_SCHEMA_VERSION,
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
    )
    return manifest, identity


def test_reviewed_policy_and_historical_v2_are_explicit() -> None:
    semantics = _policy()
    historical = load_historical_policy(
        REPOSITORY_ROOT / semantics.historical_policy_path
    )

    assert semantics.source_timezone == "Asia/Tehran"
    assert semantics.period_semantics is PeriodSemantics.PERIOD_START
    assert semantics.session_start == "09:00:00"
    assert semantics.session_end == "22:00:00"
    assert historical.session.evidence_status is HistoricalEvidenceStatus.DERIVED


def test_period_start_is_uniquely_promoted_on_non_adjacent_dates() -> None:
    rows: list[pd.DataFrame] = []
    for date in ("2026-01-03", "2026-01-11", "2026-02-07"):
        rows.append(
            _bars(
                [
                    f"{date} 09:00:00",
                    f"{date} 09:02:00",
                    f"{date} 09:04:00",
                    f"{date} 09:05:00",
                    f"{date} 09:09:00",
                    f"{date} 09:10:00",
                    f"{date} 09:14:00",
                ]
            )
        )
    lower = pd.concat(rows, ignore_index=True)
    native = _native_m5(lower)

    candidates = evaluate_period_candidates(lower, native, policy=_policy())
    by_semantics = {candidate.period_semantics: candidate for candidate in candidates}

    start = by_semantics[PeriodSemantics.PERIOD_START]
    end = by_semantics[PeriodSemantics.PERIOD_END]
    assert start.disposition is CandidateDisposition.PROMOTED
    assert start.common_count == start.exact_ohlcv_count == 9
    assert start.distinct_date_count == 3
    assert end.disposition is CandidateDisposition.REJECTED
    assert end.exact_ohlcv_count < end.common_count


def test_session_partition_retains_canonical_rows_and_excludes_22_00() -> None:
    table = _bars(
        [
            "2026-01-03 08:59:00",
            "2026-01-03 09:00:00",
            "2026-01-03 21:59:00",
            "2026-01-03 22:00:00",
            "2026-01-03 22:05:00",
        ]
    )
    fixture_path = "/".join(("data" + "_clean", "tiny-abshodeh-1.csv"))
    manifest, identity = _manifest(fixture_path, len(table))
    evaluation = evaluate_quality(
        table,
        dataset=identity,
        policy=build_canonical_policy(_policy(), expected_interval_seconds=60),
        manifest=manifest,
    )

    assert evaluation.canonicalization.frame is not None
    assert len(evaluation.canonicalization.frame) == 5
    assert evaluation.analytical_frame is not None
    assert len(evaluation.analytical_frame) == 2
    assert evaluation.excluded_out_of_session_rows == (0, 3, 4)
    g4 = evaluation.report.results[4]
    assert g4.status is GateStatus.PASS
    assert "OUT_OF_SESSION_BARS_EXCLUDED" in {
        finding.reason_code for finding in g4.findings
    }
    local = evaluation.analytical_frame["timestamp"].dt.tz_convert("Asia/Tehran")
    assert local.dt.strftime("%H:%M").tolist() == ["09:00", "21:59"]


def test_sparse_session_resampling_drops_only_global_partial_first_bin() -> None:
    local = _bars(
        [
            "2026-01-03 09:02:00",
            "2026-01-03 09:04:00",
            "2026-01-03 09:05:00",
            "2026-01-03 09:09:00",
            "2026-01-03 09:10:00",
        ]
    )
    local["timestamp"] = (
        pd.to_datetime(local["timestamp"])
        .dt.tz_localize("Asia/Tehran")
        .dt.tz_convert("UTC")
    )

    result = resample_bars(local, build_m1_to_m5_policy(_policy()))

    assert result.dropped_coverage_boundary_bin_count == 1
    assert len(result.frame) == 2
    assert result.incomplete_bin_count == 3
    labels = result.frame["timestamp"].dt.tz_convert("Asia/Tehran")
    assert labels.dt.strftime("%H:%M").tolist() == ["09:05", "09:10"]
    assert result.frame.iloc[0]["open"] == 102.0
    assert result.frame.iloc[0]["close"] == 104.0


def test_full_corpus_command_requires_explicit_research(capsys) -> None:
    assert main([]) == 2
    assert "requires explicit --research" in capsys.readouterr().err


def test_policy_model_is_immutable() -> None:
    policy = _policy()
    copied = copy.deepcopy(policy)
    assert copied.to_json_bytes() == policy.to_json_bytes()
