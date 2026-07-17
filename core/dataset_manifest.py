"""Deterministic metadata contracts for committed market datasets."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


MANIFEST_SCHEMA_VERSION = "1.0.0"
PARSER_SCHEMA_VERSION = "1.0.0"
PROTECTED_DIRECTORIES = ("raw_data", "data_clean", "data_features")
CLASSIFICATION_BY_DIRECTORY = {
    "raw_data": "RAW",
    "data_clean": "CLEAN",
    "data_features": "FEATURE",
}
CLASSIFICATION_VALUES = {
    "RAW",
    "CLEAN",
    "FEATURE",
    "FIXTURE",
    "GENERATED",
    "UNKNOWN",
}
EVIDENCE_STATUS_VALUES = {"OBSERVED", "DECLARED", "INFERRED", "UNKNOWN"}
SCHEMA_STATUS_VALUES = {"CANONICAL_OHLCV", "NON_CANONICAL"}
TIMEZONE_STATUS_VALUES = {
    "NAIVE_UNKNOWN",
    "OFFSET_AWARE",
    "MIXED",
    "UNPARSEABLE",
}
CANONICAL_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
SEMANTIC_FIELDS = (
    "market",
    "symbol",
    "timeframe",
    "source",
    "timezone",
    "timestamp_period_semantics",
    "volume_meaning",
    "price_unit",
    "parser_decision",
)
TOP_LEVEL_KEYS = {
    "datasets",
    "manifest_schema_version",
    "parser_schema_version",
    "protected_directories",
    "record_count",
}
RECORD_KEYS = {
    "bytes",
    "classification",
    "classification_evidence_status",
    "columns",
    "columns_evidence_status",
    "duplicate_timestamp_count",
    "first_timestamp",
    "last_timestamp",
    "market",
    "missing_cell_count",
    "parser_decision",
    "parser_schema_version",
    "path",
    "price_unit",
    "row_count",
    "schema_status",
    "sha256",
    "source",
    "symbol",
    "timeframe",
    "timestamp_coverage_evidence_status",
    "timestamp_period_semantics",
    "timezone",
    "timezone_status",
    "volume_meaning",
}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DatasetManifestError(ValueError):
    """Raised when a dataset cannot be represented deterministically."""


def discover_tracked_datasets(root: Path) -> list[str]:
    """Return tracked protected CSV paths from the repository index."""

    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", *PROTECTED_DIRECTORIES],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise DatasetManifestError(f"cannot run git ls-files: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise DatasetManifestError(f"git ls-files failed: {detail}")

    paths = [
        path
        for path in result.stdout.decode("utf-8").split("\0")
        if path and PurePosixPath(path).suffix.casefold() == ".csv"
    ]
    return _sorted_unique_paths(paths)


def build_manifest(
    root: Path,
    dataset_paths: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Measure protected CSVs and return a deterministic manifest object."""

    root = root.resolve()
    paths = (
        discover_tracked_datasets(root)
        if dataset_paths is None
        else _sorted_unique_paths(dataset_paths)
    )
    datasets = [_build_record(root, path) for path in paths]
    return {
        "datasets": datasets,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "protected_directories": list(PROTECTED_DIRECTORIES),
        "record_count": len(datasets),
    }


