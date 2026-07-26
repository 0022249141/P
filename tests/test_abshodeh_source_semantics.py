from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pandas as pd
import pytest

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
from pipelines.source_semantics.probe import (
    _candidate_session_frame,
    _prepare_local,
)
from scripts import run_abshodeh_source_semantics as runner
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
    assert historical.session.evidence_status is None
    assert (
        historical.session.timezone_evidence_status
        is HistoricalEvidenceStatus.DECLARED
    )
    assert (
        historical.session.period_semantics_evidence_status
        is HistoricalEvidenceStatus.DERIVED
    )


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
    assert end.dropped_coverage_boundary_count == 1


def test_candidate_session_membership_respects_each_timestamp_convention() -> None:
    prepared = _prepare_local(
        _bars(
            [
                "2026-01-03 09:00:00",
                "2026-01-03 09:01:00",
                "2026-01-03 21:59:00",
                "2026-01-03 22:00:00",
            ]
        ),
        _policy(),
    )

    period_start = _candidate_session_frame(
        prepared,
        _policy(),
        PeriodSemantics.PERIOD_START,
    )
    period_end = _candidate_session_frame(
        prepared,
        _policy(),
        PeriodSemantics.PERIOD_END,
    )

    assert period_start["timestamp"].dt.strftime("%H:%M").tolist() == [
        "09:00",
        "09:01",
        "21:59",
    ]
    assert period_end["timestamp"].dt.strftime("%H:%M").tolist() == [
        "09:01",
        "21:59",
        "22:00",
    ]


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


@pytest.mark.parametrize(
    "protected_output",
    (
        "/".join(("data" + "_clean", "abshodeNaghdi-1.csv")),
        "data/manifests/committed_datasets.json",
        "configs/research/abshodeh-source-semantics-v1.json",
        "configs/research/abshodeh-historical-labeling-v2.json",
    ),
)
def test_runner_rejects_output_aliases_to_protected_inputs_before_writing(
    protected_output: str,
    capsys,
    monkeypatch,
) -> None:
    def forbidden_build():
        raise AssertionError("artifact construction must not start")

    monkeypatch.setattr(runner, "build_artifact", forbidden_build)

    assert runner.main(["--research", "--output", protected_output]) == 2
    assert "must not overwrite" in capsys.readouterr().err


def test_runner_rejects_existing_hard_link_to_protected_input_before_writing(
    capsys,
    monkeypatch,
) -> None:
    alias = POLICY_PATH.with_name(
        f".{POLICY_PATH.name}.{os.getpid()}.hard-link-test"
    )
    protected_before = POLICY_PATH.read_bytes()

    def forbidden_build():
        raise AssertionError("artifact construction must not start")

    monkeypatch.setattr(runner, "build_artifact", forbidden_build)

    alias.hardlink_to(POLICY_PATH)
    try:
        assert runner.main(["--research", "--output", str(alias)]) == 2
        assert "must not overwrite" in capsys.readouterr().err
        assert POLICY_PATH.read_bytes() == protected_before
    finally:
        alias.unlink(missing_ok=True)


def test_runner_rejects_symbolic_link_output_before_writing(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    target = tmp_path / "target.json"
    target.write_text("existing", encoding="utf-8")
    alias = tmp_path / "output-link.json"
    alias.symlink_to(target)

    def forbidden_build(**_kwargs):
        raise AssertionError("artifact construction must not start")

    monkeypatch.setattr(runner, "build_artifact", forbidden_build)

    assert runner.main(["--research", "--output", str(alias)]) == 2
    assert "must not be a symbolic link" in capsys.readouterr().err
    assert target.read_text(encoding="utf-8") == "existing"


def test_policy_model_is_immutable() -> None:
    policy = _policy()
    copied = copy.deepcopy(policy)
    assert copied.to_json_bytes() == policy.to_json_bytes()


def test_run_manifest_records_mandatory_reproducibility_provenance() -> None:
    semantics = _policy()
    manifest_path = REPOSITORY_ROOT / semantics.manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    run = runner._build_run_manifest(
        cli_arguments=("--research",),
        config_path=POLICY_PATH,
        output_path=runner._path(runner.DEFAULT_OUTPUT),
        semantics=semantics,
        manifest=manifest,
    )

    assert len(run.code_revision) == 40
    assert run.git_dirty == (run.git_diff_sha256 is not None)
    assert run.entrypoint == "scripts/run_abshodeh_source_semantics.py"
    assert run.cli_arguments == ("--research",)
    assert run.configuration_snapshot_path == (
        "configs/research/abshodeh-source-semantics-v1.json"
    )
    assert run.configuration_snapshot_sha256 == runner._sha256(POLICY_PATH)
    assert len(run.source_inputs) == len(manifest["datasets"])
    assert all(item.sha256 and item.byte_size > 0 for item in run.source_inputs)
    assert run.analytical_timezone == "Asia/Tehran"
    assert run.calendar_version and run.bar_builder_version
    assert run.python_version and run.pandas_version and run.numpy_version
    assert run.floating_point_backend.startswith("numpy.float64")
    assert run.floating_point_settings["float64_eps"]
    assert run.random_seeds == {"numpy": None, "python": None}
