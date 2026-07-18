"""Generate or verify the deterministic KAN-11 characterization artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from pipelines.characterization import build_characterization_artifact, render_artifact


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("docs/audits/artifacts/KAN-11-structure-liquidity-comparison.json")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed bytes without writing files.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output if args.output.is_absolute() else REPOSITORY_ROOT / args.output
    content = render_artifact(build_characterization_artifact(REPOSITORY_ROOT))

    if args.check:
        if not output.is_file() or output.read_bytes() != content:
            print("KAN-11 characterization artifact is missing or stale.")
            return 1
        print("KAN-11 characterization artifact is current.")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.read_bytes() == content:
        print("KAN-11 characterization artifact unchanged.")
        return 0
    output.write_bytes(content)
    print("KAN-11 characterization artifact written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