def render_manifest(manifest: dict[str, Any]) -> bytes:
    """Serialize a manifest with stable keys, indentation, and newline."""

    text = json.dumps(
        manifest,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return f"{text}\n".encode("utf-8")


def write_manifest(path: Path, manifest: dict[str, Any]) -> bool:
    """Atomically write canonical bytes, returning whether content changed."""

    content = render_manifest(manifest)
    if path.exists() and path.read_bytes() == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_bytes(content)
    os.replace(temporary_path, path)
    return True


def verify_manifest(
    root: Path,
    manifest_path: Path,
    dataset_paths: Iterable[str] | None = None,
) -> list[str]:
    """Read and verify a manifest without modifying repository content."""

    root = root.resolve()
    manifest_path = (
        manifest_path if manifest_path.is_absolute() else root / manifest_path
    )
    errors: list[str] = []

    try:
        raw_manifest = manifest_path.read_bytes()
    except OSError as exc:
        return [f"cannot read manifest {manifest_path}: {exc}"]

    try:
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"manifest is not valid UTF-8 JSON: {exc}"]

    errors.extend(validate_manifest_structure(manifest, root))

    try:
        expected_paths = (
            discover_tracked_datasets(root)
            if dataset_paths is None
            else _sorted_unique_paths(dataset_paths)
        )
    except DatasetManifestError as exc:
        return [*errors, str(exc)]

    records = manifest.get("datasets", []) if isinstance(manifest, dict) else []
    record_paths = [
        record.get("path")
        for record in records
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    ]
    path_counts = Counter(record_paths)
    for path, count in sorted(path_counts.items(), key=lambda item: _path_key(item[0])):
        if count > 1:
            errors.append(f"duplicate manifest path: {path} appears {count} times")

    expected_set = set(expected_paths)
    record_set = set(record_paths)
    for path in sorted(expected_set - record_set, key=_path_key):
        errors.append(f"tracked dataset is missing from manifest: {path}")
    for path in sorted(record_set - expected_set, key=_path_key):
        errors.append(f"manifest path is nonexistent or untracked: {path}")

    try:
        expected_manifest = build_manifest(root, expected_paths)
    except (DatasetManifestError, OSError, UnicodeError, csv.Error) as exc:
        return [*errors, f"cannot rebuild expected manifest: {exc}"]

    unique_records = {
        record["path"]: record
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("path"), str)
        and path_counts[record["path"]] == 1
    }
    for expected_record in expected_manifest["datasets"]:
        path = expected_record["path"]
        actual_record = unique_records.get(path)
        if actual_record is None:
            continue
        for key, expected_value in expected_record.items():
            if actual_record.get(key) != expected_value:
                errors.append(f"{path}: field {key!r} does not match measured content")

    try:
        canonical_input = render_manifest(manifest)
    except (TypeError, ValueError) as exc:
        errors.append(f"manifest cannot be canonically serialized: {exc}")
    else:
        if canonical_input != raw_manifest:
            errors.append("manifest JSON is not in canonical deterministic form")

    if render_manifest(expected_manifest) != raw_manifest:
        errors.append("manifest is stale or differs from deterministic generator output")

    return _deduplicate(errors)


def validate_manifest_structure(manifest: Any, root: Path) -> list[str]:
    """Validate manifest types, required fields, enums, and path safety."""

    if not isinstance(manifest, dict):
        return ["manifest root must be a JSON object"]

    errors: list[str] = []
    missing_top = TOP_LEVEL_KEYS - set(manifest)
    extra_top = set(manifest) - TOP_LEVEL_KEYS
    if missing_top:
        errors.append(f"manifest is missing required fields: {sorted(missing_top)}")
    if extra_top:
        errors.append(f"manifest has unsupported fields: {sorted(extra_top)}")
    if manifest.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append("manifest_schema_version is unsupported or empty")
    if manifest.get("parser_schema_version") != PARSER_SCHEMA_VERSION:
        errors.append("parser_schema_version is unsupported or empty")
    if manifest.get("protected_directories") != list(PROTECTED_DIRECTORIES):
        errors.append("protected_directories does not match the versioned policy")

    records = manifest.get("datasets")
    if not isinstance(records, list):
        return [*errors, "datasets must be a JSON array"]
    if not _is_nonnegative_int(manifest.get("record_count")):
        errors.append("record_count must be a non-negative integer")
    elif manifest["record_count"] != len(records):
        errors.append("record_count does not match datasets length")

    sortable_paths: list[str] = []
    for index, record in enumerate(records):
        prefix = f"datasets[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be a JSON object")
            continue

        missing = RECORD_KEYS - set(record)
        extra = set(record) - RECORD_KEYS
        if missing:
            errors.append(f"{prefix} is missing required fields: {sorted(missing)}")
        if extra:
            errors.append(f"{prefix} has unsupported fields: {sorted(extra)}")

        path = record.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"{prefix}.path must be a non-empty string")
        else:
            sortable_paths.append(path)
            try:
                relative_path = _validate_relative_dataset_path(path)
            except DatasetManifestError as exc:
                errors.append(f"{prefix}.path is invalid: {exc}")
            else:
                file_path = root.joinpath(*relative_path.parts)
                if not file_path.is_file():
                    errors.append(f"{prefix}.path does not exist as a file: {path}")

        if record.get("classification") not in CLASSIFICATION_VALUES:
            errors.append(f"{prefix}.classification is not a valid enum value")
        _validate_evidence_status(
            record.get("classification_evidence_status"),
            f"{prefix}.classification_evidence_status",
            errors,
        )
        _validate_evidence_status(
            record.get("columns_evidence_status"),
            f"{prefix}.columns_evidence_status",
            errors,
        )
        _validate_evidence_status(
            record.get("timestamp_coverage_evidence_status"),
            f"{prefix}.timestamp_coverage_evidence_status",
            errors,
        )

        sha256 = record.get("sha256")
        if not isinstance(sha256, str) or _SHA256_PATTERN.fullmatch(sha256) is None:
            errors.append(f"{prefix}.sha256 must be a lowercase full SHA-256")
        for field in (
            "bytes",
            "row_count",
            "duplicate_timestamp_count",
            "missing_cell_count",
        ):
            if not _is_nonnegative_int(record.get(field)):
                errors.append(f"{prefix}.{field} must be a non-negative integer")

        columns = record.get("columns")
        if (
            not isinstance(columns, list)
            or not columns
            or any(not isinstance(column, str) or not column for column in columns)
        ):
            errors.append(f"{prefix}.columns must contain ordered non-empty strings")
        elif len(columns) != len(set(columns)):
            errors.append(f"{prefix}.columns contains duplicate names")

        if record.get("schema_status") not in SCHEMA_STATUS_VALUES:
            errors.append(f"{prefix}.schema_status is not a valid enum value")
        if record.get("timezone_status") not in TIMEZONE_STATUS_VALUES:
            errors.append(f"{prefix}.timezone_status is not a valid enum value")
        if record.get("parser_schema_version") != PARSER_SCHEMA_VERSION:
            errors.append(f"{prefix}.parser_schema_version is unsupported or empty")

        first_timestamp = record.get("first_timestamp")
        last_timestamp = record.get("last_timestamp")
        for field, value in (
            ("first_timestamp", first_timestamp),
            ("last_timestamp", last_timestamp),
        ):
            if value is not None and (not isinstance(value, str) or not value):
                errors.append(f"{prefix}.{field} must be null or a non-empty string")
        if (first_timestamp is None) != (last_timestamp is None):
            errors.append(f"{prefix} timestamp coverage must have both endpoints or neither")

        for field in SEMANTIC_FIELDS:
            _validate_evidence_value(record.get(field), f"{prefix}.{field}", errors)

    if sortable_paths != sorted(sortable_paths, key=_path_key):
        errors.append("dataset records are not in deterministic path order")
    return errors


