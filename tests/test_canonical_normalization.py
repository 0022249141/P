from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipelines.canonical import (
    CanonicalInput,
    CanonicalizationPolicy,
    DSTAmbiguousPolicy,
    DSTNonexistentPolicy,
    DuplicatePolicy,
    EvidenceStatus,
    GateStatus,
    PeriodSemantics,
    PriceUnitDeclaration,
    TimestampSemantics,
    ValidationMode,
    canonicalize,
)


def _bars(timestamps: list[object] | pd.DatetimeIndex) -> pd.DataFrame:
    size = len(timestamps)
    opens = np.arange(size, dtype=float) + 100.0
    return pd.DataFrame(
        {
            "timestamp": list(timestamps),
            "open": opens,
            "high": opens + 2.0,
            "low": opens - 1.0,
            "close": opens + 1.0,
            "volume": np.arange(size, dtype=float) + 10.0,
        }
    )


def _policy(
    *,
    timezone: str = "UTC",
    timezone_evidence: EvidenceStatus = EvidenceStatus.DECLARED,
    period: PeriodSemantics = PeriodSemantics.PERIOD_START,
    period_evidence: EvidenceStatus = EvidenceStatus.DECLARED,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.REJECT,
    validation_mode: ValidationMode = ValidationMode.VALIDATE_ONLY,
    ambiguous: DSTAmbiguousPolicy = DSTAmbiguousPolicy.RAISE,
    nonexistent: DSTNonexistentPolicy = DSTNonexistentPolicy.RAISE,
) -> CanonicalizationPolicy:
    return CanonicalizationPolicy(
        timestamp=TimestampSemantics(
            timezone=timezone,
            timezone_evidence=timezone_evidence,
            period_semantics=period,
            period_evidence=period_evidence,
            ambiguous_policy=ambiguous,
            nonexistent_policy=nonexistent,
        ),
        duplicate_policy=duplicate_policy,
        validation_mode=validation_mode,
    )


def _finding_codes(result, gate_index: int) -> set[str]:
    return {finding.reason_code for finding in result.gate_results[gate_index].findings}


def test_valid_canonical_utc_m1_is_deterministic() -> None:
    table = _bars(pd.date_range("2024-01-01", periods=5, freq="min", tz="UTC"))

    first = canonicalize(table, _policy())
    second = canonicalize(table, _policy())

    assert [result.status for result in first.gate_results] == [GateStatus.PASS] * 3
    assert first.frame is not None
    assert str(first.frame["timestamp"].dt.tz) == "UTC"
    assert first.serialized_frame() == second.serialized_frame()
    assert first.source_rows == ((0,), (1,), (2,), (3,), (4,))


def test_naive_timestamps_with_unknown_timezone_block_utc_output() -> None:
    table = _bars(["2024-01-01 00:00:00", "2024-01-01 00:01:00"])
    policy = _policy(timezone="UNKNOWN", timezone_evidence=EvidenceStatus.UNKNOWN)

    result = canonicalize(table, policy)

    assert result.frame is None
    assert result.gate_results[1].status is GateStatus.BLOCKED
    assert "TIMEZONE_EVIDENCE_UNKNOWN" in _finding_codes(result, 1)


def test_unknown_period_semantics_block_utc_output() -> None:
    table = _bars(["2024-01-01 00:00:00"])
    policy = _policy(period=PeriodSemantics.UNKNOWN, period_evidence=EvidenceStatus.UNKNOWN)

    result = canonicalize(table, policy)

    assert result.frame is None
    assert "TIMESTAMP_PERIOD_SEMANTICS_UNKNOWN" in _finding_codes(result, 1)


def test_explicit_iana_timezone_is_converted_to_utc() -> None:
    table = _bars(["2024-01-15 12:00:00", "2024-01-15 12:01:00"])

    result = canonicalize(table, _policy(timezone="Europe/Berlin"))

    assert result.frame is not None
    assert result.frame["timestamp"].iloc[0] == pd.Timestamp("2024-01-15 11:00:00Z")


def test_mixed_aware_and_naive_timestamps_are_rejected() -> None:
    table = _bars(["2024-01-01 00:00:00", "2024-01-01T00:01:00Z"])

    result = canonicalize(table, _policy(timezone="UTC"))

    assert result.frame is None
    assert "MIXED_AWARE_NAIVE_TIMESTAMPS" in _finding_codes(result, 1)


@pytest.mark.parametrize(
    ("timestamp", "reason"),
    [
        ("2024-11-03 01:30:00", "DST_AMBIGUOUS_TIMESTAMP"),
        ("2024-03-10 02:30:00", "DST_NONEXISTENT_TIMESTAMP"),
    ],
)
def test_dst_ambiguity_and_nonexistence_are_reported(timestamp: str, reason: str) -> None:
    result = canonicalize(_bars([timestamp]), _policy(timezone="America/New_York"))

    assert result.frame is None
    assert result.gate_results[1].status is GateStatus.BLOCKED
    assert reason in _finding_codes(result, 1)


