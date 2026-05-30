from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def copy_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False

    target.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)

    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output_fixed")
    parser.add_argument("--archive-root", default="output_fixed/run_history")
    args = parser.parse_args()

    output_dir = (ROOT / args.output_dir).resolve()
    archive_root = (ROOT / args.archive_root).resolve()

    commit = git_value(["rev-parse", "--short", "HEAD"]) or "nogit"
    branch = git_value(["branch", "--show-current"]) or "unknown_branch"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")

    run_dir = archive_root / f"{timestamp}_{branch}_{commit}"
    run_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "data_quality_audit": output_dir / "data_quality_audit.csv",
        "pipeline_summary": output_dir / "pipeline_v3_summary.csv",
        "validation_report": output_dir / "pipeline_v3_validation_report.csv",
        "workflow_manifest": output_dir / "workflow_run_manifest.json",
        "pipeline_outputs": output_dir / "pipeline_v3",
    }

    copied = {}
    for name, source in artifacts.items():
        target = run_dir / source.name
        copied[name] = {
            "source": str(source),
            "target": str(target),
            "copied": copy_if_exists(source, target),
        }

    archive_manifest = {
        "archive_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT),
        "archive_dir": str(run_dir),
        "git": {
            "branch": branch,
            "commit": commit,
            "commit_full": git_value(["rev-parse", "HEAD"]),
            "working_tree_status": git_value(["status", "--short"]),
        },
        "artifacts": copied,
    }

    archive_manifest_path = run_dir / "archive_manifest.json"
    archive_manifest_path.write_text(
        json.dumps(archive_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("=" * 100)
    print(f"Run archive created: {run_dir}")
    print(f"Archive manifest:    {archive_manifest_path}")
    for name, item in copied.items():
        status = "OK" if item["copied"] else "MISSING"
        print(f"{name}: {status}")
    print("=" * 100)

    missing = [name for name, item in copied.items() if not item["copied"]]
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
