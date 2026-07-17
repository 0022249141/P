from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipelines.canonical import (
    DatasetIdentity,
    EvidenceStatus,
    GateFinding,
    GateId,
    GateReport,
    GateResult,
    GateStatus,
    PriceUnitDeclaration,
    VolumeMeaning,
    VolumeSemantics,
)


CANONICAL_MODULES = (
    "pipelines.canonical.contracts",
    "pipelines.canonical.normalization",
    "pipelines.canonical.quality",
    "pipelines.canonical.resampling",
    "pipelines.canonical.reconciliation",
    "pipelines.canonical.eligibility",
    "pipelines.canonical",
)


def test_gate_contracts_cover_g0_to_g9_and_allowed_states() -> None:
    assert [gate.value for gate in GateId] == [
        "G0_PROVENANCE",
        "G1_SCHEMA_PARSING",
        "G2_TEMPORAL_INTEGRITY",
        "G3_OHLC_NUMERIC",
        "G4_CALENDAR_COVERAGE",
        "G5_MTF_RECONCILIATION",
        "G6_FEATURE_REPRODUCTION",
        "G7_ANALYTICAL_ELIGIBILITY",
        "G8_STATISTICAL_ELIGIBILITY",
        "G9_EXECUTION_BACKTEST_ELIGIBILITY",
    ]
    assert {status.value for status in GateStatus} == {
        "PASS",
        "FAIL",
        "BLOCKED",
        "NOT_EVALUATED",
    }


def test_gate_result_requires_bounded_examples() -> None:
    with pytest.raises(ValidationError):
        GateResult(
            gate_id=GateId.G1_SCHEMA_PARSING,
            status=GateStatus.FAIL,
            reason_code="TOO_MANY_EXAMPLES",
            message="Bounded examples are required.",
            checked_record_count=20,
            affected_record_count=20,
            examples=tuple(str(index) for index in range(11)),
        )


def test_unknown_price_and_volume_semantics_cannot_claim_known_values() -> None:
    with pytest.raises(ValidationError):
        PriceUnitDeclaration(unit="USD", evidence_status=EvidenceStatus.UNKNOWN)
    with pytest.raises(ValidationError):
        PriceUnitDeclaration(strictly_positive=True)
    with pytest.raises(ValidationError):
        VolumeSemantics(
            meaning=VolumeMeaning.TICK,
            evidence_status=EvidenceStatus.UNKNOWN,
        )


def test_gate_report_serialization_is_stable_and_versioned() -> None:
    finding = GateFinding(
        reason_code="EXAMPLE",
        message="Example finding.",
        affected_record_count=1,
        examples=("row:1",),
    )
    result = GateResult(
        gate_id=GateId.G1_SCHEMA_PARSING,
        status=GateStatus.FAIL,
        reason_code="G1_FAILED",
        message="Schema failed.",
        checked_record_count=1,
        affected_record_count=1,
        examples=("row:1",),
        findings=(finding,),
    )
    report = GateReport(
        dataset=DatasetIdentity(dataset_id="synthetic"),
        results=(result,),
    )

    assert report.to_json_bytes() == report.model_copy(deep=True).to_json_bytes()
    assert b'"schema_version":"1.0.0"' in report.to_json_bytes()


def test_canonical_imports_have_no_application_io_or_network_side_effects() -> None:
    script = """
import importlib
import pathlib
import socket
import pandas as pd

repository_root = pathlib.Path.cwd().resolve()

def blocked(*args, **kwargs):
    raise AssertionError("application I/O or network access during import")

original_read_text = pathlib.Path.read_text
original_read_bytes = pathlib.Path.read_bytes

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

modules = %r
for module in modules:
    importlib.import_module(module)
print("import-safe")
""" % (CANONICAL_MODULES,)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "import-safe"


def test_canonical_modules_do_not_mutate_sys_path() -> None:
    root = Path(__file__).resolve().parents[1] / "pipelines" / "canonical"
    violations = []
    for module in sorted(root.glob("*.py")):
        source = module.read_text(encoding="utf-8")
        if "sys.path" in source:
            violations.append(module.name)

    assert violations == []
