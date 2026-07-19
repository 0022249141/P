from __future__ import annotations

import json
import os
import subprocess
import sys

from pipelines.historical_labeling.contracts import CensorReason, OutcomeClass
from tests.historical_labeling_helpers import (
    ARTIFACT_PATH,
    POLICY_PATH,
    REPOSITORY_ROOT,
    artifact,
)


def test_fixture_artifact_is_current_and_byte_deterministic() -> None:
    first = artifact().to_json_bytes()
    second = artifact().model_copy(deep=True).to_json_bytes()

    assert first == second
    assert ARTIFACT_PATH.read_bytes() == first


def test_generator_twice_has_zero_second_run_diff(tmp_path) -> None:
    output = tmp_path / "fixture.json"
    command = [
        sys.executable,
        str(REPOSITORY_ROOT / "scripts/generate_historical_labeling_fixture.py"),
        "--config",
        str(POLICY_PATH),
        "--output",
        str(output),
    ]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT)

    first = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    first_bytes = output.read_bytes()
    second = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == first_bytes
    assert "unchanged" in second.stdout


def test_artifact_matrix_is_complete_and_contains_only_stable_evidence() -> None:
    payload = artifact().to_json_bytes()
    decoded = payload.decode("ascii")
    parsed = json.loads(decoded)

    assert parsed["fixture_scope"] == "SYNTHETIC_ONLY"
    assert {item.observed_outcome for item in artifact().fixture_results} == set(
        OutcomeClass
    )
    assert {
        item.observed_censor_reason
        for item in artifact().fixture_results
        if item.observed_censor_reason is not None
    } == set(CensorReason)
    assert [item["fixture_id"] for item in parsed["fixture_results"]] == sorted(
        item["fixture_id"] for item in parsed["fixture_results"]
    )
    for forbidden in (
        "C:\\",
        str(REPOSITORY_ROOT).replace("\\", "/"),
        "generated_at",
        "hostname",
        "username",
        "current_timestamp",
    ):
        assert forbidden not in decoded


def test_feature_and_label_modules_have_one_way_namespace_separation() -> None:
    feature_source = (
        REPOSITORY_ROOT / "pipelines/historical_labeling/features.py"
    ).read_text(encoding="utf-8")
    label_source = (
        REPOSITORY_ROOT / "pipelines/historical_labeling/labels.py"
    ).read_text(encoding="utf-8")

    assert "historical_labeling.labels" not in feature_source
    assert "historical_labeling.features" not in label_source


def test_historical_labeling_imports_have_no_application_io_side_effects() -> None:
    modules = (
        "pipelines.historical_labeling.contracts",
        "pipelines.historical_labeling.policies",
        "pipelines.historical_labeling.fixtures",
        "pipelines.historical_labeling.artifact",
        "pipelines.historical_labeling.event_source",
        "pipelines.historical_labeling.features",
        "pipelines.historical_labeling.labels",
        "pipelines.historical_labeling.pilot",
        "pipelines.historical_labeling",
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
