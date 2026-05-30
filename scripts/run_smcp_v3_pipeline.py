from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.data_ingestion import DataIngestionService

adaptive_sweep_mod = importlib.import_module("adaptive_sweep")
disp_mod = importlib.import_module("pipelines.legacy.08_displacement")
zone_mod = importlib.import_module("pipelines.legacy.09_zone_scoring")
state_mod = importlib.import_module("pipelines.legacy.10_state_machine")
exec_mod = importlib.import_module("pipelines.legacy.11_execution")

AdaptiveSweepDetector = adaptive_sweep_mod.AdaptiveSweepDetector
detect_displacement = disp_mod.detect_displacement
score_order_blocks = zone_mod.score_order_blocks
score_breakers_vectorized = zone_mod.score_breakers_vectorized
compute_setup_score = zone_mod.compute_setup_score
apply_state_machine = state_mod.apply_state_machine
compute_trade_parameters = exec_mod.compute_trade_parameters


def prepare_legacy_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    df["ATR14"] = true_range.ewm(span=14, min_periods=14, adjust=False).mean()
    df["ATR14"] = df["ATR14"].bfill().fillna(true_range.mean())
    df["atr"] = df["ATR14"]
    df["avg_volume_20"] = df["volume"].rolling(20, min_periods=1).mean()

    window = 5
    rolling_high = df["high"].rolling(window * 2 + 1, center=True, min_periods=window + 1).max()
    rolling_low = df["low"].rolling(window * 2 + 1, center=True, min_periods=window + 1).min()

    df["swing_high"] = 0.0
    df["swing_low"] = 0.0
    df.loc[df["high"].eq(rolling_high), "swing_high"] = df["high"]
    df.loc[df["low"].eq(rolling_low), "swing_low"] = df["low"]

    return df


def run_one_file(service: DataIngestionService, csv_path: Path, output_dir: Path, tail_rows: int) -> dict:
    loaded = service.load_file(csv_path)
    df = loaded.dataframe

    if tail_rows > 0 and len(df) > tail_rows:
        df = df.tail(tail_rows).reset_index(drop=True)

    df = prepare_legacy_features(df)

    detector = AdaptiveSweepDetector()
    df = detector.detect(df)
    df = detect_displacement(df)
    df = score_order_blocks(df)
    df = score_breakers_vectorized(df)
    df = compute_setup_score(df)
    df = apply_state_machine(df)

    market_dir = output_dir / "pipeline_v3" / loaded.market.value
    market_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{loaded.market.value}_{loaded.timeframe.value}"
    final_path = market_dir / f"final_{base_name}.csv"
    trades_path = market_dir / f"execution_plan_{base_name}.csv"

    df.to_csv(final_path, index=False, encoding="utf-8-sig")

    trades = compute_trade_parameters(
        df,
        risk_percent=1.0,
        account_balance=10000,
        atr_sl_mult=1.5,
        rr_ratio=1.5,
    )
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")

    long_count = int((trades["direction"] == "LONG").sum()) if "direction" in trades.columns else 0
    short_count = int((trades["direction"] == "SHORT").sum()) if "direction" in trades.columns else 0
    signals = int((df["entry_signal"] != 0).sum()) if "entry_signal" in df.columns else 0

    return {
        "file": csv_path.name,
        "market": loaded.market.value,
        "timeframe": loaded.timeframe.value,
        "rows_in": len(df),
        "signals": signals,
        "trades": len(trades),
        "long": long_count,
        "short": short_count,
        "final_output": str(final_path),
        "trades_output": str(trades_path),
        "status": "ok",
        "error": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data_clean")
    parser.add_argument("--output-dir", default="output_fixed")
    parser.add_argument("--timeframes", nargs="*", default=["15"])
    parser.add_argument("--tail-rows", type=int, default=5000)
    args = parser.parse_args()

    data_dir = (ROOT / args.data_dir).resolve()
    output_dir = (ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    service = DataIngestionService(data_dir)

    selected_files = []
    for tf in args.timeframes:
        selected_files.extend(sorted(data_dir.glob(f"*-{tf}.csv")))

    if not selected_files:
        print(f"No files found for timeframes={args.timeframes} in {data_dir}")
        return 1

    rows = []

    print("=" * 100)
    print("SMCP V3 pipeline runner")
    print(f"Data dir:   {data_dir}")
    print(f"Output dir: {output_dir}")
    print(f"Timeframes: {args.timeframes}")
    print(f"Tail rows:  {args.tail_rows}")
    print("=" * 100)

    for csv_path in selected_files:
        print(f"\nProcessing: {csv_path.name}")
        try:
            result = run_one_file(service, csv_path, output_dir, args.tail_rows)
            print(
                f"OK | rows={result['rows_in']} | signals={result['signals']} | "
                f"trades={result['trades']} | L={result['long']} | S={result['short']}"
            )
            rows.append(result)
        except Exception as exc:
            print(f"FAILED | {csv_path.name} | {exc}")
            rows.append(
                {
                    "file": csv_path.name,
                    "market": "",
                    "timeframe": "",
                    "rows_in": 0,
                    "signals": 0,
                    "trades": 0,
                    "long": 0,
                    "short": 0,
                    "final_output": "",
                    "trades_output": "",
                    "status": "failed",
                    "error": str(exc),
                }
            )

    summary = pd.DataFrame(rows)
    summary_path = output_dir / "pipeline_v3_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 100)
    print(f"Summary saved: {summary_path}")
    print(summary[["file", "status", "rows_in", "signals", "trades", "long", "short", "error"]].to_string(index=False))
    print("=" * 100)

    return 0 if (summary["status"] == "ok").all() else 1


if __name__ == "__main__":
    raise SystemExit(main())