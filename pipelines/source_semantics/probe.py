"""Deterministic candidate probes and policy builders for KAN-14."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import pandas as pd

from pipelines.canonical import (
    BoundaryConvention,
    CalendarBehavior,
    CalendarPolicy,
    CanonicalizationPolicy,
    CoverageBoundaryPolicy,
    EvidenceStatus,
    PeriodSemantics,
    ResamplingPolicy,
    TimestampSemantics,
)
from pipelines.source_semantics.contracts import (
    CandidateDisposition,
    DailyReconciliationEvidence,
    ReconciliationCandidateEvidence,
    SourceSemanticsPolicy,
)


CANONICAL_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


def load_policy(path: Path) -> SourceSemanticsPolicy:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SourceSemanticsPolicy.model_validate(payload)


def policy_sha256(policy: SourceSemanticsPolicy) -> str:
    return hashlib.sha256(policy.to_json_bytes()).hexdigest()


def build_canonical_policy(
    policy: SourceSemanticsPolicy,
    *,
    expected_interval_seconds: int,
) -> CanonicalizationPolicy:
    return CanonicalizationPolicy(
        timestamp=TimestampSemantics(
            timezone=policy.source_timezone,
            timezone_evidence=policy.timezone_evidence.status,
            period_semantics=policy.period_semantics,
            period_evidence=policy.period_evidence.status,
        ),
        gap_policy=policy.source_gap_policy,
        calendar=CalendarPolicy(
            policy_version=policy.policy_version,
            behavior=CalendarBehavior.VERSIONED_SESSION,
            expected_interval_seconds=expected_interval_seconds,
            timezone=policy.source_timezone,
            session_start=policy.session_start,
            session_end=policy.session_end,
            session_end_convention=policy.session_end_convention,
            out_of_session_policy=policy.out_of_session_policy,
        ),
    )


def build_m1_to_m5_policy(policy: SourceSemanticsPolicy) -> ResamplingPolicy:
    return ResamplingPolicy(
        policy_version=f"{policy.policy_version}-m1-to-m5",
        source_timeframe="M1",
        target_timeframe="M5",
        source_period_semantics=policy.period_semantics,
        timestamp_label=BoundaryConvention.LEFT,
        closed_boundary=BoundaryConvention.LEFT,
        origin="start_day",
        timezone=policy.source_timezone,
        calendar_behavior=CalendarBehavior.VERSIONED_SESSION,
        calendar_version=policy.policy_version,
        session_start=policy.session_start,
        session_end=policy.session_end,
        session_end_convention=policy.session_end_convention,
        source_gap_policy=policy.source_gap_policy,
        coverage_boundary_policy=policy.coverage_boundary_policy,
        incomplete_bin_policy=policy.incomplete_bin_policy,
        volume_aggregation=policy.volume_aggregation,
    )


def evaluate_period_candidates(
    lower: pd.DataFrame,
    supplied: pd.DataFrame,
    *,
    policy: SourceSemanticsPolicy,
    source_minutes: int = 1,
    target_minutes: int = 5,
) -> tuple[ReconciliationCandidateEvidence, ...]:
    """Evaluate start/end membership without silently adopting either candidate."""

    if source_minutes <= 0 or target_minutes <= source_minutes:
        raise ValueError("candidate intervals require 0 < source_minutes < target_minutes")
    prepared_lower = _prepare_local(lower, policy)
    prepared_supplied = _prepare_local(supplied, policy)
    results = tuple(
        _evaluate_candidate(
            prepared_lower,
            prepared_supplied,
            policy=policy,
            period_semantics=candidate,
            source_minutes=source_minutes,
            target_minutes=target_minutes,
            minimum_distinct_dates=policy.minimum_distinct_dates,
        )
        for candidate in (PeriodSemantics.PERIOD_START, PeriodSemantics.PERIOD_END)
    )
    promoted = [
        result
        for result in results
        if result.disposition is CandidateDisposition.PROMOTED
    ]
    if len(promoted) != 1 or promoted[0].period_semantics is not PeriodSemantics.PERIOD_START:
        raise ValueError("real-data evidence does not uniquely promote PERIOD_START")
    return results


def reconciliation_overlap(
    generated: pd.DataFrame,
    supplied: pd.DataFrame,
) -> pd.DataFrame:
    """Return the native target interval governed by generated coverage."""

    if generated.empty or supplied.empty:
        return supplied.iloc[0:0].copy()
    timestamps = pd.DatetimeIndex(generated["timestamp"])
    native = supplied.copy(deep=True)
    native_timestamps = pd.DatetimeIndex(native["timestamp"])
    return native.loc[
        (native_timestamps >= timestamps.min())
        & (native_timestamps <= timestamps.max())
    ].reset_index(drop=True)


def sha256_paths(root: Path, paths: Iterable[str]) -> dict[str, str]:
    return {
        path: hashlib.sha256(root.joinpath(path).read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def _prepare_local(
    frame: pd.DataFrame,
    policy: SourceSemanticsPolicy,
) -> pd.DataFrame:
    if tuple(frame.columns) != CANONICAL_COLUMNS:
        raise ValueError("candidate frame must use canonical columns and order")
    prepared = frame.copy(deep=True)
    timestamps = pd.to_datetime(prepared["timestamp"], errors="raise")
    if timestamps.dt.tz is not None:
        timestamps = timestamps.dt.tz_convert(policy.source_timezone).dt.tz_localize(None)
    prepared["timestamp"] = timestamps
    prepared = prepared.sort_values("timestamp", kind="stable").reset_index(drop=True)
    if prepared["timestamp"].duplicated().any():
        raise ValueError("candidate timestamps must be unique")
    return prepared


def _candidate_session_frame(
    frame: pd.DataFrame,
    policy: SourceSemanticsPolicy,
    period_semantics: PeriodSemantics,
) -> pd.DataFrame:
    """Apply session membership in the candidate's own label convention."""

    clock = frame["timestamp"].dt.strftime("%H:%M:%S")
    if period_semantics is PeriodSemantics.PERIOD_START:
        lower = clock >= policy.session_start
        upper = clock < policy.session_end
    else:
        lower = clock > policy.session_start
        upper = clock <= policy.session_end
    inside = (
        lower & upper
        if policy.session_start <= policy.session_end
        else lower | upper
    )
    return frame.loc[inside].reset_index(drop=True)