def test_explicit_dst_resolution_policy_is_deterministic() -> None:
    table = _bars(["2024-11-03 01:30:00"])
    policy = _policy(
        timezone="America/New_York",
        ambiguous=DSTAmbiguousPolicy.EARLIEST,
        nonexistent=DSTNonexistentPolicy.SHIFT_FORWARD,
    )

    first = canonicalize(table, policy)
    second = canonicalize(table, policy)

    assert first.frame is not None
    assert first.serialized_frame() == second.serialized_frame()


def test_identical_duplicate_is_rejected_by_default() -> None:
    row = _bars([pd.Timestamp("2024-01-01T00:00:00Z")]).iloc[0]
    table = pd.DataFrame([row, row])

    result = canonicalize(table, _policy())

    assert result.frame is None
    assert "DUPLICATE_TIMESTAMPS" in _finding_codes(result, 1)


def test_conflicting_duplicate_is_rejected_by_default() -> None:
    table = _bars(
        [pd.Timestamp("2024-01-01T00:00:00Z"), pd.Timestamp("2024-01-01T00:00:00Z")]
    )

    result = canonicalize(table, _policy())

    assert result.frame is None
    assert "CONFLICTING_DUPLICATE_TIMESTAMPS" in _finding_codes(result, 1)


def test_explicit_duplicate_repair_preserves_source_row_lineage() -> None:
    table = _bars(
        [pd.Timestamp("2024-01-01T00:00:00Z"), pd.Timestamp("2024-01-01T00:00:00Z")]
    )
    policy = _policy(
        duplicate_policy=DuplicatePolicy.KEEP_LAST,
        validation_mode=ValidationMode.REPAIR,
    )

    result = canonicalize(table, policy)

    assert result.frame is not None
    assert len(result.frame) == 1
    assert result.source_rows == ((0, 1),)
    assert result.repairs[0].action == "KEEP_LAST"
    assert result.repairs[0].source_rows == (0, 1)


def test_out_of_order_timestamps_fail_without_silent_sorting() -> None:
    table = _bars(
        [pd.Timestamp("2024-01-01T00:01:00Z"), pd.Timestamp("2024-01-01T00:00:00Z")]
    )

    result = canonicalize(table, _policy())

    assert result.frame is None
    assert "NON_MONOTONIC_TIMESTAMPS" in _finding_codes(result, 1)


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("open", np.nan, "NAN_VALUES"),
        ("open", "not-a-number", "NONNUMERIC_OHLC_VALUES"),
        ("close", np.inf, "INFINITE_VALUES"),
        ("close", -np.inf, "INFINITE_VALUES"),
        ("volume", -1.0, "NEGATIVE_VOLUME"),
        ("high", 90.0, "INVALID_HIGH_GEOMETRY"),
        ("low", 120.0, "INVALID_LOW_GEOMETRY"),
    ],
)
def test_numeric_and_ohlc_violations_are_reported(
    column: str,
    value: object,
    reason: str,
) -> None:
    table = _bars([pd.Timestamp("2024-01-01T00:00:00Z")])
    if isinstance(value, str):
        table[column] = table[column].astype(object)
    table.loc[0, column] = value

    result = canonicalize(table, _policy())

    assert result.frame is None
    assert reason in _finding_codes(result, 2)


def test_missing_canonical_column_fails_g1_and_blocks_g3() -> None:
    table = _bars([pd.Timestamp("2024-01-01T00:00:00Z")]).drop(columns="volume")

    result = canonicalize(table, _policy())

    assert result.gate_results[0].status is GateStatus.FAIL
    assert result.gate_results[2].status is GateStatus.BLOCKED
    assert "MISSING_CANONICAL_COLUMNS" in _finding_codes(result, 0)


def test_parser_row_width_shift_and_decision_diagnostics_fail_g1() -> None:
    table = _bars([pd.Timestamp("2024-01-01T00:00:00Z")])
    value = CanonicalInput(
        table,
        parser_decision="UNSUPPORTED",
        row_width_mismatch_rows=(0,),
        shifted_field_rows=(0,),
    )

    result = canonicalize(value, _policy())

    codes = _finding_codes(result, 0)
    assert result.frame is None
    assert {
        "ROW_WIDTH_MISMATCH",
        "SILENT_FIELD_SHIFT_DETECTED",
        "UNSUPPORTED_PARSER_DECISION",
    }.issubset(codes)


def test_declared_positive_price_policy_is_enforced_without_market_assumption() -> None:
    table = _bars([pd.Timestamp("2024-01-01T00:00:00Z")])
    table.loc[0, ["open", "high", "low", "close"]] = [0.0, 1.0, -1.0, 0.5]
    base = _policy()
    policy = CanonicalizationPolicy(
        timestamp=base.timestamp,
        price_unit=PriceUnitDeclaration(
            unit="DECLARED_TEST_UNIT",
            evidence_status=EvidenceStatus.DECLARED,
            strictly_positive=True,
        ),
    )

    result = canonicalize(table, policy)

    assert "NONPOSITIVE_PRICE_POLICY" in _finding_codes(result, 2)


def test_duplicate_column_name_is_detected() -> None:
    table = _bars([pd.Timestamp("2024-01-01T00:00:00Z")])
    table = pd.concat([table, table[["volume"]]], axis=1)

    result = canonicalize(table, _policy())

    assert result.frame is None
    assert "DUPLICATE_COLUMN_NAMES" in _finding_codes(result, 0)
