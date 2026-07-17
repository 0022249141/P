"""Explicit local live-price simulator with no import-time file access."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Sequence

import pandas as pd


DEFAULT_XAU_PATH = Path("data") / "XAU_USD-15.csv"
DEFAULT_ABSHODE_PATH = Path("data") / "abshodeNaghdi-15.csv"
DEFAULT_OUTPUT_PATH = Path("live_prices.json")


def build_live_snapshot(
    xau_path: str | Path,
    abshode_path: str | Path,
    rng: random.Random | None = None,
) -> dict[str, dict[str, float]]:
    """Read source rows on demand and build one simulated price snapshot."""

    generator = rng or random.Random()
    xau = pd.read_csv(xau_path).iloc[-1]
    abshode = pd.read_csv(abshode_path).iloc[-1]

    xau_price = xau["close"] * (1 + generator.uniform(-0.001, 0.001))
    abshode_price = abshode["close"] * (1 + generator.uniform(-0.001, 0.001))

    return {
        "xauusd": {
            "price": round(float(xau_price), 2),
            "change_pct": round(float((xau_price - xau["close"]) / xau["close"] * 100), 2),
            "high": float(xau["high"]),
            "low": float(xau["low"]),
        },
        "abshode": {
            "price": round(float(abshode_price), 2),
            "change_pct": round(
                float((abshode_price - abshode["close"]) / abshode["close"] * 100),
                2,
            ),
            "high": float(abshode["high"]),
            "low": float(abshode["low"]),
        },
    }


def update_live_prices(
    xau_path: str | Path = DEFAULT_XAU_PATH,
    abshode_path: str | Path = DEFAULT_ABSHODE_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    rng: random.Random | None = None,
) -> dict[str, dict[str, float]]:
    """Build and persist one snapshot after an explicit call."""

    snapshot = build_live_snapshot(xau_path, abshode_path, rng=rng)
    with Path(output_path).open("w", encoding="utf-8") as output:
        json.dump(snapshot, output, ensure_ascii=False)
    return snapshot


def serve(
    xau_path: str | Path = DEFAULT_XAU_PATH,
    abshode_path: str | Path = DEFAULT_ABSHODE_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    interval_seconds: float = 30.0,
) -> None:
    """Continuously update the local snapshot until interrupted."""

    while True:
        snapshot = update_live_prices(xau_path, abshode_path, output_path)
        print(
            f"Updated XAU={snapshot['xauusd']['price']:.2f}, "
            f"Abshode={snapshot['abshode']['price']:.2f}"
        )
        time.sleep(interval_seconds)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xau-path", type=Path, default=DEFAULT_XAU_PATH)
    parser.add_argument("--abshode-path", type=Path, default=DEFAULT_ABSHODE_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    serve(
        xau_path=args.xau_path,
        abshode_path=args.abshode_path,
        output_path=args.output_path,
        interval_seconds=args.interval_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
