"""Deterministic M1-to-HTF resampling under explicit policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .contracts import (
    CANONICAL_COLUMNS,
    CalendarBehavior,
    IncompleteBinPolicy,
    ResamplingPolicy,
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
    policy: ResamplingPolicy

    def to_json_bytes(self) -> bytes:
        payload = {
            "frame": json.loads(serialize_canonical_frame(self.frame)),
            "incomplete_bin_count": self.incomplete_bin_count,
            "incomplete_bin_examples": self.incomplete_bin_examples,
            "policy": self.policy.model_dump(mode="json"),
            "source_rows": self.source_rows,
        }
        text = json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)
        return f"{text}\n".encode("utf-8")


def resample_bars(frame: pd.DataFrame, policy: ResamplingPolicy) -> ResamplingResult:
    """Resample validated UTC M1 bars with no implicit pandas defaults."""

    _validate_source(frame, policy)
    if policy.calendar_behavior is not CalendarBehavior.CONTINUOUS:
        raise ResamplingError(
            "VERSIONED_SESSION resampling requires a supplied calendar binning implementation"
        )

    target_minutes = TARGET_MINUTES[policy.target_timeframe]
    expected_count = target_minutes
    rule = f"{target_minutes}min"
    origin = _pandas_origin(policy.origin)
    indexed = frame.copy(deep=True)
    indexed["_source_row"] = range(len(indexed))
    indexed = indexed.set_index("timestamp", drop=True)
    grouper = pd.Grouper(
        freq=rule,
        label=policy.timestamp_label.value,
        closed=policy.closed_boundary.value,
        origin=origin,
        offset=policy.offset,
    )

    output_rows: list[dict[str, Any]] = []
    source_rows: list[tuple[int, ...]] = []
    incomplete_examples: list[str] = []
    incomplete_count = 0
    for label, group in indexed.groupby(grouper, sort=True):
        if group.empty:
            continue
        source_group = tuple(int(row) for row in group["_source_row"].tolist())
        is_incomplete = len(group) != expected_count
        if is_incomplete:
            incomplete_count += 1
            if len(incomplete_examples) < 10:
                incomplete_examples.append(f"{pd.Timestamp(label).isoformat()}:{len(group)}/{expected_count}")
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
    if not output.empty:
        output["timestamp"] = pd.DatetimeIndex(output["timestamp"]).tz_convert("UTC")
    return ResamplingResult(
        frame=output,
        source_rows=tuple(source_rows),
        incomplete_bin_count=incomplete_count,
        incomplete_bin_examples=tuple(incomplete_examples),
        policy=policy,
    )


def _validate_source(frame: pd.DataFrame, policy: ResamplingPolicy) -> None:
    if tuple(frame.columns) != CANONICAL_COLUMNS:
        raise ResamplingError("source frame must use exact canonical columns and order")
    timestamps = pd.DatetimeIndex(frame["timestamp"])
    if timestamps.tz is None:
        raise ResamplingError("source timestamps must be timezone-aware")
    if str(timestamps.tz) != "UTC" or policy.timezone != "UTC":
        raise ResamplingError("KAN-10 canonical resampling requires explicit UTC timezone")
    if not timestamps.is_monotonic_increasing or timestamps.has_duplicates:
        raise ResamplingError("source timestamps must be unique and monotonic")
    if len(timestamps) > 1:
        epoch_ns = timestamps.to_numpy(dtype="datetime64[ns]").astype(np.int64)
        deltas = np.diff(epoch_ns) / 1_000_000_000
        if not np.all(deltas == 60):
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


def _aggregate_volume(series: pd.Series, aggregation: VolumeAggregation) -> Any:
    if aggregation is VolumeAggregation.SUM:
        return series.sum()
    if aggregation is VolumeAggregation.FIRST:
        return series.iloc[0]
    if aggregation is VolumeAggregation.LAST:
        return series.iloc[-1]
    raise ResamplingError("volume aggregation must be declared")
