"""Bounded deterministic future labels kept separate from feature models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from pipelines.historical_labeling.contracts import (
    AsOfFeatureSnapshot,
    CensorReason,
    CensoringRecord,
    DestinationClass,
    EventDirection,
    HistoricalOutcomeLabel,
    HorizonStatus,
    EligibilityEvidenceState,
    LabelingEvidence,
    MarketEventIdentity,
    MetricScope,
    OutcomeClass,
)
from pipelines.historical_labeling.policies import LabelPolicy, SessionPolicy


@dataclass(frozen=True)
class LabelingResult:
    label: HistoricalOutcomeLabel
    censoring: CensoringRecord | None


def _decimal(value: float) -> Decimal:
    if not np.isfinite(value):
        raise ValueError("label metrics must be finite")
    return Decimal(str(round(float(value), 12)))


def _prepared(frame: pd.DataFrame, *, period_seconds: int) -> pd.DataFrame:
    required = ("timestamp", "open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"label source is missing columns: {missing}")
    result = frame.loc[:, required].copy(deep=True)
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    result["timestamp"] = result["timestamp"] + pd.Timedelta(seconds=period_seconds)
    result = result.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return result


def _censored(
    event: MarketEventIdentity,
    policy: LabelPolicy,
    reason: CensorReason,
    detail: str,
    *,
    end: pd.Timestamp | None,
    secondary: tuple[CensorReason, ...] = (),
) -> LabelingResult:
    horizon_end = None if end is None else end.to_pydatetime()
    label = HistoricalOutcomeLabel(
        event_id=event.event_id,
        label_policy_version=policy.policy_version,
        horizon_start_timestamp=event.first_feature_eligible_timestamp,
        horizon_end_timestamp=horizon_end,
        maximum_horizon_bars=policy.maximum_horizon_bars,
        maximum_horizon_seconds=policy.maximum_horizon_seconds,
        outcome_class=OutcomeClass.CENSORED,
        metric_scope=MetricScope.NOT_EVALUATED,
        metric_end_timestamp=None,
        metric_bar_count=0,
        penetration_depth_atr=None,
        pullback_depth_atr=None,
        mae_atr=None,
        mfe_atr=None,
        bars_outside_level=0,
        seconds_outside_level=0,
        reentry_timestamp=None,
        acceptance_timestamp=None,
        time_to_destination_seconds=None,
        final_destination_class=DestinationClass.CENSORED,
        horizon_status=(
            HorizonStatus.INSUFFICIENT_HORIZON
            if reason
            in {
                CensorReason.INSUFFICIENT_FUTURE_HORIZON,
                CensorReason.DATASET_END,
            }
            else HorizonStatus.CENSORED
        ),
        conflict_status=(
            "INTRABAR_PATH_AMBIGUOUS"
            if reason is CensorReason.INTRABAR_PATH_AMBIGUOUS
            else "NONE"
        ),
    )
    return LabelingResult(
        label=label,
        censoring=CensoringRecord(
            event_id=event.event_id,
            label_policy_version=policy.policy_version,
            primary_reason=reason,
            secondary_reasons=secondary,
            evidence_start_timestamp=event.first_feature_eligible_timestamp,
            evidence_end_timestamp=horizon_end,
            detail=detail,
        ),
    )


def _inside_session(
    timestamp: pd.Timestamp,
    anchor_date: str,
    policy: SessionPolicy,
) -> bool:
    local = timestamp.tz_convert(ZoneInfo(policy.timezone))
    start = time.fromisoformat(policy.session_start)
    end = time.fromisoformat(policy.session_end)
    return local.strftime("%Y-%m-%d") == anchor_date and start <= local.time() <= end


def _oriented_values(
    horizon: pd.DataFrame,
    event: MarketEventIdentity,
    atr: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    level = float(event.level_price)
    if event.direction is EventDirection.ABOVE:
        outward = (horizon["high"].to_numpy(float) - level) / atr
        inward = (horizon["low"].to_numpy(float) - level) / atr
        closes = (horizon["close"].to_numpy(float) - level) / atr
    else:
        outward = (level - horizon["low"].to_numpy(float)) / atr
        inward = (level - horizon["high"].to_numpy(float)) / atr
        closes = (level - horizon["close"].to_numpy(float)) / atr
    return outward, inward, closes


def _first(mask: np.ndarray) -> int | None:
    positions = np.flatnonzero(mask)
    return None if len(positions) == 0 else int(positions[0])


def _acceptance_index(closes: np.ndarray, threshold: float, count: int) -> int | None:
    consecutive = 0
    for index, value in enumerate(closes):
        consecutive = consecutive + 1 if value >= threshold else 0
        if consecutive >= count:
            return index
    return None


def label_historical_outcome(
    frame: pd.DataFrame,
    event: MarketEventIdentity,
    snapshot: AsOfFeatureSnapshot,
    *,
    label_policy: LabelPolicy,
    session_policy: SessionPolicy,
    evidence: LabelingEvidence,
    upstream_censor_reason: CensorReason | None = None,
) -> LabelingResult:
    """Label one event using only the declared bounded future horizon."""

    if not isinstance(evidence, LabelingEvidence):
        raise TypeError("explicit typed labeling evidence is required")
    if snapshot.event_id != event.event_id:
        raise ValueError("feature and label records must reference the same event")
    if snapshot.snapshot_timestamp != event.first_feature_eligible_timestamp:
        raise ValueError("feature snapshot must be anchored at event eligibility")
    if evidence.source_status is not EligibilityEvidenceState.PASS:
        return _censored(
            event,
            label_policy,
            CensorReason.FAILED_ELIGIBILITY,
            f"Source eligibility is {evidence.source_status.value}: "
            f"{evidence.source_reason_code}.",
            end=None,
        )
    if evidence.calendar_status is not EligibilityEvidenceState.PASS:
        return _censored(
            event,
            label_policy,
            CensorReason.UNAVAILABLE_CALENDAR_SEMANTICS,
            f"Calendar semantics are {evidence.calendar_status.value}: "
            f"{evidence.calendar_reason_code}.",
            end=None,
        )
    if upstream_censor_reason is not None:
        return _censored(
            event,
            label_policy,
            upstream_censor_reason,
            "An explicit upstream evidence condition censored this event.",
            end=None,
        )

    prepared = _prepared(frame, period_seconds=label_policy.expected_bar_seconds)
    cutoff = pd.Timestamp(event.first_feature_eligible_timestamp)
    future = prepared.loc[prepared["timestamp"] > cutoff].reset_index(drop=True)
    if future.empty:
        return _censored(
            event,
            label_policy,
            CensorReason.DATASET_END,
            "No future bar exists after event eligibility.",
            end=None,
            secondary=(CensorReason.INSUFFICIENT_FUTURE_HORIZON,),
        )

    atr = float(snapshot.atr_value)
    continuation_threshold = float(label_policy.continuation_atr)
    reversal_threshold = float(label_policy.reversal_atr)
    anchor_date = cutoff.tz_convert(ZoneInfo(session_policy.timezone)).strftime("%Y-%m-%d")
    candidates = future.iloc[: label_policy.maximum_horizon_bars].copy(deep=True)
    terminal_kind: str | None = None
    processed_count = 0
    previous_timestamp = cutoff
    for index, row in candidates.iterrows():
        timestamp = pd.Timestamp(row["timestamp"])
        if int((candidates["timestamp"] == timestamp).sum()) > 1:
            end = None if processed_count == 0 else previous_timestamp
            return _censored(
                event,
                label_policy,
                CensorReason.MISSING_BARS,
                "Duplicate M5 evidence exists before a terminal.",
                end=end,
            )
        if not _inside_session(timestamp, anchor_date, session_policy):
            end = None if processed_count == 0 else previous_timestamp
            return _censored(
                event,
                label_policy,
                CensorReason.SESSION_BOUNDARY,
                "Outcome evidence crossed the configured local session before a terminal.",
                end=end,
            )
        delta = int((timestamp - previous_timestamp).total_seconds())
        if delta != label_policy.expected_bar_seconds:
            end = None if processed_count == 0 else previous_timestamp
            return _censored(
                event,
                label_policy,
                CensorReason.MISSING_BARS,
                "Expected M5 evidence is missing or irregular before a terminal.",
                end=end,
            )
        elapsed = int((timestamp - cutoff).total_seconds())
        if elapsed > label_policy.maximum_horizon_seconds:
            end = None if processed_count == 0 else previous_timestamp
            return _censored(
                event,
                label_policy,
                CensorReason.INSUFFICIENT_FUTURE_HORIZON,
                "Outcome evidence exceeded the maximum duration before a terminal.",
                end=end,
            )

        one_bar = candidates.loc[[index]]
        bar_outward, bar_inward, bar_close = _oriented_values(one_bar, event, atr)
        if (
            bar_outward[0] >= continuation_threshold
            and bar_inward[0] <= -reversal_threshold
        ):
            return _censored(
                event,
                label_policy,
                CensorReason.INTRABAR_PATH_AMBIGUOUS,
                "One OHLC bar spans both terminal barriers without observable path order.",
                end=timestamp,
            )

        processed_count += 1
        previous_timestamp = timestamp
        if bar_close[0] >= continuation_threshold:
            terminal_kind = "CONTINUATION"
            break
        if bar_close[0] <= -reversal_threshold:
            terminal_kind = "REVERSAL"
            break

    if terminal_kind is None and processed_count < label_policy.maximum_horizon_bars:
        return _censored(
            event,
            label_policy,
            CensorReason.INSUFFICIENT_FUTURE_HORIZON,
            "Fewer than the required future bars exist and no terminal was observed.",
            end=None if processed_count == 0 else previous_timestamp,
        )

    horizon = candidates.iloc[:processed_count].copy(deep=True)
    outward, inward, closes = _oriented_values(horizon, event, atr)
    terminal_index = processed_count - 1 if terminal_kind is not None else None

    penetration_index = _first(outward >= float(label_policy.penetration_atr))
    reentry_index: int | None = None
    pullback_index: int | None = None
    if penetration_index is not None:
        after_penetration = closes[penetration_index:]
        relative_reentry = _first(
            after_penetration <= -float(label_policy.reentry_close_atr)
        )
        relative_pullback = _first(
            after_penetration <= -float(label_policy.qualifying_pullback_atr)
        )
        if relative_reentry is not None:
            reentry_index = penetration_index + relative_reentry
        if relative_pullback is not None:
            pullback_index = penetration_index + relative_pullback

    acceptance_index = _acceptance_index(
        closes,
        float(label_policy.acceptance_close_atr),
        label_policy.acceptance_consecutive_closes,
    )
    if terminal_kind == "REVERSAL":
        if (
            penetration_index is not None
            and reentry_index is not None
            and penetration_index <= reentry_index < terminal_index
        ):
            outcome = OutcomeClass.FALSE_BREAK_REENTRY
        else:
            outcome = OutcomeClass.FULL_RANGE_REVERSAL
        destination = DestinationClass.INWARD_BARRIER
    elif terminal_kind == "CONTINUATION":
        if acceptance_index is not None and acceptance_index < terminal_index:
            outcome = OutcomeClass.ACCEPTANCE_THEN_EXPANSION
        elif (
            penetration_index is not None
            and reentry_index is not None
            and pullback_index is not None
            and pullback_index < terminal_index
        ):
            outcome = OutcomeClass.SWEEP_PULLBACK_CONTINUATION
        else:
            outcome = OutcomeClass.DIRECT_CONTINUATION
        destination = DestinationClass.OUTWARD_BARRIER
    else:
        outcome = OutcomeClass.NO_RESOLUTION
        destination = DestinationClass.NONE
        terminal_index = None

    timestamps = horizon["timestamp"].tolist()
    reentry_timestamp = (
        None if reentry_index is None else timestamps[reentry_index].to_pydatetime()
    )
    acceptance_timestamp = (
        None
        if acceptance_index is None
        else timestamps[acceptance_index].to_pydatetime()
    )
    time_to_destination = (
        None
        if terminal_index is None
        else int((timestamps[terminal_index] - cutoff).total_seconds())
    )
    bars_outside = int((closes > 0).sum())
    metric_scope = (
        MetricScope.PRE_TERMINAL_INCLUSIVE
        if terminal_index is not None
        else MetricScope.COMPLETE_HORIZON_NO_TERMINAL
    )
    metric_end = horizon["timestamp"].iloc[-1].to_pydatetime()
    return LabelingResult(
        label=HistoricalOutcomeLabel(
            event_id=event.event_id,
            label_policy_version=label_policy.policy_version,
            horizon_start_timestamp=event.first_feature_eligible_timestamp,
            horizon_end_timestamp=horizon["timestamp"].iloc[-1].to_pydatetime(),
            maximum_horizon_bars=label_policy.maximum_horizon_bars,
            maximum_horizon_seconds=label_policy.maximum_horizon_seconds,
            outcome_class=outcome,
            metric_scope=metric_scope,
            metric_end_timestamp=metric_end,
            metric_bar_count=len(horizon),
            penetration_depth_atr=_decimal(max(0.0, float(np.max(outward)))),
            pullback_depth_atr=_decimal(max(0.0, float(-np.min(closes)))),
            mae_atr=_decimal(max(0.0, float(-np.min(inward)))),
            mfe_atr=_decimal(max(0.0, float(np.max(outward)))),
            bars_outside_level=bars_outside,
            seconds_outside_level=bars_outside * label_policy.expected_bar_seconds,
            reentry_timestamp=reentry_timestamp,
            acceptance_timestamp=acceptance_timestamp,
            time_to_destination_seconds=time_to_destination,
            final_destination_class=destination,
            horizon_status=HorizonStatus.COMPLETE,
            conflict_status="NONE",
        ),
        censoring=None,
    )


__all__ = ["LabelingResult", "label_historical_outcome"]
