"""Build the deterministic KAN-11 structure/liquidity audit artifact."""

from __future__ import annotations

from pathlib import Path

from pipelines.characterization.comparisons import _comparisons
from pipelines.characterization.contracts import Artifact
from pipelines.characterization.fixtures import fixture_catalog, fixture_evidence
from pipelines.characterization.liquidity_adapters import (
    _freeze_layer3_liquidity,
    _freeze_simple_liquidity,
    _freeze_zone_engine,
)
from pipelines.characterization.source_audit import (
    EXPECTED_SOURCE_SHA256,
    scan_temporal_patterns,
)
from pipelines.characterization.structure_adapters import (
    _freeze_layer2_structure,
    _freeze_simple_structure,
)


def build_characterization_artifact(root: Path) -> Artifact:
    """Freeze every implementation independently, then compare snapshots."""

    repository_root = root.resolve()
    fixtures = fixture_catalog()
    snapshots = (
        _freeze_simple_structure(
            repository_root,
            fixtures,
            implementation="legacy-structure",
            module_name="pipelines.legacy.03_structure",
            right_confirmation=2,
            has_bos=True,
        ),
        _freeze_simple_structure(
            repository_root,
            fixtures,
            implementation="vector-structure",
            module_name="src.structure_engine",
            right_confirmation=1,
            has_bos=False,
        ),
        _freeze_layer2_structure(repository_root, fixtures),
        _freeze_simple_liquidity(
            repository_root,
            fixtures,
            implementation="legacy-liquidity",
            module_name="pipelines.legacy.04_liquidity",
        ),
        _freeze_simple_liquidity(
            repository_root,
            fixtures,
            implementation="vector-liquidity",
            module_name="src.liquidity_engine",
        ),
        _freeze_layer3_liquidity(repository_root, fixtures),
        _freeze_zone_engine(repository_root),
    )
    return Artifact(
        fixtures=fixture_evidence(fixtures),
        implementation_snapshots=tuple(
            sorted(snapshots, key=lambda item: item.implementation_identifier)
        ),
        comparisons=_comparisons(),
        limitations=(
            "Characterization freezes observed software behavior on synthetic fixtures; it does not prove universal equivalence or market validity.",
            "MSS, reclaimed/accepted lifecycle states, and destination ranking remain BLOCKED_BY_MISSING_SEMANTICS.",
            "Simple structure and liquidity thresholds use complete-frame ATR means and are not real-time eligible.",
            "Layer2 BOS/CHoCH uses wick penetration, which diverges from the governed close-based definition.",
            "Layer3 sweeps require the next candle but are written at the raid row; downstream eligibility begins at confirmation.",
            "Resting liquidity is derived from a complete sweep list without an as-of timestamp and cannot be promoted to a historical lifecycle state.",
            "OHLCV-based BSL/SSL labels are deterministic proxies and do not evidence actual resting orders.",
            "G6-G9 remain NOT_EVALUATED; this artifact does not establish analytical, statistical, or execution readiness.",
        ),
    )


def render_artifact(artifact: Artifact) -> bytes:
    return artifact.to_json_bytes()


__all__ = [
    "EXPECTED_SOURCE_SHA256",
    "build_characterization_artifact",
    "render_artifact",
    "scan_temporal_patterns",
]
