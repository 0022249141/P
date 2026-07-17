"""In-memory canonicalization with explicit G1-G3 validation."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from .contracts import (
    CANONICAL_COLUMNS,
    MAX_EXAMPLES,
    CanonicalizationPolicy,
    DSTAmbiguousPolicy,
    DSTNonexistentPolicy,
    DuplicatePolicy,
    EvidenceStatus,
    GateFinding,
    GateId,
    GateResult,
    GateStatus,
    PeriodSemantics,
    RepairRecord,
    ValidationMode,
    VolumeAggregation,
)


@dataclass(frozen=True)
class CanonicalInput:
    """An explicit in-memory table plus parser-level diagnostics."""

    table: pd.DataFrame
    parser_decision: str = "IN_MEMORY_DATAFRAME"
    row_width_mismatch_rows: tuple[int, ...] = ()
    shifted_field_rows: tuple[int, ...] = ()


@dataclass(frozen=True)
class CanonicalizationResult:
    """Canonical rows, lineage, repairs, and G1-G3 gate evidence."""

    frame: pd.DataFrame | None
    source_rows: tuple[tuple[int, ...], ...]
    repairs: tuple[RepairRecord, ...]
    gate_results: tuple[GateResult, ...]

    def serialized_frame(self) -> bytes | None:
        return None if self.frame is None else serialize_canonical_frame(self.frame)


def canonicalize(
    value: pd.DataFrame | CanonicalInput,
    policy: CanonicalizationPolicy,
) -> CanonicalizationResult:
    """Validate and canonicalize a table without reading or writing files."""

    canonical_input = value if isinstance(value, CanonicalInput) else CanonicalInput(value)
    table = canonical_input.table.copy(deep=True)
    row_count = len(table)

    g1_findings, numeric = _evaluate_schema_and_parsing(table, canonical_input, policy)
    g1 = _gate_result(
        GateId.G1_SCHEMA_PARSING,
        GateStatus.FAIL if g1_findings else GateStatus.PASS,
        "G1_SCHEMA_PARSING_FAILED" if g1_findings else "G1_SCHEMA_PARSING_OK",
        "Schema or parser violations were detected."
        if g1_findings
        else "Canonical columns and parser evidence are valid.",
        row_count,
        g1_findings,
        remediation=(
            "Correct parser decisions, headers, row widths, and numeric source values."
            if g1_findings
            else "No remediation required."
        ),
    )

    g2_findings, utc_timestamps, temporal_blocked, duplicate_rows = (
        _evaluate_temporal(table, policy)
    )
    temporal_failures = any(
        finding.reason_code
        not in {"DUPLICATES_REPAIRED", "DUPLICATE_IDENTICAL_REPAIRED"}
        for finding in g2_findings
    )
    if temporal_failures:
        g2_status = GateStatus.BLOCKED if temporal_blocked else GateStatus.FAIL
    else:
        g2_status = GateStatus.PASS
    if g2_status is GateStatus.PASS and g2_findings:
        g2_reason = "G2_TEMPORAL_REPAIRED"
        g2_message = "Temporal duplicates were resolved under explicit repair policy."
    elif g2_status is GateStatus.PASS:
        g2_reason = "G2_TEMPORAL_INTEGRITY_OK"
        g2_message = "Timestamp evidence and temporal ordering are valid."
    elif g2_status is GateStatus.BLOCKED:
        g2_reason = "G2_TEMPORAL_EVIDENCE_BLOCKED"
        g2_message = "Required timestamp semantics or configured resolution evidence is unavailable."
    else:
        g2_reason = "G2_TEMPORAL_INTEGRITY_FAILED"
        g2_message = "Temporal integrity violations were detected."
    g2 = _gate_result(
        GateId.G2_TEMPORAL_INTEGRITY,
        g2_status,
        g2_reason,
        g2_message,
        row_count,
        g2_findings,
        remediation=(
            "Declare timezone and period semantics; correct timestamp ordering or use explicit audited repair."
            if g2_status is not GateStatus.PASS
            else "Review emitted repair records before using repaired output."
            if g2_findings
            else "No remediation required."
        ),
    )

    g3_findings = _evaluate_ohlc_numeric(table, numeric, policy)
    if not all(column in table.columns for column in CANONICAL_COLUMNS[1:]):
        g3_status = GateStatus.BLOCKED
        g3_reason = "G3_SCHEMA_DEPENDENCY_BLOCKED"
        g3_message = "OHLC numeric checks require all canonical numeric columns."
    else:
        g3_status = GateStatus.FAIL if g3_findings else GateStatus.PASS
        g3_reason = "G3_OHLC_NUMERIC_FAILED" if g3_findings else "G3_OHLC_NUMERIC_OK"
        g3_message = (
            "OHLC or numeric integrity violations were detected."
            if g3_findings
            else "OHLC geometry and configured numeric policies are valid."
        )
    g3 = _gate_result(
        GateId.G3_OHLC_NUMERIC,
        g3_status,
        g3_reason,
        g3_message,
        row_count,
        g3_findings,
        remediation=(
            "Correct non-finite, nonnumeric, volume, or OHLC geometry violations."
            if g3_status is not GateStatus.PASS
            else "No remediation required."
        ),
    )

    if any(result.status is not GateStatus.PASS for result in (g1, g2, g3)):
        return CanonicalizationResult(None, (), (), (g1, g2, g3))

    frame, source_rows, repairs = _build_output(
        table,
        numeric,
        utc_timestamps,
        duplicate_rows,
        policy,
    )
    return CanonicalizationResult(frame, source_rows, repairs, (g1, g2, g3))


def serialize_canonical_frame(frame: pd.DataFrame) -> bytes:
    """Serialize canonical rows deterministically for reproducibility checks."""

    if tuple(frame.columns) != CANONICAL_COLUMNS:
        raise ValueError("frame does not use the canonical schema and order")
    records: list[dict[str, Any]] = []
    for row in frame.itertuples(index=False, name=None):
        timestamp = pd.Timestamp(row[0])
        if timestamp.tzinfo is None:
            raise ValueError("canonical timestamp must be timezone-aware")
        timestamp_text = timestamp.tz_convert("UTC").isoformat().replace("+00:00", "Z")
        record = {"timestamp": timestamp_text}
        for column, value in zip(CANONICAL_COLUMNS[1:], row[1:]):
            if isinstance(value, np.generic):
                value = value.item()
            record[column] = value
        records.append(record)
    text = json.dumps(
        records,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{text}\n".encode("utf-8")


def _evaluate_schema_and_parsing(
    table: pd.DataFrame,
    canonical_input: CanonicalInput,
    policy: CanonicalizationPolicy,
) -> tuple[list[GateFinding], dict[str, pd.Series]]:
    findings: list[GateFinding] = []
    columns = [str(column) for column in table.columns]
    column_counts = Counter(columns)
    duplicate_columns = sorted(column for column, count in column_counts.items() if count > 1)
    empty_headers = [index for index, column in enumerate(columns) if not column.strip()]
    missing_columns = [column for column in CANONICAL_COLUMNS if column not in column_counts]
    unsupported_columns = [column for column in columns if column not in CANONICAL_COLUMNS]

    if empty_headers:
        findings.append(_finding("EMPTY_HEADER", "Empty column headers were detected.", empty_headers))
    if duplicate_columns:
        findings.append(
            _finding(
                "DUPLICATE_COLUMN_NAMES",
                "Duplicate column names are unsupported.",
                duplicate_columns,
            )
        )
    if missing_columns:
        findings.append(
            _finding("MISSING_CANONICAL_COLUMNS", "Required columns are missing.", missing_columns)
        )
    if policy.strict_columns and columns != list(CANONICAL_COLUMNS):
        findings.append(
            _finding(
                "CANONICAL_COLUMN_ORDER_MISMATCH",
                "Strict canonical mode requires exact columns and order.",
                [f"observed={columns}"],
                affected=max(1, len(missing_columns) + len(unsupported_columns)),
            )
        )
    elif unsupported_columns:
        findings.append(
            _finding(
                "UNSUPPORTED_COLUMNS",
                "Unsupported columns were reported.",
                unsupported_columns,
            )
        )
    if canonical_input.row_width_mismatch_rows:
        findings.append(
            _finding(
                "ROW_WIDTH_MISMATCH",
                "Parser reported rows with unexpected field counts.",
                canonical_input.row_width_mismatch_rows,
            )
        )
    if canonical_input.shifted_field_rows:
        findings.append(
            _finding(
                "SILENT_FIELD_SHIFT_DETECTED",
                "Parser reported shifted fields.",
                canonical_input.shifted_field_rows,
            )
        )
    if canonical_input.parser_decision not in policy.supported_parser_decisions:
        findings.append(
            _finding(
                "UNSUPPORTED_PARSER_DECISION",
                "Parser decision is not allowed by canonical policy.",
                [canonical_input.parser_decision],
            )
        )

    numeric: dict[str, pd.Series] = {}
    for column in CANONICAL_COLUMNS:
        if column_counts.get(column) != 1:
            continue
        series = table[column]
        missing_mask = series.isna() | series.astype(str).str.strip().eq("")
        if missing_mask.any():
            rows = tuple(int(index) for index in np.flatnonzero(missing_mask.to_numpy()))
            findings.append(
                _finding(
                    "EMPTY_REQUIRED_VALUES",
                    f"Required column {column!r} contains empty values.",
                    rows,
                )
            )
        if column == "timestamp":
            continue
        converted = pd.to_numeric(series, errors="coerce")
        numeric[column] = converted
        unparseable = (~missing_mask) & converted.isna()
        if unparseable.any():
            rows = tuple(int(index) for index in np.flatnonzero(unparseable.to_numpy()))
            findings.append(
                _finding(
                    "UNPARSEABLE_NUMERIC_VALUES",
                    f"Column {column!r} contains nonnumeric values.",
                    rows,
                )
            )
    return findings, numeric


def _evaluate_temporal(
    table: pd.DataFrame,
    policy: CanonicalizationPolicy,
) -> tuple[list[GateFinding], pd.Series | None, bool, tuple[int, ...]]:
    findings: list[GateFinding] = []
    blocked = False
    if list(table.columns).count("timestamp") != 1:
        return (
            [_finding("TIMESTAMP_SCHEMA_DEPENDENCY", "A unique timestamp column is required.", ())],
            None,
            True,
            (),
        )

    parsed: list[pd.Timestamp | None] = []
    unparseable_rows: list[int] = []
    for row_number, value in enumerate(table["timestamp"].tolist()):
        if value is None or (isinstance(value, float) and np.isnan(value)) or not str(value).strip():
            parsed.append(None)
            unparseable_rows.append(row_number)
            continue
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError):
            parsed.append(None)
            unparseable_rows.append(row_number)
        else:
            parsed.append(timestamp)
    if unparseable_rows:
        findings.append(
            _finding(
                "UNPARSEABLE_TIMESTAMPS",
                "Timestamp values could not be parsed.",
                unparseable_rows,
            )
        )

    timestamp_semantics = policy.timestamp
    if (
        timestamp_semantics.timezone == "UNKNOWN"
        or timestamp_semantics.timezone_evidence is EvidenceStatus.UNKNOWN
    ):
        findings.append(
            _finding(
                "TIMEZONE_EVIDENCE_UNKNOWN",
                "UTC conversion requires explicit timezone evidence.",
                (),
                affected=len(table),
            )
        )
        blocked = True
    if (
        timestamp_semantics.period_semantics is PeriodSemantics.UNKNOWN
        or timestamp_semantics.period_evidence is EvidenceStatus.UNKNOWN
    ):
        findings.append(
            _finding(
                "TIMESTAMP_PERIOD_SEMANTICS_UNKNOWN",
                "Period-start or period-end semantics must be explicit.",
                (),
                affected=len(table),
            )
        )
        blocked = True

    valid_parsed = [timestamp for timestamp in parsed if timestamp is not None]
    awareness = [timestamp.tzinfo is not None for timestamp in valid_parsed]
    if awareness and any(awareness) and not all(awareness):
        findings.append(
            _finding(
                "MIXED_AWARE_NAIVE_TIMESTAMPS",
                "Aware and naive timestamps cannot be mixed.",
                [index for index, timestamp in enumerate(parsed) if timestamp is not None],
            )
        )
    if unparseable_rows or blocked or (awareness and any(awareness) and not all(awareness)):
        return findings, None, blocked, ()

    utc_values: list[pd.Timestamp]
    try:
        if valid_parsed and awareness and all(awareness):
            ZoneInfo(timestamp_semantics.timezone)
            utc_values = [timestamp.tz_convert("UTC") for timestamp in valid_parsed]
        else:
            ZoneInfo(timestamp_semantics.timezone)
            index = pd.DatetimeIndex(valid_parsed)
            localized = index.tz_localize(
                timestamp_semantics.timezone,
                ambiguous=_ambiguous_argument(timestamp_semantics.ambiguous_policy),
                nonexistent=_nonexistent_argument(timestamp_semantics.nonexistent_policy),
            )
            if localized.isna().any():
                rows = tuple(int(index) for index in np.flatnonzero(localized.isna()))
                findings.append(
                    _finding(
                        "DST_RESOLUTION_PRODUCED_NAT",
                        "Configured DST policy produced unavailable timestamps.",
                        rows,
                    )
                )
                return findings, None, True, ()
            utc_values = list(localized.tz_convert("UTC"))
    except ZoneInfoNotFoundError:
        findings.append(
            _finding(
                "INVALID_IANA_TIMEZONE",
                "Configured timezone is not available in the IANA database.",
                [timestamp_semantics.timezone],
            )
        )
        return findings, None, True, ()
    except Exception as exc:  # pandas exposes DST exceptions through backend-specific classes
        exception_name = type(exc).__name__
        reason = (
            "DST_AMBIGUOUS_TIMESTAMP"
            if "Ambiguous" in exception_name or "ambiguous" in str(exc).lower()
            else "DST_NONEXISTENT_TIMESTAMP"
            if "NonExistent" in exception_name or "nonexistent" in str(exc).lower()
            else "TIMEZONE_LOCALIZATION_FAILED"
        )
        findings.append(
            _finding(reason, "Configured timezone localization failed.", [exception_name])
        )
        return findings, None, True, ()

    utc_series = pd.Series(pd.DatetimeIndex(utc_values), index=table.index)
    if not utc_series.is_monotonic_increasing:
        rows = tuple(
            index
            for index in range(1, len(utc_series))
            if utc_series.iloc[index] < utc_series.iloc[index - 1]
        )
        findings.append(
            _finding(
                "NON_MONOTONIC_TIMESTAMPS",
                "Timestamp order is not monotonic.",
                rows,
            )
        )

    duplicate_mask = utc_series.duplicated(keep=False)
    duplicate_rows = tuple(int(index) for index in np.flatnonzero(duplicate_mask.to_numpy()))
    if duplicate_rows:
        conflicting_rows = _conflicting_duplicate_rows(table, utc_series)
        if policy.duplicate_policy is DuplicatePolicy.REJECT:
            reason = "CONFLICTING_DUPLICATE_TIMESTAMPS" if conflicting_rows else "DUPLICATE_TIMESTAMPS"
            findings.append(
                _finding(
                    reason,
                    "Duplicate timestamps are rejected by default.",
                    conflicting_rows or duplicate_rows,
                )
            )
        elif policy.duplicate_policy is DuplicatePolicy.CUSTOM:
            findings.append(
                _finding(
                    "CUSTOM_DUPLICATE_POLICY_UNAVAILABLE",
                    "CUSTOM duplicate policy requires an external audited resolver.",
                    duplicate_rows,
                )
            )
            blocked = True
        elif (
            policy.duplicate_policy is DuplicatePolicy.AGGREGATE
            and policy.volume.aggregation is VolumeAggregation.UNKNOWN
        ):
            findings.append(
                _finding(
                    "DUPLICATE_AGGREGATION_VOLUME_UNKNOWN",
                    "Duplicate aggregation requires declared volume aggregation.",
                    duplicate_rows,
                )
            )
            blocked = True
        else:
            reason = "DUPLICATES_REPAIRED" if conflicting_rows else "DUPLICATE_IDENTICAL_REPAIRED"
            findings.append(
                _finding(
                    reason,
                    "Duplicate timestamps will be resolved under explicit repair mode.",
                    duplicate_rows,
                )
            )
    return findings, utc_series, blocked, duplicate_rows


def _evaluate_ohlc_numeric(
    table: pd.DataFrame,
    numeric: dict[str, pd.Series],
    policy: CanonicalizationPolicy,
) -> list[GateFinding]:
    findings: list[GateFinding] = []
    if not all(column in numeric for column in CANONICAL_COLUMNS[1:]):
        return findings

    nonnumeric_rows: set[int] = set()
    nan_rows: set[int] = set()
    infinity_rows: set[int] = set()
    for column, series in numeric.items():
        original = table[column]
        missing = original.isna() | original.astype(str).str.strip().eq("")
        converted_nan = series.isna()
        nan_rows.update(int(index) for index in np.flatnonzero(missing.to_numpy()))
        nonnumeric_rows.update(
            int(index) for index in np.flatnonzero(((~missing) & converted_nan).to_numpy())
        )
        infinity_rows.update(int(index) for index in np.flatnonzero(np.isinf(series.to_numpy())))
    if nonnumeric_rows:
        findings.append(
            _finding("NONNUMERIC_OHLC_VALUES", "Nonnumeric values were detected.", nonnumeric_rows)
        )
    if nan_rows:
        findings.append(_finding("NAN_VALUES", "NaN or empty numeric values were detected.", nan_rows))
    if infinity_rows:
        findings.append(
            _finding("INFINITE_VALUES", "Positive or negative infinity was detected.", infinity_rows)
        )

    finite_mask = np.logical_and.reduce(
        [np.isfinite(numeric[column].to_numpy(dtype=float)) for column in CANONICAL_COLUMNS[1:]]
    )
    volume_negative = numeric["volume"].to_numpy(dtype=float) < 0
    if volume_negative.any():
        findings.append(
            _finding(
                "NEGATIVE_VOLUME",
                "Volume must be non-negative.",
                np.flatnonzero(volume_negative),
            )
        )

    open_values = numeric["open"].to_numpy(dtype=float)
    high_values = numeric["high"].to_numpy(dtype=float)
    low_values = numeric["low"].to_numpy(dtype=float)
    close_values = numeric["close"].to_numpy(dtype=float)
    invalid_high = finite_mask & (
        high_values < np.maximum.reduce([open_values, close_values, low_values])
    )
    invalid_low = finite_mask & (
        low_values > np.minimum.reduce([open_values, close_values, high_values])
    )
    if invalid_high.any():
        findings.append(
            _finding(
                "INVALID_HIGH_GEOMETRY",
                "High must be at least open, close, and low.",
                np.flatnonzero(invalid_high),
            )
        )
    if invalid_low.any():
        findings.append(
            _finding(
                "INVALID_LOW_GEOMETRY",
                "Low must be at most open, close, and high.",
                np.flatnonzero(invalid_low),
            )
        )
    if policy.price_unit.strictly_positive:
        prices = np.column_stack([open_values, high_values, low_values, close_values])
        nonpositive = finite_mask & (prices <= 0).any(axis=1)
        if nonpositive.any():
            findings.append(
                _finding(
                    "NONPOSITIVE_PRICE_POLICY",
                    "Declared market policy requires strictly positive prices.",
                    np.flatnonzero(nonpositive),
                )
            )
    return findings


def _build_output(
    table: pd.DataFrame,
    numeric: dict[str, pd.Series],
    utc_timestamps: pd.Series | None,
    duplicate_rows: tuple[int, ...],
    policy: CanonicalizationPolicy,
) -> tuple[pd.DataFrame, tuple[tuple[int, ...], ...], tuple[RepairRecord, ...]]:
    if utc_timestamps is None:
        raise ValueError("UTC timestamps are required for canonical output")
    working = pd.DataFrame({"timestamp": utc_timestamps})
    for column in CANONICAL_COLUMNS[1:]:
        working[column] = numeric[column].to_numpy()
    working["_source_row"] = list(range(len(working)))

    if not duplicate_rows:
        frame = working[list(CANONICAL_COLUMNS)].reset_index(drop=True)
        lineage = tuple((int(row),) for row in working["_source_row"])
        return frame, lineage, ()

    grouped = list(working.groupby("timestamp", sort=False, dropna=False))
    repairs: list[RepairRecord] = []
    output_rows: list[dict[str, Any]] = []
    lineage: list[tuple[int, ...]] = []
    for timestamp, group in grouped:
        source_rows = tuple(int(row) for row in group["_source_row"].tolist())
        if len(group) == 1:
            selected = group.iloc[0]
            output_rows.append({column: selected[column] for column in CANONICAL_COLUMNS})
            lineage.append(source_rows)
            continue

        if policy.duplicate_policy is DuplicatePolicy.KEEP_FIRST:
            selected = group.iloc[0]
            row = {column: selected[column] for column in CANONICAL_COLUMNS}
            action = "KEEP_FIRST"
        elif policy.duplicate_policy is DuplicatePolicy.KEEP_LAST:
            selected = group.iloc[-1]
            row = {column: selected[column] for column in CANONICAL_COLUMNS}
            action = "KEEP_LAST"
        elif policy.duplicate_policy is DuplicatePolicy.AGGREGATE:
            row = {
                "timestamp": timestamp,
                "open": group["open"].iloc[0],
                "high": group["high"].max(),
                "low": group["low"].min(),
                "close": group["close"].iloc[-1],
                "volume": _aggregate_volume(group["volume"], policy.volume.aggregation),
            }
            action = "AGGREGATE"
        else:
            raise ValueError("duplicate output requires an implemented repair policy")
        output_rows.append(row)
        lineage.append(source_rows)
        repairs.append(
            RepairRecord(
                action=action,
                timestamp=pd.Timestamp(timestamp).isoformat().replace("+00:00", "Z"),
                source_rows=source_rows,
                detail="Explicit duplicate repair preserved all source row identities.",
            )
        )
    frame = pd.DataFrame(output_rows, columns=CANONICAL_COLUMNS)
    return frame, tuple(lineage), tuple(repairs)


def _aggregate_volume(series: pd.Series, aggregation: VolumeAggregation) -> Any:
    if aggregation is VolumeAggregation.SUM:
        return series.sum()
    if aggregation is VolumeAggregation.FIRST:
        return series.iloc[0]
    if aggregation is VolumeAggregation.LAST:
        return series.iloc[-1]
    raise ValueError("volume aggregation must be declared")


def _conflicting_duplicate_rows(table: pd.DataFrame, timestamps: pd.Series) -> tuple[int, ...]:
    conflicting: list[int] = []
    duplicate_mask = timestamps.duplicated(keep=False)
    for timestamp in timestamps[duplicate_mask].drop_duplicates().tolist():
        rows = [
            int(index)
            for index in np.flatnonzero((timestamps == timestamp).to_numpy())
        ]
        values = {
            tuple(str(table.iloc[row][column]) for column in CANONICAL_COLUMNS[1:] if column in table)
            for row in rows
        }
        if len(values) > 1:
            conflicting.extend(rows)
    return tuple(sorted(conflicting))


def _ambiguous_argument(policy: DSTAmbiguousPolicy) -> str | bool:
    return {
        DSTAmbiguousPolicy.RAISE: "raise",
        DSTAmbiguousPolicy.INFER: "infer",
        DSTAmbiguousPolicy.EARLIEST: True,
        DSTAmbiguousPolicy.LATEST: False,
        DSTAmbiguousPolicy.NAT: "NaT",
    }[policy]


def _nonexistent_argument(policy: DSTNonexistentPolicy) -> str:
    return {
        DSTNonexistentPolicy.RAISE: "raise",
        DSTNonexistentPolicy.SHIFT_FORWARD: "shift_forward",
        DSTNonexistentPolicy.SHIFT_BACKWARD: "shift_backward",
        DSTNonexistentPolicy.NAT: "NaT",
    }[policy]


def _finding(
    reason_code: str,
    message: str,
    examples: Iterable[object],
    *,
    affected: int | None = None,
) -> GateFinding:
    ordered_examples = (
        sorted(examples, key=lambda value: str(value))
        if isinstance(examples, (set, frozenset))
        else examples
    )
    stable_examples = tuple(str(value) for value in ordered_examples)
    return GateFinding(
        reason_code=reason_code,
        message=message,
        affected_record_count=len(stable_examples) if affected is None else affected,
        examples=stable_examples[:MAX_EXAMPLES],
    )


def _gate_result(
    gate_id: GateId,
    status: GateStatus,
    reason_code: str,
    message: str,
    checked: int,
    findings: list[GateFinding],
    *,
    remediation: str,
) -> GateResult:
    affected = sum(finding.affected_record_count for finding in findings)
    examples = tuple(
        example for finding in findings for example in finding.examples
    )[:MAX_EXAMPLES]
    return GateResult(
        gate_id=gate_id,
        status=status,
        reason_code=reason_code,
        message=message,
        checked_record_count=checked,
        affected_record_count=affected,
        examples=examples,
        evidence_references=("in-memory-table",),
        limitations=(),
        remediation_guidance=(remediation,),
        findings=tuple(findings),
    )
