"""Run the explicit research-only KAN-14 Abshodeh source-semantics probe."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

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


def build_artifact() -> SourceSemanticsArtifact:
    semantics = load_policy(_path(DEFAULT_CONFIG))
    manifest_path = _path(semantics.manifest_path)
    manifest_before = _sha256(manifest_path)
    manifest_errors = verify_manifest(REPOSITORY_ROOT, manifest_path)
    if manifest_errors:
        raise ValueError(f"committed dataset manifest is invalid: {manifest_errors}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
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
    args = parse_args(argv)
    if not args.research:
        print("KAN-14 full-corpus evidence requires explicit --research.", file=sys.stderr)
        return 2
    config_path = _path(args.config)
    if config_path != _path(DEFAULT_CONFIG):
        print("Only the reviewed KAN-14 source-semantics config is supported.", file=sys.stderr)
        return 2
    artifact = build_artifact()
    content = artifact.to_json_bytes()
    output = _path(args.output)
    if args.check:
        if not output.is_file() or output.read_bytes() != content:
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
