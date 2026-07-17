"""Verify tracked repository hygiene and report dataset integrity evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Sequence


FORBIDDEN_DIRECTORY_NAMES = {
    ".pytest_cache",
    ".venv",
    ".vs",
    "__pycache__",
    "build",
    "dist",
    "venv",
}
FORBIDDEN_TRACKED_FILES = {"live_prices.json", "project_tree.txt"}
DATASET_DIRECTORIES = ("raw_data", "data_clean", "data_features")
IGNORE_PROBES = (
    "venv/probe.txt",
    "nested/.venv/probe.txt",
    "nested/.vs/probe.db",
    "nested/__pycache__/probe.pyc",
    "nested/.pytest_cache/probe",
    "nested/build/probe.whl",
    "nested/dist/probe.whl",
    "nested/package.egg-info/PKG-INFO",
    "live_prices.json",
    "project_tree.txt",
)


def run_git(
    *args: str,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {message}")
    return result


def repository_root() -> Path:
    output = run_git("rev-parse", "--show-toplevel").stdout
    return Path(output.decode("utf-8").strip())


def index_entries(root: Path) -> list[tuple[str, str, str]]:
    raw = run_git("ls-files", "--stage", "-z", cwd=root).stdout
    entries: list[tuple[str, str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", maxsplit=1)
        mode, object_id, stage = metadata.decode("ascii").split()
        if stage != "0":
            raise RuntimeError("Unmerged index entries prevent hygiene verification")
        entries.append(
            (mode, object_id, raw_path.decode("utf-8", errors="surrogateescape"))
        )
    return entries


def tracked_blob_bytes(entries: list[tuple[str, str, str]], root: Path) -> int:
    object_ids = sorted({object_id for mode, object_id, _ in entries if mode != "160000"})
    if not object_ids:
        return 0
    request = ("\n".join(object_ids) + "\n").encode("ascii")
    output = run_git(
        "cat-file",
        "--batch-check=%(objectname) %(objectsize)",
        cwd=root,
        input_bytes=request,
    ).stdout.decode("ascii")
    sizes = {
        object_id: int(size)
        for object_id, size in (line.split() for line in output.splitlines())
    }
    return sum(sizes[object_id] for mode, object_id, _ in entries if mode != "160000")


def is_forbidden(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if any(part in FORBIDDEN_DIRECTORY_NAMES for part in parts):
        return True
    if any(part.endswith(".egg-info") for part in parts):
        return True
    return path in FORBIDDEN_TRACKED_FILES


def ignored_probe_failures(root: Path) -> list[str]:
    failures = []
    for path in IGNORE_PROBES:
        result = run_git("check-ignore", "--quiet", "--no-index", path, cwd=root, check=False)
        if result.returncode != 0:
            failures.append(path)
    return failures


def dataset_summary(root: Path) -> dict[str, int | str]:
    raw = run_git("ls-files", "-z", "--", *DATASET_DIRECTORIES, cwd=root).stdout
    paths = sorted(
        (
            item.decode("utf-8", errors="surrogateescape")
            for item in raw.split(b"\0")
            if item
        ),
        key=str.casefold,
    )
    total_bytes = 0
    manifest_lines = []
    for path in paths:
        payload = (root / path).read_bytes()
        total_bytes += len(payload)
        digest = hashlib.sha256(payload).hexdigest()
        manifest_lines.append(f"{digest}  {path}\n")
    manifest = "".join(manifest_lines).encode("utf-8")
    return {
        "path_count": len(paths),
        "bytes": total_bytes,
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
    }


def build_report(root: Path, *, skip_dataset_integrity: bool = False) -> dict[str, object]:
    """Build the hygiene report, optionally without reading dataset content."""

    entries = index_entries(root)
    paths = [path for _, _, path in entries]
    violations = sorted(path for path in paths if is_forbidden(path))
    ignore_failures = ignored_probe_failures(root)
    gitlinks = sorted(path for mode, _, path in entries if mode == "160000")
    submodules = run_git("submodule", "status", "--recursive", cwd=root, check=False)

    report: dict[str, object] = {
        "tracked_file_count": len(entries),
        "tracked_blob_bytes": tracked_blob_bytes(entries, root),
        "forbidden_tracked_paths": violations,
        "ignore_probe_failures": ignore_failures,
        "gitlinks": gitlinks,
        "submodule_status_exit_code": submodules.returncode,
        "datasets": (
            {"status": "skipped"}
            if skip_dataset_integrity
            else dataset_summary(root)
        ),
    }
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-dataset-integrity",
        action="store_true",
        help="Run Git hygiene checks without opening or hashing protected CSV files.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = repository_root()
    report = build_report(root, skip_dataset_integrity=args.skip_dataset_integrity)
    print(json.dumps(report, indent=2, sort_keys=True))

    if (
        report["forbidden_tracked_paths"]
        or report["ignore_probe_failures"]
        or report["submodule_status_exit_code"] != 0
    ):
        submodules = run_git("submodule", "status", "--recursive", cwd=root, check=False)
        if submodules.stderr:
            print(submodules.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
