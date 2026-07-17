from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipelines.canonical import (
    BoundaryConvention,
    CalendarBehavior,
    GateStatus,
    IncompleteBinPolicy,
    PeriodSemantics,
    ReconciliationTolerance,
    ResamplingError,
    ResamplingPolicy,
    VolumeAggregation,
    reconcile_bars,
    resample_bars,
)


def _m1_bars(periods: int, *, start: str = "2024-01-01T00:00:00Z") -> pd.DataFrame:
    opens = np.arange(periods, dtype=float) + 100.0
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start, periods=periods, freq="min", tz="UTC"),
            "open": opens,
            "high": opens + 2.0,
            "low": opens - 1.0,
            "close": opens + 1.0,
            "volume": np.arange(periods, dtype=float) + 1.0,
        }
    )


def _policy(
    target: str,
    *,
    incomplete: IncompleteBinPolicy = IncompleteBinPolicy.REJECT,
    origin: str = "epoch",
    period: PeriodSemantics = PeriodSemantics.PERIOD_START,
    label: BoundaryConvention | None = None,
    closed: BoundaryConvention | None = None,
) -> ResamplingPolicy:
    default_boundary = (
        BoundaryConvention.LEFT
        if period is PeriodSemantics.PERIOD_START
        else BoundaryConvention.RIGHT
    )
    return ResamplingPolicy(
        policy_version="resample-v1",
        source_timeframe="M1",
        target_timeframe=target,
        source_period_semantics=period,
        timestamp_label=label or default_boundary,
        closed_boundary=closed or default_boundary,
        origin=origin,
        timezone="UTC",
        calendar_behavior=CalendarBehavior.CONTINUOUS,
        calendar_version="continuous-utc-v1",
        incomplete_bin_policy=incomplete,
        volume_aggregation=VolumeAggregation.SUM,
    )


@pytest.mark.parametrize(
    ("target", "minutes"),
    [("M5", 5), ("M15", 15), ("M30", 30), ("H1", 60), ("H4", 240), ("D1", 1440)],
)
def test_all_required_m1_targets_are_supported(target: str, minutes: int) -> None:
    result = resample_bars(_m1_bars(minutes), _policy(target))

    assert len(result.frame) == 1
    assert result.source_rows == (tuple(range(minutes)),)
    assert result.incomplete_bin_count == 0


def test_m1_to_m5_and_m15_aggregation_is_deterministic() -> None:
    m5_first = resample_bars(_m1_bars(15), _policy("M5"))
    m5_second = resample_bars(_m1_bars(15), _policy("M5"))
    m15 = resample_bars(_m1_bars(15), _policy("M15"))

    assert len(m5_first.frame) == 3
    assert m5_first.frame.iloc[0].to_dict() == {
        "timestamp": pd.Timestamp("2024-01-01T00:00:00Z"),
        "open": 100.0,
        "high": 106.0,
        "low": 99.0,
        "close": 105.0,
        "volume": 15.0,
    }
    assert m15.frame.iloc[0]["close"] == 115.0
    assert m5_first.to_json_bytes() == m5_second.to_json_bytes()


def test_source_period_semantics_control_membership_and_target_timestamp() -> None:
    period_start = resample_bars(
        _m1_bars(5, start="2024-01-01T00:00:00Z"),
        _policy("M5", period=PeriodSemantics.PERIOD_START),
    )
    period_end = resample_bars(
        _m1_bars(5, start="2024-01-01T00:01:00Z"),
        _policy("M5", period=PeriodSemantics.PERIOD_END),
    )

    assert period_start.source_rows == (tuple(range(5)),)
    assert period_start.frame["timestamp"].tolist() == [
        pd.Timestamp("2024-01-01T00:00:00Z")
    ]
    assert period_end.source_rows == (tuple(range(5)),)
    assert period_end.frame["timestamp"].tolist() == [
        pd.Timestamp("2024-01-01T00:05:00Z")
    ]


@pytest.mark.parametrize(
    ("period", "closed"),
    [
        (PeriodSemantics.PERIOD_START, BoundaryConvention.RIGHT),
        (PeriodSemantics.PERIOD_END, BoundaryConvention.LEFT),
    ],
)
def test_incompatible_period_semantics_and_closed_boundary_are_rejected(
    period: PeriodSemantics,
    closed: BoundaryConvention,
) -> None:
    with pytest.raises(ValueError, match="source timestamps require"):
        _policy("M5", period=period, closed=closed)