def _build_record(root: Path, relative_path: str) -> dict[str, Any]:
    path = _validate_relative_dataset_path(relative_path)
    file_path = root.joinpath(*path.parts)
    if not file_path.is_file():
        raise DatasetManifestError(f"dataset does not exist: {relative_path}")

    directory = path.parts[0]
    classification = CLASSIFICATION_BY_DIRECTORY.get(directory, "UNKNOWN")
    symbol_value, timeframe_value = _filename_labels(path.stem)
    metrics = _measure_csv(file_path)

    inferred_symbol = _evidence_value(symbol_value, "INFERRED")
    return {
        "bytes": metrics["bytes"],
        "classification": classification,
        "classification_evidence_status": "DECLARED",
        "columns": metrics["columns"],
        "columns_evidence_status": "OBSERVED",
        "duplicate_timestamp_count": metrics["duplicate_timestamp_count"],
        "first_timestamp": metrics["first_timestamp"],
        "last_timestamp": metrics["last_timestamp"],
        "market": dict(inferred_symbol),
        "missing_cell_count": metrics["missing_cell_count"],
        "parser_decision": _evidence_value(
            "PYTHON_CSV_EXCEL_DIALECT_WITH_HEADER", "DECLARED"
        ),
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "path": path.as_posix(),
        "price_unit": _evidence_value("UNKNOWN", "UNKNOWN"),
        "row_count": metrics["row_count"],
        "schema_status": metrics["schema_status"],
        "sha256": metrics["sha256"],
        "source": _evidence_value("UNKNOWN", "UNKNOWN"),
        "symbol": inferred_symbol,
        "timeframe": _evidence_value(timeframe_value, "INFERRED"),
        "timestamp_coverage_evidence_status": (
            "OBSERVED" if metrics["first_timestamp"] is not None else "UNKNOWN"
        ),
        "timestamp_period_semantics": _evidence_value("UNKNOWN", "UNKNOWN"),
        "timezone": _evidence_value("UNKNOWN", "UNKNOWN"),
        "timezone_status": metrics["timezone_status"],
        "volume_meaning": _evidence_value("UNKNOWN", "UNKNOWN"),
    }


