"""Past-only feature snapshots for confirmed market events."""

from __future__ import annotations

from decimal import Decimal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from pipelines.historical_labeling.contracts import (
    AsOfFeatureSnapshot,
    EventDirection,
    EvidenceStatus,
    MarketEventIdentity,
)
from pipelines.historical_labeling.policies import FeaturePolicy, SessionPolicy


class FeatureEligibilityError(ValueError):
    pass


def _decimal(value: float) -> Decimal:
    if not np.isfinite(value):
        raise FeatureEligibilityError("feature values must be finite")
    return Decimal(str(round(float(value), 12)))


def _prepare_prefix(
    frame: pd.DataFrame,
    event: MarketEventIdentity,
    *,
    event_bar_seconds: int,
) -> pd.DataFrame:
    required = ("timestamp", "open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise FeatureEligibilityError(f"feature source is missing columns: {missing}")
    prepared = frame.loc[:, required].copy(deep=True)
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], utc=True)
    prepared = prepared.sort_values("timestamp", kind="stable")
    if prepared["timestamp"].duplicated().any():
        raise FeatureEligibilityError("feature timestamps must be unique")
    cutoff = pd.Timestamp(event.first_feature_eligible_timestamp)
    prepared["_availability_timestamp"] = prepared["timestamp"] + pd.Timedelta(
        seconds=event_bar_seconds
    )
    prefix = prepared.loc[
        prepared["_availability_timestamp"] <= cutoff
    ].reset_index(drop=True)
    if prefix.empty or prefix["_availability_timestamp"].iloc[-1] != cutoff:
        raise FeatureEligibilityError("feature eligibility timestamp is absent")
    return prefix.drop(columns="_availability_timestamp")


def _true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        (
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ),
        axis=1,
    ).max(axis=1)


def _overlap_ratio(window: pd.DataFrame) -> float:
    ratios: list[float] = []
    for left_index in range(len(window) - 1):
        left = window.iloc[left_index]
        right = window.iloc[left_index + 1]
        overlap = max(0.0, min(left.high, right.high) - max(left.low, right.low))
        denominator = max(float(left.high - left.low), float(right.high - right.low))
        ratios.append(0.0 if denominator <= 0 else overlap / denominator)
    return float(np.mean(ratios)) if ratios else 0.0


def _session_bucket(local: pd.Timestamp, policy: SessionPolicy) -> str:
    current = local.strftime("%H:%M")
    for bucket in policy.neutral_buckets:
        start, end = bucket.split("-")
        if start <= current < end or (current == end and end == "22:00"):
            return bucket
    return "OUT_OF_SESSION"