def test_h1_and_h4_use_explicit_anchor() -> None:
    origin = "2024-01-01T00:00:00Z"
    h1 = resample_bars(_m1_bars(240), _policy("H1", origin=origin))
    h4 = resample_bars(_m1_bars(240), _policy("H4", origin=origin))

    assert list(h1.frame["timestamp"]) == list(
        pd.date_range(origin, periods=4, freq="h", tz="UTC")
    )
    assert list(h4.frame["timestamp"]) == [pd.Timestamp(origin)]


def test_incomplete_target_bin_reject_drop_and_keep_are_explicit() -> None:
    bars = _m1_bars(6)

    with pytest.raises(ResamplingError, match="incomplete target bin"):
        resample_bars(bars, _policy("M5", incomplete=IncompleteBinPolicy.REJECT))

    dropped = resample_bars(bars, _policy("M5", incomplete=IncompleteBinPolicy.DROP))
    kept = resample_bars(bars, _policy("M5", incomplete=IncompleteBinPolicy.KEEP))

    assert len(dropped.frame) == 1
    assert dropped.incomplete_bin_count == 1
    assert len(kept.frame) == 2
    assert kept.incomplete_bin_count == 1


def test_empty_source_and_zero_output_after_drop_are_rejected() -> None:
    with pytest.raises(ResamplingError, match="at least one canonical bar"):
        resample_bars(_m1_bars(0), _policy("M5"))

    with pytest.raises(ResamplingError, match="zero target bars"):
        resample_bars(
            _m1_bars(2),
            _policy("M5", incomplete=IncompleteBinPolicy.DROP),
        )


def test_resampling_rejects_irregular_or_non_utc_source() -> None:
    irregular = _m1_bars(3).drop(index=1).reset_index(drop=True)
    with pytest.raises(ResamplingError, match="contiguous M1"):
        resample_bars(irregular, _policy("M5", incomplete=IncompleteBinPolicy.KEEP))

    naive = _m1_bars(5)
    naive["timestamp"] = naive["timestamp"].dt.tz_localize(None)
    with pytest.raises(ResamplingError, match="timezone-aware"):
        resample_bars(naive, _policy("M5"))


def test_reconciliation_exact_tolerance_and_mismatch() -> None:
    generated = resample_bars(_m1_bars(5), _policy("M5")).frame
    exact = reconcile_bars(generated, generated.copy(), ReconciliationTolerance())
    assert exact.gate_result.status is GateStatus.PASS
    assert exact.result.exact_match_count == 1

    supplied_tolerance = generated.copy()
    supplied_tolerance.loc[0, "close"] += 0.005
    within = reconcile_bars(
        generated,
        supplied_tolerance,
        ReconciliationTolerance(price_absolute="0.01"),
    )
    assert within.gate_result.status is GateStatus.PASS
    assert within.result.tolerance_match_count == 1

    supplied_mismatch = generated.copy()
    supplied_mismatch.loc[0, "close"] += 0.1
    mismatch = reconcile_bars(
        generated,
        supplied_mismatch,
        ReconciliationTolerance(price_absolute="0.01"),
    )
    assert mismatch.gate_result.status is GateStatus.FAIL
    assert mismatch.result.mismatch_count == 1
    assert mismatch.result.field_differences.close == 1


def test_empty_reconciliation_is_blocked_instead_of_passing() -> None:
    empty = _m1_bars(0)

    evaluation = reconcile_bars(empty, empty.copy(), ReconciliationTolerance())

    assert evaluation.gate_result.status is GateStatus.BLOCKED
    assert evaluation.gate_result.reason_code == "G5_EMPTY_RECONCILIATION_BLOCKED"
    assert evaluation.result.exact_match_count == 0


def test_reconciliation_reports_missing_and_extra_target_bars() -> None:
    generated = resample_bars(_m1_bars(10), _policy("M5")).frame
    supplied_missing = generated.iloc[:1].copy()
    missing = reconcile_bars(generated, supplied_missing, ReconciliationTolerance())
    assert missing.result.missing_target_bars == 1
    assert missing.gate_result.status is GateStatus.FAIL

    extra_row = generated.iloc[-1:].copy()
    extra_row["timestamp"] = extra_row["timestamp"] + pd.Timedelta(minutes=5)
    supplied_extra = pd.concat([generated, extra_row], ignore_index=True)
    extra = reconcile_bars(generated, supplied_extra, ReconciliationTolerance())
    assert extra.result.extra_target_bars == 1
    assert extra.gate_result.status is GateStatus.FAIL


def test_reconciliation_serialization_is_byte_identical() -> None:
    generated = resample_bars(_m1_bars(5), _policy("M5")).frame

    first = reconcile_bars(generated, generated.copy(), ReconciliationTolerance())
    second = reconcile_bars(generated, generated.copy(), ReconciliationTolerance())

    assert first.to_json_bytes() == second.to_json_bytes()