def _measure_csv(path: Path) -> dict[str, Any]:
    initial_stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        try:
            columns = next(reader)
        except StopIteration as exc:
            raise DatasetManifestError(f"dataset has no CSV header: {path}") from exc

        row_count = 0
        missing_cell_count = 0
        duplicate_timestamp_count = 0
        seen_timestamps: set[str] = set()
        first_timestamp: str | None = None
        last_timestamp: str | None = None
        parseable_timestamp_count = 0
        aware_timestamp_count = 0
        row_widths_valid = True
        timestamp_index = columns.index("timestamp") if "timestamp" in columns else None

        for row in reader:
            row_count += 1
            if len(row) != len(columns):
                row_widths_valid = False
            missing_cell_count += sum(not value.strip() for value in row)
            missing_cell_count += max(0, len(columns) - len(row))

            if timestamp_index is None or timestamp_index >= len(row):
                continue
            timestamp = row[timestamp_index].strip()
            if not timestamp:
                continue
            if timestamp in seen_timestamps:
                duplicate_timestamp_count += 1
            else:
                seen_timestamps.add(timestamp)

            parsed_timestamp = _parse_timestamp(timestamp)
            if parsed_timestamp is None:
                continue
            parseable_timestamp_count += 1
            if parsed_timestamp.utcoffset() is not None:
                aware_timestamp_count += 1
            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp

    final_stat = path.stat()
    if (
        initial_stat.st_size != final_stat.st_size
        or initial_stat.st_mtime_ns != final_stat.st_mtime_ns
    ):
        raise DatasetManifestError(f"dataset changed while it was being measured: {path}")

    if parseable_timestamp_count == 0:
        timezone_status = "UNPARSEABLE"
    elif aware_timestamp_count == 0:
        timezone_status = "NAIVE_UNKNOWN"
    elif aware_timestamp_count == parseable_timestamp_count:
        timezone_status = "OFFSET_AWARE"
    else:
        timezone_status = "MIXED"

    return {
        "bytes": initial_stat.st_size,
        "columns": columns,
        "duplicate_timestamp_count": duplicate_timestamp_count,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "missing_cell_count": missing_cell_count,
        "row_count": row_count,
        "schema_status": (
            "CANONICAL_OHLCV"
            if columns == CANONICAL_COLUMNS and row_widths_valid
            else "NON_CANONICAL"
        ),
        "sha256": digest.hexdigest(),
        "timezone_status": timezone_status,
    }


def _parse_timestamp(value: str) -> datetime | None:
    candidate = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _filename_labels(stem: str) -> tuple[str, str]:
    symbol, separator, timeframe = stem.rpartition("-")
    if not separator or not symbol or not timeframe:
        return stem or "UNKNOWN", "UNKNOWN"
    return symbol, timeframe


def _evidence_value(value: str, evidence_status: str) -> dict[str, str]:
    return {"evidence_status": evidence_status, "value": value}


def _validate_evidence_value(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or set(value) != {"evidence_status", "value"}:
        errors.append(f"{field} must contain exactly value and evidence_status")
        return
    if not isinstance(value.get("value"), str) or not value["value"]:
        errors.append(f"{field}.value must be a non-empty string")
    _validate_evidence_status(
        value.get("evidence_status"), f"{field}.evidence_status", errors
    )


def _validate_evidence_status(value: Any, field: str, errors: list[str]) -> None:
    if value not in EVIDENCE_STATUS_VALUES:
        errors.append(f"{field} is not a valid enum value")


def _validate_relative_dataset_path(path: str) -> PurePosixPath:
    normalized = path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise DatasetManifestError("path must be repository-relative without traversal")
    if not candidate.parts or candidate.parts[0] not in PROTECTED_DIRECTORIES:
        raise DatasetManifestError("path must be under a protected dataset directory")
    if candidate.suffix.casefold() != ".csv":
        raise DatasetManifestError("path must identify a CSV file")
    if candidate.as_posix() != path:
        raise DatasetManifestError("path must use normalized forward slashes")
    return candidate


def _sorted_unique_paths(paths: Iterable[str]) -> list[str]:
    normalized = [str(path).replace("\\", "/") for path in paths]
    if len(normalized) != len(set(normalized)):
        raise DatasetManifestError("dataset path input contains duplicates")
    for path in normalized:
        _validate_relative_dataset_path(path)
    return sorted(normalized, key=_path_key)


def _path_key(path: str) -> tuple[str, str]:
    return path.casefold(), path


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
