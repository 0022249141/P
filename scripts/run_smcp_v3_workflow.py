from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, command: list[str]) -> int:
    print("\n" + "=" * 100)
    print(f"STEP: {name}")
    print("COMMAND:")
    print(" ".join(command))
    print("=" * 100)

    result = subprocess.run(command, cwd=ROOT)

    if result.returncode != 0:
        print("\n" + "!" * 100)
        print(f"FAILED STEP: {name}")
        print(f"Return code: {result.returncode}")
        print("!" * 100)
        return result.returncode

    print(f"\nOK: {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data_clean")
    parser.add_argument("--output-dir", default="output_fixed")
    parser.add_argument("--timeframes", nargs="*", default=["5", "15", "30", "60", "240", "1D"])
    parser.add_argument("--tail-rows", type=int, default=5000)
    args = parser.parse_args()

    python = sys.executable

    audit_output = f"{args.output_dir}/data_quality_audit.csv"
    pipeline_summary = f"{args.output_dir}/pipeline_v3_summary.csv"
    validation_output = f"{args.output_dir}/pipeline_v3_validation_report.csv"

    steps = [
        (
            "Data quality audit",
            [
                python,
                "scripts/run_data_quality_audit.py",
                "--data-dir",
                args.data_dir,
                "--output",
                audit_output,
            ],
        ),
        (
            "SMCP V3 pipeline run",
            [
                python,
                "scripts/run_smcp_v3_pipeline.py",
                "--data-dir",
                args.data_dir,
                "--output-dir",
                args.output_dir,
                "--timeframes",
                *args.timeframes,
                "--tail-rows",
                str(args.tail_rows),
            ],
        ),
        (
            "Pipeline output validation",
            [
                python,
                "scripts/validate_pipeline_outputs.py",
                "--summary",
                pipeline_summary,
                "--output",
                validation_output,
            ],
        ),
    ]

    for name, command in steps:
        code = run_step(name, command)
        if code != 0:
            return code

    print("\n" + "=" * 100)
    print("SMCP V3 WORKFLOW COMPLETED SUCCESSFULLY")
    print(f"Audit report:      {ROOT / audit_output}")
    print(f"Pipeline summary:  {ROOT / pipeline_summary}")
    print(f"Validation report: {ROOT / validation_output}")
    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())