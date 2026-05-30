from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


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


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="output_fixed/data_quality_audit.csv")
    parser.add_argument("--summary", default="output_fixed/pipeline_v3_summary.csv")
    parser.add_argument("--validation", default="output_fixed/pipeline_v3_validation_report.csv")
    parser.add_argument("--output", default="output_fixed/workflow_run_manifest.json")
    args = parser.parse_args()

    audit_path = (ROOT / args.audit).resolve()
    summary_path = (ROOT / args.summary).resolve()
    validation_path = (ROOT / args.validation).resolve()
    output_path = (ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    audit = read_csv(audit_path)
    summary = read_csv(summary_path)
    validation = read_csv(validation_path)

    audit_total = int(len(audit))
    audit_ok = int((audit["status"] == "ok").sum()) if "status" in audit.columns else 0
    audit_failed = audit_total - audit_ok

    pipeline_total = int(len(summary))
    pipeline_ok = int((summary["status"] == "ok").sum()) if "status" in summary.columns else 0
    pipeline_failed = pipeline_total - pipeline_ok

    validation_total = int(len(validation))
    validation_ok = int((validation["validation_status"] == "ok").sum()) if "validation_status" in validation.columns else 0
    validation_failed = validation_total - validation_ok

    total_signals = int(summary["signals"].sum()) if "signals" in summary.columns else 0
    total_trades = int(summary["trades"].sum()) if "trades" in summary.columns else 0
    total_long = int(summary["long"].sum()) if "long" in summary.columns else 0
    total_short = int(summary["short"].sum()) if "short" in summary.columns else 0

    markets = sorted(summary["market"].dropna().unique().tolist()) if "market" in summary.columns else []
    timeframes = sorted(summary["timeframe"].dropna().unique().tolist()) if "timeframe" in summary.columns else []

    final_status = "ok" if audit_failed == 0 and pipeline_failed == 0 and validation_failed == 0 else "failed"

    manifest = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT),
        "git": {
            "branch": git_value(["branch", "--show-current"]),
            "commit": git_value(["rev-parse", "--short", "HEAD"]),
            "commit_full": git_value(["rev-parse", "HEAD"]),
            "working_tree_status": git_value(["status", "--short"]),
        },
        "reports": {
            "audit": str(audit_path),
            "pipeline_summary": str(summary_path),
            "validation": str(validation_path),
            "manifest": str(output_path),
        },
        "audit": {
            "total_files": audit_total,
            "ok": audit_ok,
            "failed": audit_failed,
        },
        "pipeline": {
            "total_outputs": pipeline_total,
            "ok": pipeline_ok,
            "failed": pipeline_failed,
            "markets": markets,
            "timeframes": timeframes,
            "signals": total_signals,
            "trades": total_trades,
            "long": total_long,
            "short": total_short,
        },
        "validation": {
            "checked_outputs": validation_total,
            "ok": validation_ok,
            "failed": validation_failed,
        },
        "final_status": final_status,
    }

    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("=" * 100)
    print(f"Workflow manifest written: {output_path}")
    print(f"Final status: {final_status}")
    print(f"Audit:      {audit_ok}/{audit_total} OK")
    print(f"Pipeline:   {pipeline_ok}/{pipeline_total} OK")
    print(f"Validation: {validation_ok}/{validation_total} OK")
    print(f"Signals:    {total_signals}")
    print(f"Trades:     {total_trades} | Long={total_long} | Short={total_short}")
    print("=" * 100)

    return 0 if final_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