def build_asof_feature_snapshot(
    frame: pd.DataFrame,
    event: MarketEventIdentity,
    *,
    feature_policy: FeaturePolicy,
    session_policy: SessionPolicy,
    htf_frame: pd.DataFrame | None = None,
) -> AsOfFeatureSnapshot:
    """Compute features only from bars available at the event cutoff."""

    prefix = _prepare_prefix(
        frame,
        event,
        event_bar_seconds=feature_policy.event_bar_seconds,
    )
    timestamps = prefix["timestamp"]
    origin_timestamp = pd.Timestamp(event.level_origin_timestamp)
    origin_matches = np.flatnonzero((timestamps == origin_timestamp).to_numpy())
    if len(origin_matches) != 1:
        raise FeatureEligibilityError("event origin must identify one source bar")
    origin_index = int(origin_matches[0])
    required_history = max(
        feature_policy.atr_lookback_bars + 1,
        feature_policy.approach_lookback_bars + 1,
        feature_policy.compression_lookback_bars,
        feature_policy.range_expansion_lookback_bars + 1,
    )
    if origin_index + 1 < required_history:
        raise FeatureEligibilityError("insufficient past-only history for feature policy")

    true_range = _true_range(prefix)
    atr_series = true_range.rolling(
        feature_policy.atr_lookback_bars,
        min_periods=feature_policy.atr_lookback_bars,
    ).mean()
    atr = float(atr_series.iloc[-1])
    if not np.isfinite(atr) or atr <= 0:
        raise FeatureEligibilityError("past-only ATR is unavailable at eligibility")

    level = float(event.level_price)
    tolerance = float(feature_policy.prior_touch_tolerance_atr) * atr
    touch_start = max(0, origin_index - feature_policy.prior_touch_lookback_bars)
    prior = prefix.iloc[touch_start:origin_index]
    touches = int(
        ((prior["low"] <= level + tolerance) & (prior["high"] >= level - tolerance)).sum()
    )

    approach_start = origin_index - feature_policy.approach_lookback_bars
    origin_close = float(prefix["close"].iloc[origin_index])
    prior_close = float(prefix["close"].iloc[approach_start])
    direction_sign = 1.0 if event.direction is EventDirection.ABOVE else -1.0
    velocity = direction_sign * (origin_close - prior_close) / atr

    compression_start = origin_index - feature_policy.compression_lookback_bars + 1
    overlap = _overlap_ratio(prefix.iloc[compression_start : origin_index + 1])
    expansion_start = origin_index - feature_policy.range_expansion_lookback_bars
    baseline = float(true_range.iloc[expansion_start:origin_index].mean())
    origin_bar = prefix.iloc[origin_index]
    origin_range = float(origin_bar.high - origin_bar.low)
    if baseline <= 0 or origin_range <= 0:
        raise FeatureEligibilityError("range features require positive bar ranges")
    expansion = origin_range / baseline
    body = abs(float(origin_bar.close - origin_bar.open))
    upper_wick = float(origin_bar.high - max(origin_bar.open, origin_bar.close))
    lower_wick = float(min(origin_bar.open, origin_bar.close) - origin_bar.low)

    snapshot_bar = prefix.iloc[-1]
    if event.direction is EventDirection.ABOVE:
        penetration = (float(snapshot_bar.high) - level) / atr
    else:
        penetration = (level - float(snapshot_bar.low)) / atr

    htf_location: Decimal | None = None
    htf_status = EvidenceStatus.NOT_EVALUATED
    if htf_frame is not None and not htf_frame.empty:
        htf = htf_frame.copy(deep=True)
        htf["timestamp"] = pd.to_datetime(htf["timestamp"], utc=True)
        htf["_availability_timestamp"] = htf["timestamp"] + pd.Timedelta(
            seconds=feature_policy.htf_bar_seconds
        )
        eligible_htf = htf.loc[
            htf["_availability_timestamp"]
            <= pd.Timestamp(event.first_feature_eligible_timestamp)
        ].sort_values("timestamp", kind="stable")
        if not eligible_htf.empty:
            bar = eligible_htf.iloc[-1]
            span = float(bar.high - bar.low)
            if span > 0:
                htf_location = _decimal((level - float(bar.low)) / span)
                htf_status = EvidenceStatus.DERIVED

    local = pd.Timestamp(event.first_feature_eligible_timestamp).tz_convert(
        ZoneInfo(session_policy.timezone)
    )
    return AsOfFeatureSnapshot(
        event_id=event.event_id,
        feature_policy_version=feature_policy.policy_version,
        snapshot_timestamp=event.first_feature_eligible_timestamp,
        atr_value=_decimal(atr),
        atr_lookback_bars=feature_policy.atr_lookback_bars,
        prior_touch_count=touches,
        prior_touch_lookback_bars=feature_policy.prior_touch_lookback_bars,
        level_age_seconds=int(
            (
                event.first_feature_eligible_timestamp
                - event.level_origin_timestamp
            ).total_seconds()
        ),
        approach_velocity_atr=_decimal(velocity),
        approach_lookback_bars=feature_policy.approach_lookback_bars,
        approach_overlap_ratio=_decimal(overlap),
        compression_lookback_bars=feature_policy.compression_lookback_bars,
        range_expansion_ratio=_decimal(expansion),
        range_expansion_lookback_bars=feature_policy.range_expansion_lookback_bars,
        body_ratio=_decimal(body / origin_range),
        upper_wick_ratio=_decimal(upper_wick / origin_range),
        lower_wick_ratio=_decimal(lower_wick / origin_range),
        penetration_at_snapshot_atr=_decimal(penetration),
        session_date=local.strftime("%Y-%m-%d"),
        neutral_session_bucket=_session_bucket(local, session_policy),
        htf_location=htf_location,
        htf_location_status=htf_status,
        source_bar_count=len(prefix),
    )


__all__ = [
    "FeatureEligibilityError",
    "build_asof_feature_snapshot",
]
