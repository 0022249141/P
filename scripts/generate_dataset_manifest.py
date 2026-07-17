"""Generate the committed dataset manifest deterministically."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from core.dataset_manifest import (  # noqa: E402
    DatasetManifestError,
    build_manifest,
    write_manifest,
)


DEFAULT_MANIFEST_PATH = Path("data/manifests/committed_datasets.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        manifest = build_manifest(root)
        changed = write_manifest(output, manifest)
    except (DatasetManifestError, OSError, UnicodeError, csv.Error) as exc:
        print(f"Dataset manifest generation failed: {exc}", file=sys.stderr)
        return 1

    state = "Wrote" if changed else "Unchanged"
    print(f"{state}: {output} ({manifest['record_count']} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
