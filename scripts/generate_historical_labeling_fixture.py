"""Generate or verify deterministic KAN-13 synthetic fixture evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from pipelines.historical_labeling.artifact import build_fixture_artifact  # noqa: E402
from pipelines.historical_labeling.policies import load_policy  # noqa: E402


DEFAULT_CONFIG = Path("configs/research/abshodeh-historical-labeling-v1.json")
DEFAULT_OUTPUT = Path(
    "docs/audits/artifacts/KAN-13-market-event-labeling-fixture.json"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = args.config if args.config.is_absolute() else REPOSITORY_ROOT / args.config
    output = args.output if args.output.is_absolute() else REPOSITORY_ROOT / args.output
    content = build_fixture_artifact(load_policy(config)).to_json_bytes()
    if args.check:
        if not output.is_file() or output.read_bytes() != content:
            print("KAN-13 fixture artifact is missing or stale.")
            return 1
        print("KAN-13 fixture artifact is current.")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.read_bytes() == content:
        print("KAN-13 fixture artifact unchanged.")
        return 0
    output.write_bytes(content)
    print("KAN-13 fixture artifact written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