def _evaluate_candidate(
    lower: pd.DataFrame,
    supplied: pd.DataFrame,
    *,
    policy: SourceSemanticsPolicy,
    period_semantics: PeriodSemantics,
    source_minutes: int,
    target_minutes: int,
    minimum_distinct_dates: int,
) -> ReconciliationCandidateEvidence:
    lower = _candidate_session_frame(lower, policy, period_semantics)
    supplied = _candidate_session_frame(supplied, policy, period_semantics)
    if period_semantics is PeriodSemantics.PERIOD_START:
        label = closed = "left"
    else:
        label = closed = "right"
    lower_indexed = lower.set_index("timestamp")
    generated = (
        lower_indexed.groupby(
            pd.Grouper(
                freq=f"{target_minutes}min",
                label=label,
                closed=closed,
                origin="start_day",
            )
        )
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna(subset=["open"])
    )
    dropped_boundary = 0
    target_delta = pd.Timedelta(minutes=target_minutes)
    source_delta = pd.Timedelta(minutes=source_minutes)
    first_target_label = None if generated.empty else generated.index[0]
    first_expected_source_label = (
        None
        if first_target_label is None
        else first_target_label
        if period_semantics is PeriodSemantics.PERIOD_START
        else first_target_label - target_delta + source_delta
    )
    if (
        policy.coverage_boundary_policy
        is CoverageBoundaryPolicy.DROP_PARTIAL_FIRST
        and not generated.empty
        and not lower.empty
        and first_expected_source_label is not None
        and lower["timestamp"].iloc[0] > first_expected_source_label
    ):
        generated = generated.iloc[1:]
        dropped_boundary = 1

    supplied_indexed = supplied.set_index("timestamp")
    if not generated.empty and not supplied_indexed.empty:
        lower_bound = max(generated.index.min(), supplied_indexed.index.min())
        upper_bound = min(generated.index.max(), supplied_indexed.index.max())
        generated = generated.loc[
            (generated.index >= lower_bound) & (generated.index <= upper_bound)
        ]
        supplied_indexed = supplied_indexed.loc[
            (supplied_indexed.index >= lower_bound)
            & (supplied_indexed.index <= upper_bound)
        ]

    common = generated.index.intersection(supplied_indexed.index)
    generated_only = generated.index.difference(supplied_indexed.index)
    supplied_only = supplied_indexed.index.difference(generated.index)
    generated_common = generated.loc[common]
    supplied_common = supplied_indexed.loc[common]
    price_columns = ["open", "high", "low", "close"]
    ohlc_matches = (
        generated_common[price_columns] == supplied_common[price_columns]
    ).all(axis=1)
    ohlcv_matches = (
        generated_common[list(CANONICAL_COLUMNS[1:])]
        == supplied_common[list(CANONICAL_COLUMNS[1:])]
    ).all(axis=1)
    volume_difference = (
        generated_common["volume"] - supplied_common["volume"]
    ).abs()
    volume_only = ohlc_matches & (volume_difference != 0)

    daily: list[DailyReconciliationEvidence] = []
    all_dates = sorted(
        {
            *[timestamp.strftime("%Y-%m-%d") for timestamp in generated.index],
            *[timestamp.strftime("%Y-%m-%d") for timestamp in supplied_indexed.index],
        }
    )
    for session_date in all_dates:
        generated_date = generated.index.strftime("%Y-%m-%d") == session_date
        supplied_date = supplied_indexed.index.strftime("%Y-%m-%d") == session_date
        common_date = common.strftime("%Y-%m-%d") == session_date
        date_common = common[common_date]
        daily.append(
            DailyReconciliationEvidence(
                session_date=session_date,
                common_count=len(date_common),
                exact_ohlc_count=int(ohlc_matches.loc[date_common].sum()),
                exact_ohlcv_count=int(ohlcv_matches.loc[date_common].sum()),
                generated_only_count=int(generated_date.sum())
                - len(date_common),
                supplied_only_count=int(supplied_date.sum())
                - len(date_common),
            )
        )

    exact_start = (
        period_semantics is PeriodSemantics.PERIOD_START
        and len(common) > 0
        and int(ohlcv_matches.sum()) == len(common)
        and not generated_only.size
        and not supplied_only.size
        and len(daily) >= minimum_distinct_dates
    )
    disposition = (
        CandidateDisposition.PROMOTED
        if exact_start
        else CandidateDisposition.REJECTED
        if len(common)
        else CandidateDisposition.BLOCKED
    )
    maximum_volume_difference = (
        Decimal("0")
        if volume_difference.empty
        else Decimal(str(volume_difference.max()))
    )
    return ReconciliationCandidateEvidence(
        period_semantics=period_semantics,
        disposition=disposition,
        generated_count=len(generated),
        supplied_count=len(supplied_indexed),
        common_count=len(common),
        exact_ohlc_count=int(ohlc_matches.sum()),
        exact_ohlcv_count=int(ohlcv_matches.sum()),
        generated_only_count=len(generated_only),
        supplied_only_count=len(supplied_only),
        volume_only_mismatch_count=int(volume_only.sum()),
        maximum_volume_absolute_difference=format(
            maximum_volume_difference,
            "f",
        ),
        distinct_date_count=len(daily),
        dropped_coverage_boundary_count=dropped_boundary,
        daily_evidence=tuple(daily),
    )


__all__ = [
    "build_canonical_policy",
    "build_m1_to_m5_policy",
    "evaluate_period_candidates",
    "load_policy",
    "policy_sha256",
    "reconciliation_overlap",
    "sha256_paths",
]
