from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from scripts import verify_git_hygiene


DATASET_DIRECTORIES = verify_git_hygiene.DATASET_DIRECTORIES


IGNORE_POLICY = """venv/
.venv/
.vs/
__pycache__/
.pytest_cache/
build/
dist/
*.egg-info/
live_prices.json
project_tree.txt
"""


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _temporary_repository(root: Path) -> Path:
    _git(root, "init", "--quiet")
    (root / ".gitignore").write_text(IGNORE_POLICY, encoding="utf-8")
    dataset = root / DATASET_DIRECTORIES[0] / "sample-5.csv"
    dataset.parent.mkdir(parents=True)
    dataset.write_bytes(b"timestamp,open,high,low,close,volume\n")
    _git(root, "add", ".")
    return dataset


def test_default_hygiene_report_retains_dataset_summary(tmp_path: Path) -> None:
    dataset = _temporary_repository(tmp_path)

    report = verify_git_hygiene.build_report(tmp_path)

    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    manifest_line = f"{digest}  {dataset.relative_to(tmp_path).as_posix()}\n"
    assert report["datasets"] == {
        "path_count": 1,
        "bytes": dataset.stat().st_size,
        "manifest_sha256": hashlib.sha256(manifest_line.encode()).hexdigest(),
    }


def test_skip_dataset_integrity_never_reads_dataset_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dataset = _temporary_repository(tmp_path).resolve()
    original_read_bytes = Path.read_bytes

    def reject_dataset_read(path: Path) -> bytes:
        if path.resolve() == dataset:
            raise AssertionError("skip mode attempted to read a protected dataset")
        return original_read_bytes(path)

    def reject_dataset_summary(root: Path) -> dict[str, object]:
        raise AssertionError(f"skip mode invoked dataset summary for {root}")

    monkeypatch.setattr(Path, "read_bytes", reject_dataset_read)
    monkeypatch.setattr(verify_git_hygiene, "dataset_summary", reject_dataset_summary)

    report = verify_git_hygiene.build_report(
        tmp_path,
        skip_dataset_integrity=True,
    )

    assert report["datasets"] == {"status": "skipped"}
    assert report["tracked_file_count"] == 2
    assert report["forbidden_tracked_paths"] == []
    assert report["ignore_probe_failures"] == []
    assert report["gitlinks"] == []
    assert report["submodule_status_exit_code"] == 0
