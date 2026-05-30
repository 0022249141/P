from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.data_ingestion import DataIngestionService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data_clean")
    parser.add_argument("--output", default="output_fixed/data_quality_audit.csv")
    parser.add_argument("--min-quality", type=float, default=0.0)
    args = parser.parse_args()

    data_dir = (ROOT / args.data_dir).resolve()
    output_path = (ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    service = DataIngestionService(data_dir)
    rows = service.audit_directory(min_quality_score=args.min_quality)

    report = pd.DataFrame(rows)
    report.to_csv(output_path, index=False, encoding="utf-8-sig")

    total = len(report)
    ok = int((report["status"] == "ok").sum()) if total else 0
    failed = total - ok

    print("=" * 80)
    print(f"Data directory: {data_dir}")
    print(f"Audit output:   {output_path}")
    print(f"Total files:    {total}")
    print(f"OK:             {ok}")
    print(f"Failed:         {failed}")
    print("=" * 80)

    if total:
        cols = [
            "file",
            "status",
            "market",
            "timeframe",
            "rows",
            "quality_score",
            "integrity_score",
            "warnings",
        ]
        print(report[cols].to_string(index=False))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())