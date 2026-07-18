from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from pipelines.characterization import ComparisonClassification, render_artifact
from tests.characterization_helpers import REPOSITORY_ROOT, artifact


ARTIFACT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "audits"
    / "artifacts"
    / "KAN-11-structure-liquidity-comparison.json"
)


def test_artifact_is_current_and_byte_deterministic() -> None:
    first = render_artifact(artifact())
    second = render_artifact(artifact().model_copy(deep=True))

    assert first == second
    assert ARTIFACT_PATH.read_bytes() == first


def test_generator_twice_has_zero_second_run_diff(tmp_path) -> None:
    output = tmp_path / "comparison.json"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
    command = [
        sys.executable,
        str(REPOSITORY_ROOT / "scripts" / "generate_structure_liquidity_characterization.py"),
        "--output",
        str(output),
    ]

    first = subprocess.run(command, cwd=REPOSITORY_ROOT, env=environment, check=False, capture_output=True, text=True)
    first_bytes = output.read_bytes()
    second = subprocess.run(command, cwd=REPOSITORY_ROOT, env=environment, check=False, capture_output=True, text=True)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == first_bytes
    assert "unchanged" in second.stdout


def test_artifact_contains_only_stable_repository_relative_evidence() -> None:
    payload = render_artifact(artifact())
    decoded = payload.decode("ascii")

    assert "C:\\" not in decoded
    assert str(REPOSITORY_ROOT).replace("\\", "/") not in decoded
    for forbidden in ("generated_at", "hostname", "username", "current_timestamp"):
        assert forbidden not in decoded
    parsed = json.loads(decoded)
    assert parsed["fixture_scope"] == "SYNTHETIC_ONLY"
    assert [item["fixture_id"] for item in parsed["fixtures"]] == sorted(
        item["fixture_id"] for item in parsed["fixtures"]
    )
    assert [item["implementation_identifier"] for item in parsed["implementation_snapshots"]] == sorted(
        item["implementation_identifier"] for item in parsed["implementation_snapshots"]
    )


def test_every_emitted_event_has_required_provenance_fields() -> None:
    required = {
        "implementation_identifier",
        "event_type",
        "direction",
        "origin_or_pivot_timestamp",
        "observation_timestamp",
        "confirmation_or_availability_timestamp",
        "first_downstream_eligible_timestamp",
        "observed_price_or_level",
        "eligibility_classification",
        "temporal_evidence",
        "source_fixture",
        "fixture_sha256",
    }
    for implementation in artifact().implementation_snapshots:
        for event in implementation.events:
            assert required <= set(event.model_dump())


def test_all_duplicate_pairs_have_approved_classifications() -> None:
    comparisons = artifact().comparisons
    pairs = {
        frozenset((item.left_implementation, item.right_implementation))
        for item in comparisons
    }

    assert {
        frozenset(("legacy-structure", "vector-structure")),
        frozenset(("legacy-structure", "layer2-structure")),
        frozenset(("vector-structure", "layer2-structure")),
        frozenset(("legacy-liquidity", "vector-liquidity")),
        frozenset(("legacy-liquidity", "layer3-liquidity")),
        frozenset(("legacy-liquidity", "zone-engine")),
        frozenset(("vector-liquidity", "layer3-liquidity")),
        frozenset(("vector-liquidity", "zone-engine")),
        frozenset(("layer3-liquidity", "zone-engine")),
    } <= pairs
    assert {item.classification for item in comparisons} == set(ComparisonClassification)


def test_characterization_imports_have_no_application_io_or_network_side_effects() -> None:
    modules = (
        "pipelines.characterization.contracts",
        "pipelines.characterization.fixtures",
        "pipelines.characterization.structure_liquidity",
        "pipelines.characterization",
    )
    script = r'''
import importlib
import pathlib
import socket
import pandas as pd

repository_root = pathlib.Path.cwd().resolve()
original_read_text = pathlib.Path.read_text
original_read_bytes = pathlib.Path.read_bytes

def blocked(*args, **kwargs):
    raise AssertionError("application I/O or network access during import")

def guarded_read_text(path, *args, **kwargs):
    resolved = path.resolve()
    if resolved.is_relative_to(repository_root):
        relative = resolved.relative_to(repository_root)
        packaging_metadata = any(part.endswith(".egg-info") for part in relative.parts)
        if not packaging_metadata and ".venv" not in relative.parts and resolved.suffix not in {".py", ".pyc"}:
            blocked()
    return original_read_text(path, *args, **kwargs)

def guarded_read_bytes(path, *args, **kwargs):
    resolved = path.resolve()
    if resolved.is_relative_to(repository_root):
        relative = resolved.relative_to(repository_root)
        packaging_metadata = any(part.endswith(".egg-info") for part in relative.parts)
        if not packaging_metadata and ".venv" not in relative.parts and resolved.suffix not in {".py", ".pyc"}:
            blocked()
    return original_read_bytes(path, *args, **kwargs)

pathlib.Path.read_text = guarded_read_text
pathlib.Path.read_bytes = guarded_read_bytes
pathlib.Path.write_text = blocked
pathlib.Path.write_bytes = blocked
pd.read_csv = blocked
pd.DataFrame.to_csv = blocked
socket.create_connection = blocked
socket.socket.connect = blocked

for module in %r:
    importlib.import_module(module)
print("import-safe")
''' % (modules,)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "import-safe"
