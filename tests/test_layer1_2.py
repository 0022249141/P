from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from market_engine import MarketDataEngine
from structure_engine import StructuralEngine


def test_layer1_and_structure_smoke_use_synthetic_fixture(tmp_path: Path) -> None:
    """Pytest collection must not depend on a local data/ directory."""

    fixture_path = tmp_path / "synthetic_ohlcv.csv"
    rows = []
    for idx in range(120):
        base = 100.0 + idx * 0.1
        rows.append(
            {
                "timestamp": (pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=idx)).isoformat(),
                "open": base,
                "high": base + 1.0,
                "low": base - 1.0,
                "close": base + 0.2,
                "volume": 1000 + idx,
            }
        )
    pd.DataFrame(rows).to_csv(fixture_path, index=False)

    engine = MarketDataEngine.from_custom_csv(str(fixture_path))
    assert len(engine.df) == 120
    assert {"timestamp", "tr", "ATR14", "avg_volume_20"}.issubset(engine.df.columns)
    assert engine.get_regime(0) == "NORMAL"

    struct = StructuralEngine(engine)
    struct.detect_swings(window=5)

    assert len(struct.df) == len(engine.df)
    assert {"swing_high", "swing_low"}.issubset(struct.df.columns)
