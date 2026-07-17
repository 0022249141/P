"""Verify the committed dataset manifest without writing any files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from core.dataset_manifest import verify_manifest  # noqa: E402


DEFAULT_MANIFEST_PATH = Path("data/manifests/committed_datasets.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = verify_manifest(args.root, args.manifest)
    if errors:
        print("Dataset manifest verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Dataset manifest verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
