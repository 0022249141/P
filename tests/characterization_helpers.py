from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pipelines.characterization import Artifact, ImplementationSnapshot
from pipelines.characterization.structure_liquidity import build_characterization_artifact


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def artifact() -> Artifact:
    return build_characterization_artifact(REPOSITORY_ROOT)


def snapshot(identifier: str) -> ImplementationSnapshot:
    return next(
        item
        for item in artifact().implementation_snapshots
        if item.implementation_identifier == identifier
    )
