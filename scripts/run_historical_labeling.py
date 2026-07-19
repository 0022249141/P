"""Run the explicitly gated KAN-13 historical research pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Sequence

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from pipelines.historical_labeling.pilot import run_gated_pilot  # noqa: E402
from pipelines.historical_labeling.policies import load_policy  # noqa: E402


DEFAULT_CONFIG = Path("configs/research/abshodeh-historical-labeling-v1.json")
DEFAULT_MANIFEST = Path("data/manifests/committed_datasets.json")
DEFAULT_SUMMARY = Path(
    "docs/audits/artifacts/KAN-13-abshodeh-pilot-summary.json"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def _repository_path(value: str) -> Path:
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in value or ":" in value:
        raise ValueError("dataset path must be normalized and repository-relative")
    return REPOSITORY_ROOT.joinpath(*candidate.parts)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.research:
        print("KAN-13 historical extraction requires explicit --research.", file=sys.stderr)
        return 2

    config_path = args.config if args.config.is_absolute() else REPOSITORY_ROOT / args.config
    manifest_path = (
        args.manifest if args.manifest.is_absolute() else REPOSITORY_ROOT / args.manifest
    )
    policy = load_policy(config_path)
    requested_dataset = args.dataset.as_posix() if args.dataset else policy.dataset.dataset_path
    if requested_dataset != policy.dataset.dataset_path:
        print("Dataset path does not match the approved policy.", file=sys.stderr)
        return 2
    try:
        dataset_path = _repository_path(requested_dataset)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matches = [
        record
        for record in manifest.get("datasets", [])
        if record.get("path") == policy.dataset.dataset_path
    ]
    if len(matches) != 1:
        print("Approved dataset requires exactly one manifest record.", file=sys.stderr)
        return 1
    record = matches[0]
    if hashlib.sha256(dataset_path.read_bytes()).hexdigest() != record["sha256"]:
        print("Approved dataset hash differs from committed manifest.", file=sys.stderr)
        return 1

    table = pd.read_csv(dataset_path)

    def forbidden_eligible_path() -> None:
        raise AssertionError(
            "selected pilot unexpectedly passed KAN-10; reviewed eligible extraction is absent"
        )

    execution = run_gated_pilot(
        table,
        manifest=manifest,
        manifest_record=record,
        policy=policy,
        on_eligible=forbidden_eligible_path,
    )
    content = execution.summary.to_json_bytes()
    output = (
        args.summary_output
        if args.summary_output.is_absolute()
        else REPOSITORY_ROOT / args.summary_output
    )
    if args.check:
        if not output.is_file() or output.read_bytes() != content:
            print("KAN-13 blocked-pilot audit summary is missing or stale.")
            return 1
        print(f"KAN-13 pilot: {execution.summary.status.value}; summary is current.")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.read_bytes() == content:
        state = "unchanged"
    else:
        output.write_bytes(content)
        state = "written"
    print(f"KAN-13 pilot: {execution.summary.status.value}; summary {state}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
