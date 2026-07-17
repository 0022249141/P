"""Deterministic Decimal-safe HTF reconciliation and G5 evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd

from .contracts import (
    CANONICAL_COLUMNS,
    MAX_EXAMPLES,
    FieldDifferenceCounts,
    GateId,
    GateResult,
    GateStatus,
    ReconciliationResult,
    ReconciliationTolerance,
)


@dataclass(frozen=True)
class ReconciliationEvaluation:
    result: ReconciliationResult
    gate_result: GateResult

    def to_json_bytes(self) -> bytes:
        payload = {
            "gate_result": self.gate_result.model_dump(mode="json"),
            "result": self.result.model_dump(mode="json"),
        }
        text = json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)
        return f"{text}\n".encode("utf-8")


def reconcile_bars(
    generated: pd.DataFrame,
    supplied: pd.DataFrame,
    tolerance: ReconciliationTolerance,
) -> ReconciliationEvaluation:
    """Compare generated and supplied HTF bars using explicit tolerances."""

    _validate_columns(generated, "generated")
    _validate_columns(supplied, "supplied")
    if generated.empty and supplied.empty:
        result = ReconciliationResult(
            missing_target_bars=0,
            extra_target_bars=0,
            exact_match_count=0,
            tolerance_match_count=0,
            mismatch_count=0,
            field_differences=FieldDifferenceCounts(),
            mismatch_examples=(),
            tolerance=tolerance,
        )
        gate = GateResult(
            gate_id=GateId.G5_MTF_RECONCILIATION,
            status=GateStatus.BLOCKED,
            reason_code="G5_EMPTY_RECONCILIATION_BLOCKED",
            message="Reconciliation requires at least one generated or supplied target bar.",
            checked_record_count=0,
            affected_record_count=0,
            limitations=("Empty inputs provide no multi-timeframe reconciliation evidence.",),
            remediation_guidance=("Provide non-empty higher-timeframe bars for comparison.",),
        )
        return ReconciliationEvaluation(result, gate)

    generated_indexed = _indexed(generated, "generated")
    supplied_indexed = _indexed(supplied, "supplied")
    generated_timestamps = set(generated_indexed.index)
    supplied_timestamps = set(supplied_indexed.index)
    missing = sorted(generated_timestamps - supplied_timestamps)
    extra = sorted(supplied_timestamps - generated_timestamps)
    common = sorted(generated_timestamps & supplied_timestamps)

    exact_count = 0
    tolerance_count = 0
    mismatch_count = 0
    field_counts = {column: 0 for column in CANONICAL_COLUMNS[1:]}
    mismatch_examples: list[str] = []
    for timestamp in common:
        generated_row = generated_indexed.loc[timestamp]
        supplied_row = supplied_indexed.loc[timestamp]
        field_matches: dict[str, tuple[bool, bool]] = {}
        for column in CANONICAL_COLUMNS[1:]:
            generated_value = Decimal(str(generated_row[column]))
            supplied_value = Decimal(str(supplied_row[column]))
            exact = generated_value == supplied_value
            absolute = (
                Decimal(tolerance.volume_absolute)
                if column == "volume"
                else Decimal(tolerance.price_absolute)
            )
            allowed = absolute + Decimal(tolerance.relative) * abs(supplied_value)
            within = abs(generated_value - supplied_value) <= allowed
            field_matches[column] = exact, within
            if not within:
                field_counts[column] += 1
        if all(exact for exact, _ in field_matches.values()):
            exact_count += 1
        elif all(within for _, within in field_matches.values()):
            tolerance_count += 1
        else:
            mismatch_count += 1
            if len(mismatch_examples) < MAX_EXAMPLES:
                differing = sorted(column for column, (_, within) in field_matches.items() if not within)
                mismatch_examples.append(f"{pd.Timestamp(timestamp).isoformat()}:{','.join(differing)}")

    for timestamp in missing:
        if len(mismatch_examples) < MAX_EXAMPLES:
            mismatch_examples.append(f"missing:{pd.Timestamp(timestamp).isoformat()}")
    for timestamp in extra:
        if len(mismatch_examples) < MAX_EXAMPLES:
            mismatch_examples.append(f"extra:{pd.Timestamp(timestamp).isoformat()}")

    result = ReconciliationResult(
        missing_target_bars=len(missing),
        extra_target_bars=len(extra),
        exact_match_count=exact_count,
        tolerance_match_count=tolerance_count,
        mismatch_count=mismatch_count,
        field_differences=FieldDifferenceCounts(**field_counts),
        mismatch_examples=tuple(mismatch_examples),
        tolerance=tolerance,
    )
    has_failure = bool(missing or extra or mismatch_count)
    gate = GateResult(
        gate_id=GateId.G5_MTF_RECONCILIATION,
        status=GateStatus.FAIL if has_failure else GateStatus.PASS,
        reason_code="G5_RECONCILIATION_FAILED" if has_failure else "G5_RECONCILIATION_OK",
        message=(
            "Generated and supplied higher-timeframe bars differ."
            if has_failure
            else "Generated bars match supplied bars within declared tolerances."
        ),
        checked_record_count=len(common),
        affected_record_count=len(missing) + len(extra) + mismatch_count,
        examples=tuple(mismatch_examples),
        evidence_references=(
            f"price-absolute:{tolerance.price_absolute}",
            f"volume-absolute:{tolerance.volume_absolute}",
            f"relative:{tolerance.relative}",
        ),
        limitations=(
            (
                "Tolerance matches are not exact matches."
                if tolerance_count
                else "No tolerance-only matches were required."
            ),
        ),
        remediation_guidance=(
            (
                "Review missing, extra, and field-level differences before downstream eligibility."
                if has_failure
                else "No remediation required."
            ),
        ),
    )
    return ReconciliationEvaluation(result, gate)


def _indexed(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    _validate_columns(frame, label)
    if frame.empty:
        indexed = frame.copy(deep=True)
        indexed["timestamp"] = pd.DatetimeIndex([], tz="UTC")
        return indexed.set_index("timestamp")
    timestamps = pd.DatetimeIndex(frame["timestamp"])
    if timestamps.tz is None:
        raise ValueError(f"{label} timestamps must be timezone-aware")
    if timestamps.has_duplicates:
        raise ValueError(f"{label} timestamps must be unique")
    indexed = frame.copy(deep=True)
    indexed["timestamp"] = timestamps.tz_convert("UTC")
    return indexed.set_index("timestamp").sort_index()


def _validate_columns(frame: pd.DataFrame, label: str) -> None:
    if tuple(frame.columns) != CANONICAL_COLUMNS:
        raise ValueError(f"{label} frame must use canonical columns and order")
