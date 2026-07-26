"""Run the explicit research-only KAN-14 Abshodeh source-semantics probe."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import locale
import os
import platform
import subprocess
import sys
import time as runtime_time
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from core.dataset_manifest import verify_manifest  # noqa: E402
from pipelines.canonical import (  # noqa: E402
    DatasetIdentity,
    GateStatus,
    ReconciliationTolerance,
    evaluate_quality,
    reconcile_bars,
    resample_bars,
)
from pipelines.historical_labeling.contracts import (  # noqa: E402
    CalendarSemanticsEvidence,
    EligibilityEvidenceState,
    PilotStatus,
)
from pipelines.historical_labeling.pilot import run_gated_pilot  # noqa: E402
from pipelines.historical_labeling.policies import (  # noqa: E402
    load_policy as load_historical_policy,
)
from pipelines.source_semantics import (  # noqa: E402
    AnalyticalRunManifest,
    RunInputEvidence,
    SourceSemanticsArtifact,
    build_canonical_policy,
    build_m1_to_m5_policy,
    evaluate_period_candidates,
    load_policy,
    policy_sha256,
    reconciliation_overlap,
    sha256_paths,
)


DEFAULT_CONFIG = Path("configs/research/abshodeh-source-semantics-v1.json")
DEFAULT_OUTPUT = Path(
    "docs/audits/artifacts/KAN-14-abshodeh-source-semantics.json"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def _path(value: str | Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else REPOSITORY_ROOT / candidate


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()


def _git_output(*args: str) -> bytes:
    return subprocess.check_output(
        ("git", *args),
        cwd=REPOSITORY_ROOT,
        stderr=subprocess.DEVNULL,
    )


def _git_provenance(
    *,
    excluded_outputs: Sequence[Path],
) -> tuple[str, bool, str | None]:
    revision = _git_output("rev-parse", "HEAD").decode("ascii").strip()
    repository_root = REPOSITORY_ROOT.resolve()
    excluded_relative = {
        _repository_relative(path)
        for path in excluded_outputs
        if path.resolve().is_relative_to(repository_root)
    }
    pathspecs = (".", *(f":(exclude){path}" for path in sorted(excluded_relative)))
    tracked_diff = _git_output("diff", "--binary", "HEAD", "--", *pathspecs)

    untracked = _git_output(
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    untracked_paths = tuple(
        raw_path
        for raw_path in sorted(item for item in untracked.split(b"\0") if item)
        if raw_path.decode("utf-8") not in excluded_relative
    )
    if not tracked_diff and not untracked_paths:
        return revision, False, None

    digest = hashlib.sha256()
    digest.update(tracked_diff)
    for raw_path in untracked_paths:
        path = REPOSITORY_ROOT / raw_path.decode("utf-8")
        digest.update(b"\0UNTRACKED\0")
        digest.update(raw_path)
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
    return revision, True, digest.hexdigest()


def _build_run_manifest(
    *,
    cli_arguments: Sequence[str],
    config_path: Path,
    output_path: Path,
    semantics: object,
    manifest: Mapping[str, object],
) -> AnalyticalRunManifest:
    revision, dirty, diff_sha256 = _git_provenance(
        excluded_outputs=(_path(DEFAULT_OUTPUT), output_path),
    )
    source_inputs = tuple(
        RunInputEvidence(
            path=str(record["path"]),
            sha256=str(record["sha256"]),
            byte_size=int(record["bytes"]),
        )
        for record in sorted(
            (
                record
                for record in manifest["datasets"]  # type: ignore[index]
                if isinstance(record, dict)
            ),
            key=lambda record: str(record["path"]),
        )
    )
    resampling_policy = build_m1_to_m5_policy(semantics)  # type: ignore[arg-type]
    return AnalyticalRunManifest(
        code_revision=revision,
        git_dirty=dirty,
        git_diff_sha256=diff_sha256,
        entrypoint="scripts/run_abshodeh_source_semantics.py",
        cli_arguments=tuple(cli_arguments),
        configuration_snapshot_path=_repository_relative(config_path),
        configuration_snapshot_sha256=_sha256(config_path),
        source_inputs=source_inputs,
        locale=locale.setlocale(locale.LC_ALL, None),
        runtime_timezone=(
            f"TZ={os.environ.get('TZ', 'UNSET')};"
            f"tzname={'|'.join(runtime_time.tzname)}"
        ),
        analytical_timezone=semantics.source_timezone,  # type: ignore[attr-defined]
        calendar_version=resampling_policy.calendar_version,
        bar_builder_version=resampling_policy.policy_version,
        python_version=platform.python_version(),
        pandas_version=pd.__version__,
        numpy_version=np.__version__,
        floating_point_backend=(
            f"numpy.float64/IEEE-754/{np.finfo(np.float64).bits}-bit"
        ),
        floating_point_settings={
            **{
                f"numpy_geterr_{key}": str(value)
                for key, value in sorted(np.geterr().items())
            },
            "float64_eps": repr(float(np.finfo(np.float64).eps)),
        },
        random_seeds={"numpy": None, "python": None},
        randomness_policy="NO_RANDOMNESS_USED_DETERMINISTIC_PIPELINE",
    )


def _protected_input_paths(config_path: Path) -> frozenset[Path]:
    semantics = load_policy(config_path)
    manifest_path = _path(semantics.manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    protected = {
        config_path.resolve(),
        manifest_path,
        _path(semantics.historical_policy_path).resolve(),
    }
    protected.update(
        _path(str(record["path"])).resolve()
        for record in manifest.get("datasets", [])
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    )
    return frozenset(protected)


def _validate_output_path(output: Path, config_path: Path) -> None:
    if output.is_symlink():
        raise ValueError("KAN-14 output must not be a symbolic link.")
    protected_inputs = _protected_input_paths(config_path)
    aliases_protected_input = output.exists() and any(
        protected_input.exists() and output.samefile(protected_input)
        for protected_input in protected_inputs
    )
    if output.resolve() in protected_inputs or aliases_protected_input:
        raise ValueError(
            "KAN-14 output must not overwrite a protected dataset, manifest, "
            "or configuration input."
        )


def _record(
    manifest: Mapping[str, object],
    path: str,
) -> Mapping[str, object]:
    matches = [
        item
        for item in manifest.get("datasets", [])  # type: ignore[union-attr]
        if isinstance(item, dict) and item.get("path") == path
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one manifest record for {path}")
    return matches[0]


def _identity(
    manifest: Mapping[str, object],
    record: Mapping[str, object],
    *,
    dataset_id: str,
) -> DatasetIdentity:
    parser = record["parser_decision"]
    parser_decision = parser["value"] if isinstance(parser, dict) else str(parser)
    return DatasetIdentity(
        dataset_id=dataset_id,
        path=str(record["path"]),
        source_sha256=str(record["sha256"]),
        byte_size=int(record["bytes"]),
        parser_decision=str(parser_decision),
        parser_schema_version=str(record["parser_schema_version"]),
        manifest_schema_version=str(manifest["manifest_schema_version"]),
    )


def _require_g0_g4_pass(evaluation: object, label: str) -> None:
    report = evaluation.report  # type: ignore[attr-defined]
    failed = [
        f"{result.gate_id.value}:{result.status.value}:{result.reason_code}"
        for result in report.results[:5]
        if result.status is not GateStatus.PASS
    ]
    if failed:
        raise ValueError(f"{label} G0-G4 did not pass: {failed}")


def build_artifact(
    *,
    cli_arguments: Sequence[str] = ("--research",),
    config_path: Path | None = None,
    output_path: Path | None = None,
) -> SourceSemanticsArtifact:
    resolved_config = _path(DEFAULT_CONFIG) if config_path is None else config_path
    resolved_output = _path(DEFAULT_OUTPUT) if output_path is None else output_path
    semantics = load_policy(resolved_config)
    manifest_path = _path(semantics.manifest_path)
    manifest_before = _sha256(manifest_path)
    manifest_errors = verify_manifest(REPOSITORY_ROOT, manifest_path)
    if manifest_errors:
        raise ValueError(f"committed dataset manifest is invalid: {manifest_errors}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_manifest = _build_run_manifest(
        cli_arguments=cli_arguments,
        config_path=resolved_config,
        output_path=resolved_output,
        semantics=semantics,
        manifest=manifest,
    )
    protected_paths = [
        str(record["path"])
        for record in manifest["datasets"]
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    ]
    protected_before = sha256_paths(REPOSITORY_ROOT, protected_paths)

    m1_record = _record(manifest, semantics.m1_dataset_path)
    m5_record = _record(manifest, semantics.native_m5_dataset_path)
    m1_path = _path(semantics.m1_dataset_path)
    m5_path = _path(semantics.native_m5_dataset_path)
    if _sha256(m1_path) != m1_record["sha256"]:
        raise ValueError("M1 bytes differ from the committed manifest")
    if _sha256(m5_path) != m5_record["sha256"]:
        raise ValueError("native M5 bytes differ from the committed manifest")
    m1 = pd.read_csv(m1_path)
    native_m5 = pd.read_csv(m5_path)

    candidates = evaluate_period_candidates(
        m1,
        native_m5,
        policy=semantics,
        target_minutes=5,
    )
    m1_policy = build_canonical_policy(
        semantics,
        expected_interval_seconds=60,
    )
    m5_policy = build_canonical_policy(
        semantics,
        expected_interval_seconds=300,
    )
    m1_quality = evaluate_quality(
        m1,
        dataset=_identity(
            manifest,
            m1_record,
            dataset_id="abshode-naghdi-clean-m1-manifest-v1",
        ),
        policy=m1_policy,
        manifest=manifest,
    )
    m5_quality = evaluate_quality(
        native_m5,
        dataset=_identity(
            manifest,
            m5_record,
            dataset_id="abshode-naghdi-clean-m5-manifest-v1",
        ),
        policy=m5_policy,
        manifest=manifest,
    )
    _require_g0_g4_pass(m1_quality, "M1")
    _require_g0_g4_pass(m5_quality, "native M5")
    if m1_quality.analytical_frame is None or m5_quality.analytical_frame is None:
        raise ValueError("canonical session partition did not produce analytical frames")

    resampling_policy = build_m1_to_m5_policy(semantics)
    generated = resample_bars(
        m1_quality.analytical_frame,
        resampling_policy,
    )
    native_overlap = reconciliation_overlap(
        generated.frame,
        m5_quality.analytical_frame,
    )
    reconciliation = reconcile_bars(
        generated.frame,
        native_overlap,
        ReconciliationTolerance(),
    )
    if reconciliation.gate_result.status is not GateStatus.PASS:
        raise ValueError(
            "governed real-data M1-to-M5 reconciliation did not pass: "
            f"{reconciliation.gate_result.reason_code}"
        )

    historical_policy = load_historical_policy(
        _path(semantics.historical_policy_path)
    )
    execution = run_gated_pilot(
        m1,
        reconciliation_table=native_overlap,
        manifest=manifest,
        manifest_record=m1_record,
        policy=historical_policy,
        canonical_policy=m1_policy,
        resampling_policy=resampling_policy,
        reconciliation_tolerance=ReconciliationTolerance(),
        repository_root=REPOSITORY_ROOT,
        calendar_evidence=CalendarSemanticsEvidence(
            status=EligibilityEvidenceState.PASS,
            policy_version=historical_policy.session.policy_version,
            reason_code="SESSION_SEMANTICS_PASS_HOLIDAY_COMPLETENESS_UNKNOWN",
        ),
    )
    if execution.summary.status is not PilotStatus.ELIGIBLE:
        raise ValueError(
            f"real KAN-13 pilot remains blocked: {execution.summary.status.value}"
        )
    if execution.eligible_output is None:
        raise ValueError("eligible pilot did not return an extraction result")
    feature_ineligibility_reasons = Counter(
        record.reason_code
        for record in execution.eligible_output.feature_ineligibility
    )
    label_outcome_counts = Counter(
        label.outcome_class.value for label in execution.eligible_output.labels
    )

    excluded_examples = tuple(
        str(m1.iloc[index]["timestamp"])
        for index in m1_quality.excluded_out_of_session_rows[:10]
    )
    protected_after = sha256_paths(REPOSITORY_ROOT, protected_paths)
    manifest_after = _sha256(manifest_path)
    g0_g5 = {
        gate.gate_id: gate.status
        for gate in execution.summary.gate_audit
        if gate.gate_id.startswith(tuple(f"G{index}_" for index in range(6)))
    }
    return SourceSemanticsArtifact(
        policy_version=semantics.policy_version,
        policy_sha256=policy_sha256(semantics),
        run_manifest=run_manifest,
        manifest_sha256_before=manifest_before,
        manifest_sha256_after=manifest_after,
        protected_source_hashes_before=protected_before,
        protected_source_hashes_after=protected_after,
        timezone_candidate_matrix=(
            {
                "candidate": "Asia/Tehran",
                "disposition": "PROMOTED",
                "evidence_basis": semantics.timezone_evidence.basis.value,
                "evidence_status": semantics.timezone_evidence.status.value,
            },
            {
                "candidate": "UTC",
                "disposition": "REJECTED",
                "reason": "contradicts the user-verified Faraz export setting",
            },
            {
                "candidate": "UNKNOWN_SERVER_TIME",
                "disposition": "REJECTED",
                "reason": "higher-strength explicit platform-setting evidence is available",
            },
        ),
        period_candidates=candidates,
        promoted_semantics={
            "out_of_session_policy": semantics.out_of_session_policy.value,
            "period_semantics": semantics.period_semantics.value,
            "session": (
                f"[{semantics.session_start},{semantics.session_end})"
            ),
            "session_end_convention": semantics.session_end_convention.value,
            "source_gap_policy": semantics.source_gap_policy.value,
            "timezone": semantics.source_timezone,
        },
        canonical_source_row_count=len(m1_quality.canonicalization.frame),
        analytical_source_row_count=len(m1_quality.analytical_frame),
        excluded_out_of_session_row_count=len(
            m1_quality.excluded_out_of_session_rows
        ),
        excluded_out_of_session_examples=excluded_examples,
        generated_m5_count=len(generated.frame),
        native_m5_overlap_count=len(native_overlap),
        feature_ineligible_event_count=(
            execution.eligible_output.feature_ineligibility_count
        ),
        feature_ineligibility_records=(
            execution.eligible_output.feature_ineligibility
        ),
        feature_ineligibility_reasons=dict(
            sorted(feature_ineligibility_reasons.items())
        ),
        censored_label_count=execution.eligible_output.censoring_count,
        label_outcome_counts=dict(sorted(label_outcome_counts.items())),
        g0_g5_status=g0_g5,
        pilot_summary=execution.summary.model_dump(
            mode="json",
            exclude_none=False,
        ),
        external_reconciliation=semantics.external_reconciliation,
        unresolved_evidence=(
            "authoritative holiday and trading-day calendar is unavailable",
            "individual sparse intervals cannot always distinguish no-print from feed outage",
            "volume meaning is unknown",
        ),
        limitations=semantics.limitations,
    )


def main(argv: Sequence[str] | None = None) -> int:
    cli_arguments = tuple(sys.argv[1:] if argv is None else argv)
    args = parse_args(cli_arguments)
    if not args.research:
        print("KAN-14 full-corpus evidence requires explicit --research.", file=sys.stderr)
        return 2
    config_path = _path(args.config)
    if config_path != _path(DEFAULT_CONFIG):
        print("Only the reviewed KAN-14 source-semantics config is supported.", file=sys.stderr)
        return 2
    output = _path(args.output)
    try:
        _validate_output_path(output, config_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    artifact = build_artifact(
        cli_arguments=cli_arguments,
        config_path=config_path,
        output_path=output,
    )
    content = artifact.to_json_bytes()
    if args.check:
        if not output.is_file():
            print("KAN-14 source-semantics artifact is missing or stale.")
            return 1
        try:
            recorded = SourceSemanticsArtifact.model_validate_json(
                output.read_text(encoding="ascii")
            )
        except ValueError:
            print("KAN-14 source-semantics artifact is missing or stale.")
            return 1
        reproducible = artifact.model_copy(
            update={"run_manifest": recorded.run_manifest}
        ).to_json_bytes()
        if output.read_bytes() != reproducible:
            print("KAN-14 source-semantics artifact is missing or stale.")
            return 1
        print(
            "KAN-14 source semantics: PERIOD_START promoted; "
            "G0-G5 PASS; real pilot ELIGIBLE; artifact current."
        )
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    state = "unchanged" if output.is_file() and output.read_bytes() == content else "written"
    if state == "written":
        output.write_bytes(content)
    print(
        "KAN-14 source semantics: PERIOD_START promoted; "
        f"G0-G5 PASS; real pilot ELIGIBLE; artifact {state}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
