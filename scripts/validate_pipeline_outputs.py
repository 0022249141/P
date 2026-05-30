from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SUMMARY_COLUMNS = {
    "file",
    "market",
    "timeframe",
    "rows_in",
    "signals",
    "trades",
    "final_output",
    "trades_output",
    "status",
}

REQUIRED_FINAL_COLUMNS = {
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def check_file(path_value: str) -> tuple[bool, str]:
    path = Path(path_value)
    if not path.exists():
        return False, f"missing file: {path}"
    if path.stat().st_size == 0:
        return False, f"empty file: {path}"
    return True, ""


def validate_final_output(path_value: str) -> tuple[bool, str, int]:
    ok, error = check_file(path_value)
    if not ok:
        return False, error, 0

    df = pd.read_csv(path_value)
    if df.empty:
        return False, "final output is empty", 0

    missing_cols = REQUIRED_FINAL_COLUMNS.difference(df.columns)
    if missing_cols:
        return False, f"missing final columns: {sorted(missing_cols)}", len(df)

    numeric_cols = ["open", "high", "low", "close", "volume"]
    bad_cells = int(df[numeric_cols].isna().sum().sum())
    if bad_cells:
        return False, f"final output has NaN numeric cells: {bad_cells}", len(df)

    return True, "", len(df)


def validate_execution_plan(path_value: str, expected_trades: int) -> tuple[bool, str, int]:
    ok, error = check_file(path_value)
    if not ok:
        return False, error, 0

    df = pd.read_csv(path_value)
    actual_trades = len(df)

    if actual_trades != expected_trades:
        return False, f"trade count mismatch: expected={expected_trades}, actual={actual_trades}", actual_trades

    if expected_trades > 0 and "direction" in df.columns:
        invalid_direction = ~df["direction"].isin(["LONG", "SHORT"])
        invalid_count = int(invalid_direction.sum())
        if invalid_count:
            return False, f"invalid directions: {invalid_count}", actual_trades

    return True, "", actual_trades


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="output_fixed/pipeline_v3_summary.csv")
    parser.add_argument("--output", default="output_fixed/pipeline_v3_validation_report.csv")
    args = parser.parse_args()

    summary_path = (ROOT / args.summary).resolve()
    output_path = (ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not summary_path.exists():
        print(f"Missing summary file: {summary_path}")
        return 1

    summary = pd.read_csv(summary_path)

    missing_summary_cols = REQUIRED_SUMMARY_COLUMNS.difference(summary.columns)
    if missing_summary_cols:
        print(f"Summary missing columns: {sorted(missing_summary_cols)}")
        return 1

    rows = []

    for _, row in summary.iterrows():
        final_ok, final_error, final_rows = validate_final_output(str(row["final_output"]))
        trades_ok, trades_error, trade_rows = validate_execution_plan(
            str(row["trades_output"]),
            int(row["trades"]),
        )

        validation_status = "ok" if final_ok and trades_ok and row["status"] == "ok" else "failed"

        rows.append(
            {
                "file": row["file"],
                "market": row["market"],
                "timeframe": row["timeframe"],
                "summary_status": row["status"],
                "validation_status": validation_status,
                "summary_rows": int(row["rows_in"]),
                "final_rows": int(final_rows),
                "summary_trades": int(row["trades"]),
                "trade_rows": int(trade_rows),
                "final_error": final_error,
                "trades_error": trades_error,
            }
        )

    report = pd.DataFrame(rows)
    report.to_csv(output_path, index=False, encoding="utf-8-sig")

    failed = report[report["validation_status"] != "ok"]

    print("=" * 100)
    print(f"Summary: {summary_path}")
    print(f"Validation report: {output_path}")
    print(f"Checked outputs: {len(report)}")
    print(f"Failed: {len(failed)}")
    print("=" * 100)
    print(report.to_string(index=False))

    return 0 if failed.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())