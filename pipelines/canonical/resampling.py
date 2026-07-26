"""Deterministic M1-to-HTF resampling under explicit policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from .contracts import (
    CANONICAL_COLUMNS,
    CalendarBehavior,
    CoverageBoundaryPolicy,
    GapPolicy,
    IncompleteBinPolicy,
    ResamplingPolicy,
    SessionEndConvention,
    VolumeAggregation,
)
from .normalization import serialize_canonical_frame


TARGET_MINUTES = {
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


class ResamplingError(ValueError):
    """Raised when explicit resampling preconditions are not met."""


@dataclass(frozen=True)
class ResamplingResult:
    frame: pd.DataFrame
    source_rows: tuple[tuple[int, ...], ...]
    incomplete_bin_count: int
    incomplete_bin_examples: tuple[str, ...]
    dropped_coverage_boundary_bin_count: int
    dropped_coverage_boundary_bin_examples: tuple[str, ...]
    policy: ResamplingPolicy

    def to_json_bytes(self) -> bytes:
        payload = {
            "frame": json.loads(serialize_canonical_frame(self.frame)),
            "incomplete_bin_count": self.incomplete_bin_count,
            "incomplete_bin_examples": self.incomplete_bin_examples,
            "dropped_coverage_boundary_bin_count": (
                self.dropped_coverage_boundary_bin_count
            ),
            "dropped_coverage_boundary_bin_examples": (
                self.dropped_coverage_boundary_bin_examples
            ),
            "policy": self.policy.model_dump(mode="json"),
            "source_rows": self.source_rows,
        }
        text = json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)
        return f"{text}\n".encode("utf-8")


def resample_bars(frame: pd.DataFrame, policy: ResamplingPolicy) -> ResamplingResult:
    """Resample validated UTC M1 bars with no implicit pandas defaults."""

    _validate_source(frame, policy)

    target_minutes = TARGET_MINUTES[policy.target_timeframe]
    expected_count = target_minutes
    rule = f"{target_minutes}min"
    indexed = frame.copy(deep=True)
    indexed["_source_row"] = range(len(indexed))
    indexed = indexed.set_index("timestamp", drop=True)

    output_rows: list[dict[str, Any]] = []
    source_rows: list[tuple[int, ...]] = []
    incomplete_examples: list[str] = []
    dropped_boundary_examples: list[str] = []
    incomplete_count = 0
    first_source_timestamp = pd.Timestamp(indexed.index[0])
    for label, group in _group_source(indexed, rule, policy):
        if group.empty:
            continue
        source_group = tuple(int(row) for row in group["_source_row"].tolist())
        is_incomplete = len(group) != expected_count
        is_partial_coverage_boundary = (
            not output_rows
            and not dropped_boundary_examples
            and policy.coverage_boundary_policy
            is CoverageBoundaryPolicy.DROP_PARTIAL_FIRST
            and first_source_timestamp
            > _first_expected_source_label(
                pd.Timestamp(label),
                target_minutes,
                policy,
            )
        )
        if is_incomplete:
            incomplete_count += 1
            if len(incomplete_examples) < 10:
                incomplete_examples.append(f"{pd.Timestamp(label).isoformat()}:{len(group)}/{expected_count}")
            if is_partial_coverage_boundary:
                dropped_boundary_examples.append(
                    f"{pd.Timestamp(label).isoformat()}:"
                    f"{pd.Timestamp(indexed.index[0]).isoformat()}"
                )
                continue
            if policy.incomplete_bin_policy is IncompleteBinPolicy.REJECT:
                raise ResamplingError(
                    f"incomplete target bin at {pd.Timestamp(label).isoformat()}: "
                    f"{len(group)}/{expected_count} source bars"
                )
            if policy.incomplete_bin_policy is IncompleteBinPolicy.DROP:
                continue

        output_rows.append(
            {
                "timestamp": pd.Timestamp(label),
                "open": group["open"].dropna().iloc[0],
                "high": group["high"].max(),
                "low": group["low"].min(),
                "close": group["close"].dropna().iloc[-1],
                "volume": _aggregate_volume(group["volume"], policy.volume_aggregation),
            }
        )
        source_rows.append(source_group)

    output = pd.DataFrame(output_rows, columns=CANONICAL_COLUMNS)
    if output.empty:
        raise ResamplingError("resampling produced zero target bars")
    output["timestamp"] = pd.DatetimeIndex(output["timestamp"]).tz_convert("UTC")
    return ResamplingResult(
        frame=output,
        source_rows=tuple(source_rows),
        incomplete_bin_count=incomplete_count,
        incomplete_bin_examples=tuple(incomplete_examples),
        dropped_coverage_boundary_bin_count=len(dropped_boundary_examples),
        dropped_coverage_boundary_bin_examples=tuple(dropped_boundary_examples),
        policy=policy,
    )


def _first_expected_source_label(
    target_label: pd.Timestamp,
    target_minutes: int,
    policy: ResamplingPolicy,
) -> pd.Timestamp:
    if policy.source_period_semantics.value == "PERIOD_START":
        return target_label
    return target_label - pd.Timedelta(minutes=target_minutes - 1)


def _validate_source(frame: pd.DataFrame, policy: ResamplingPolicy) -> None:
    if tuple(frame.columns) != CANONICAL_COLUMNS:
        raise ResamplingError("source frame must use exact canonical columns and order")
    if frame.empty:
        raise ResamplingError("source frame must contain at least one canonical bar")
    timestamps = pd.DatetimeIndex(frame["timestamp"])
    if timestamps.tz is None:
        raise ResamplingError("source timestamps must be timezone-aware")
    if str(timestamps.tz) != "UTC":
        raise ResamplingError("canonical resampling requires UTC source timestamps")
    if policy.calendar_behavior is CalendarBehavior.CONTINUOUS and policy.timezone != "UTC":
        raise ResamplingError("continuous canonical resampling requires UTC binning")
    if policy.calendar_behavior is CalendarBehavior.VERSIONED_SESSION:
        try:
            ZoneInfo(policy.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ResamplingError("versioned-session timezone is unavailable") from exc
    if not timestamps.is_monotonic_increasing or timestamps.has_duplicates:
        raise ResamplingError("source timestamps must be unique and monotonic")
    if len(timestamps) > 1:
        epoch_ns = timestamps.to_numpy(dtype="datetime64[ns]").astype(np.int64)
        deltas = np.diff(epoch_ns) / 1_000_000_000
        if not np.all((deltas > 0) & (deltas % 60 == 0)):
            raise ResamplingError("source timestamps must be positive whole-minute intervals")
        if policy.source_gap_policy is GapPolicy.REJECT and not np.all(deltas == 60):
            raise ResamplingError("source bars must be contiguous M1 before resampling")
    numeric = frame[list(CANONICAL_COLUMNS[1:])].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ResamplingError("source canonical numeric values must be finite")


def _pandas_origin(value: str) -> str | pd.Timestamp:
    if value in {"epoch", "start", "start_day", "end", "end_day"}:
        return value
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ResamplingError("timestamp origin must be timezone-aware")
    return timestamp.tz_convert("UTC")


def _group_source(
    indexed: pd.DataFrame,
    rule: str,
    policy: ResamplingPolicy,
) -> list[tuple[pd.Timestamp, pd.DataFrame]]:
    if policy.calendar_behavior is CalendarBehavior.CONTINUOUS:
        grouper = pd.Grouper(
            freq=rule,
            label=policy.timestamp_label.value,
            closed=policy.closed_boundary.value,
            origin=_pandas_origin(policy.origin),
            offset=policy.offset,
        )
        return list(indexed.groupby(grouper, sort=True))

    local = indexed.copy(deep=True)
    local.index = local.index.tz_convert(ZoneInfo(policy.timezone))
    start = time.fromisoformat(policy.session_start or "00:00:00")
    end = time.fromisoformat(policy.session_end or "00:00:00")
    anchors = [
        _session_anchor(
            timestamp
            if policy.source_period_semantics.value == "PERIOD_START"
            else timestamp - pd.Timedelta(minutes=1),
            start,
            end,
            policy.session_end_convention,
        )
        for timestamp in local.index
    ]
    if any(anchor is None for anchor in anchors):
        raise ResamplingError(
            "versioned-session resampling received out-of-session analytical rows"
        )
    local["_session_anchor"] = anchors
    groups: list[tuple[pd.Timestamp, pd.DataFrame]] = []
    for _, session in local.groupby("_session_anchor", sort=True):
        session = session.drop(columns="_session_anchor")
        grouper = pd.Grouper(
            freq=rule,
            label=policy.timestamp_label.value,
            closed=policy.closed_boundary.value,
            origin=_session_origin(policy.origin, session.index[0]),
            offset=policy.offset,
        )
        groups.extend(session.groupby(grouper, sort=True))
    return groups


def _session_origin(value: str, first_timestamp: pd.Timestamp) -> str | pd.Timestamp:
    if value == "start_day":
        return first_timestamp.normalize()
    if value in {"start", "end", "end_day"}:
        return value
    if value == "epoch":
        return "epoch"
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ResamplingError("timestamp origin must be timezone-aware")
    return timestamp.tz_convert(first_timestamp.tz)


def _time_in_session(
    value: time,
    start: time,
    end: time,
    end_convention: SessionEndConvention,
) -> bool:
    include_end = end_convention is SessionEndConvention.INCLUSIVE
    if start <= end:
        return start <= value <= end if include_end else start <= value < end
    return value >= start or (value <= end if include_end else value < end)


def _session_anchor(
    timestamp: pd.Timestamp,
    start: time,
    end: time,
    end_convention: SessionEndConvention,
) -> object | None:
    value = timestamp.time()
    if not _time_in_session(value, start, end, end_convention):
        return None
    if start <= end or value >= start:
        return timestamp.date()
    return (timestamp - pd.Timedelta(days=1)).date()


def _aggregate_volume(series: pd.Series, aggregation: VolumeAggregation) -> Any:
    if aggregation is VolumeAggregation.SUM:
        return series.sum()
    if aggregation is VolumeAggregation.FIRST:
        return series.iloc[0]
    if aggregation is VolumeAggregation.LAST:
        return series.iloc[-1]
    raise ResamplingError("volume aggregation must be declared")
