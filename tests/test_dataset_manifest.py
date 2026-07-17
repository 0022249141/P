from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from core.dataset_manifest import (
    EVIDENCE_STATUS_VALUES,
    PROTECTED_DIRECTORIES,
    build_manifest,
    render_manifest,
    verify_manifest,
    write_manifest,
)


CSV_CONTENT = """timestamp,open,high,low,close,volume
2024-01-01 00:00:00,10,12,9,11,100
2024-01-01 00:05:00,11,13,10,12,
"""


def _create_dataset(root: Path, name: str = "sample-5.csv") -> list[str]:
    relative_path = f"{PROTECTED_DIRECTORIES[0]}/{name}"
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CSV_CONTENT, encoding="utf-8", newline="")
    return [relative_path]


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_bytes(render_manifest(manifest))


def test_manifest_generation_is_deterministic_and_measures_content(tmp_path: Path) -> None:
    dataset_paths = _create_dataset(tmp_path)

    first = build_manifest(tmp_path, dataset_paths)
    second = build_manifest(tmp_path, dataset_paths)

    assert render_manifest(first) == render_manifest(second)
    record = first["datasets"][0]
    assert first["record_count"] == 1
    assert record["row_count"] == 2
    assert record["columns"] == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert record["missing_cell_count"] == 1
    assert record["duplicate_timestamp_count"] == 0
    assert record["first_timestamp"] == "2024-01-01 00:00:00"
    assert record["last_timestamp"] == "2024-01-01 00:05:00"
    assert record["timezone_status"] == "NAIVE_UNKNOWN"


def test_filename_semantics_are_inferred_and_unsupported_semantics_unknown(
    tmp_path: Path,
) -> None:
    dataset_paths = _create_dataset(tmp_path)
    record = build_manifest(tmp_path, dataset_paths)["datasets"][0]

    assert record["classification_evidence_status"] == "DECLARED"
    for field in ("market", "symbol", "timeframe"):
        assert record[field]["evidence_status"] == "INFERRED"
    for field in (
        "source",
        "timezone",
        "timestamp_period_semantics",
        "volume_meaning",
        "price_unit",
    ):
        assert record[field] == {"evidence_status": "UNKNOWN", "value": "UNKNOWN"}
    assert record["parser_decision"]["evidence_status"] == "DECLARED"
    assert EVIDENCE_STATUS_VALUES == {"OBSERVED", "DECLARED", "INFERRED", "UNKNOWN"}


def test_generator_write_is_unchanged_on_second_run(tmp_path: Path) -> None:
    manifest = build_manifest(tmp_path, _create_dataset(tmp_path))
    manifest_path = tmp_path / "manifest.json"

    assert write_manifest(manifest_path, manifest) is True
    first_bytes = manifest_path.read_bytes()
    assert write_manifest(manifest_path, manifest) is False
    assert manifest_path.read_bytes() == first_bytes


def test_verifier_accepts_current_canonical_manifest(tmp_path: Path) -> None:
    dataset_paths = _create_dataset(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, build_manifest(tmp_path, dataset_paths))

    assert verify_manifest(tmp_path, manifest_path, dataset_paths) == []


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("sha256", "0" * 64),
        ("bytes", 1),
        ("row_count", 99),
        ("columns", ["timestamp", "close"]),
        ("first_timestamp", "2020-01-01 00:00:00"),
        ("last_timestamp", "2030-01-01 00:00:00"),
    ],
)
def test_verifier_rejects_stale_observed_fields(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    dataset_paths = _create_dataset(tmp_path)
    manifest = build_manifest(tmp_path, dataset_paths)
    manifest["datasets"][0][field] = replacement
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, manifest)

    errors = verify_manifest(tmp_path, manifest_path, dataset_paths)

    assert any(field in error for error in errors)
    assert any("stale" in error for error in errors)


def test_verifier_rejects_missing_and_duplicate_records(tmp_path: Path) -> None:
    dataset_paths = _create_dataset(tmp_path)
    original = build_manifest(tmp_path, dataset_paths)
    manifest_path = tmp_path / "manifest.json"

    missing = copy.deepcopy(original)
    missing["datasets"] = []
    missing["record_count"] = 0
    _write_manifest(manifest_path, missing)
    assert any(
        "missing from manifest" in error
        for error in verify_manifest(tmp_path, manifest_path, dataset_paths)
    )

    duplicate = copy.deepcopy(original)
    duplicate["datasets"].append(copy.deepcopy(duplicate["datasets"][0]))
    duplicate["record_count"] = 2
    _write_manifest(manifest_path, duplicate)
    assert any(
        "duplicate manifest path" in error
        for error in verify_manifest(tmp_path, manifest_path, dataset_paths)
    )


def test_verifier_rejects_nonexistent_and_untracked_records(tmp_path: Path) -> None:
    dataset_paths = _create_dataset(tmp_path)
    manifest = build_manifest(tmp_path, dataset_paths)
    manifest_path = tmp_path / "manifest.json"

    nonexistent = copy.deepcopy(manifest["datasets"][0])
    nonexistent["path"] = f"{PROTECTED_DIRECTORIES[0]}/absent-5.csv"
    manifest["datasets"].append(nonexistent)
    manifest["record_count"] = 2
    _write_manifest(manifest_path, manifest)
    errors = verify_manifest(tmp_path, manifest_path, dataset_paths)
    assert any("does not exist" in error for error in errors)
    assert any("nonexistent or untracked" in error for error in errors)

    untracked_paths = _create_dataset(tmp_path, "untracked-5.csv")
    untracked_record = build_manifest(tmp_path, untracked_paths)["datasets"][0]
    manifest = build_manifest(tmp_path, dataset_paths)
    manifest["datasets"].append(untracked_record)
    manifest["datasets"].sort(key=lambda record: record["path"].casefold())
    manifest["record_count"] = 2
    _write_manifest(manifest_path, manifest)
    errors = verify_manifest(tmp_path, manifest_path, dataset_paths)
    assert any("nonexistent or untracked" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("classification", "INVALID"),
        ("schema_status", "INVALID"),
        ("classification_evidence_status", "INVALID"),
        ("source", {"evidence_status": "UNKNOWN", "value": ""}),
    ],
)
def test_verifier_rejects_bad_enums_and_empty_required_fields(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    dataset_paths = _create_dataset(tmp_path)
    manifest = build_manifest(tmp_path, dataset_paths)
    manifest["datasets"][0][field] = replacement
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, manifest)

    assert verify_manifest(tmp_path, manifest_path, dataset_paths)


def test_verifier_rejects_noncanonical_serialization(tmp_path: Path) -> None:
    dataset_paths = _create_dataset(tmp_path)
    manifest = build_manifest(tmp_path, dataset_paths)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=4), encoding="utf-8")

    errors = verify_manifest(tmp_path, manifest_path, dataset_paths)

    assert any("canonical deterministic form" in error for error in errors)
