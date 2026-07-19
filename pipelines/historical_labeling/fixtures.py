"""Synthetic KAN-13 fixtures for every outcome and censoring policy class."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd

from core.dataset_manifest import MANIFEST_SCHEMA_VERSION, PARSER_SCHEMA_VERSION, RECORD_KEYS
from pipelines.canonical import (
    BoundaryConvention,
    CalendarBehavior,
    CalendarPolicy,
    CanonicalizationPolicy,
    EvidenceStatus as CanonicalEvidenceStatus,
    IncompleteBinPolicy,
    PeriodSemantics,
    ResamplingPolicy,
    TimestampSemantics,
    VolumeAggregation,
)
from pipelines.historical_labeling.contracts import (
    AsOfFeatureSnapshot,
    CalendarSemanticsEvidence,
    CensorReason,
    EligibilityEvidenceState,
    EventDirection,
    EventType,
    LabelingEvidence,
    MarketEventIdentity,
    OutcomeClass,
)
from pipelines.historical_labeling.policies import (
    PilotDatasetPolicy,
    ResearchPolicyBundle,
)


SYNTHETIC_SOURCE_SHA256 = "a" * 64


def synthetic_event(
    policy: ResearchPolicyBundle,
    direction: EventDirection,
    *,
    cutoff: datetime | None = None,
) -> MarketEventIdentity:
    eligible = cutoff or datetime(2025, 1, 6, 12, 0, tzinfo=timezone.utc)
    origin = eligible - timedelta(minutes=10)
    event_type = (
        EventType.SWING_HIGH
        if direction is EventDirection.ABOVE
        else EventType.SWING_LOW
    )
    return MarketEventIdentity.create(
        schema_version="1.0.0",
        event_policy_version=policy.event_source.policy_version,
        market="ABSHODEH_FIXTURE",
        symbol="SYNTHETIC",
        timeframe="M5",
        source_timeframe="M1",
        source_dataset_id="synthetic-kan13-v1",
        source_sha256="a" * 64,
        implementation_identifier=policy.event_source.implementation_identifier,
        source_parameters=policy.event_source.parameter_strings(),
        source_parameter_sha256=policy.event_source.parameter_sha256(),
        event_type=event_type,
        direction=direction,
        level_type=event_type.value,
        level_price=Decimal("100"),
        level_origin_timestamp=origin,
        observation_timestamp=origin,
        confirmation_or_availability_timestamp=eligible,
        first_feature_eligible_timestamp=eligible,
    )


def synthetic_snapshot(
    policy: ResearchPolicyBundle,
    event: MarketEventIdentity,
) -> AsOfFeatureSnapshot:
    local = pd.Timestamp(event.first_feature_eligible_timestamp).tz_convert(
        policy.session.timezone
    )
    return AsOfFeatureSnapshot(
        event_id=event.event_id,
        feature_policy_version=policy.features.policy_version,
        snapshot_timestamp=event.first_feature_eligible_timestamp,
        atr_value=Decimal("1"),
        atr_lookback_bars=policy.features.atr_lookback_bars,
        prior_touch_count=1,
        prior_touch_lookback_bars=policy.features.prior_touch_lookback_bars,
        level_age_seconds=600,
        approach_velocity_atr=Decimal("0.5"),
        approach_lookback_bars=policy.features.approach_lookback_bars,
        approach_overlap_ratio=Decimal("0.4"),
        compression_lookback_bars=policy.features.compression_lookback_bars,
        range_expansion_ratio=Decimal("1.2"),
        range_expansion_lookback_bars=policy.features.range_expansion_lookback_bars,
        body_ratio=Decimal("0.5"),
        upper_wick_ratio=Decimal("0.25"),
        lower_wick_ratio=Decimal("0.25"),
        penetration_at_snapshot_atr=Decimal("0"),
        session_date=local.strftime("%Y-%m-%d"),
        neutral_session_bucket="15:00-18:00",
        htf_location=None,
        source_bar_count=20,
    )


def synthetic_labeling_evidence(
    *,
    source_status: EligibilityEvidenceState = EligibilityEvidenceState.PASS,
    calendar_status: EligibilityEvidenceState = EligibilityEvidenceState.PASS,
) -> LabelingEvidence:
    return LabelingEvidence(
        source_status=source_status,
        source_profile="SYNTHETIC_G0_G5_V1",
        source_reason_code=f"SYNTHETIC_SOURCE_{source_status.value}",
        calendar_status=calendar_status,
        calendar_policy_version="synthetic-complete-session-v1",
        calendar_reason_code=f"SYNTHETIC_CALENDAR_{calendar_status.value}",
    )


def synthetic_calendar_evidence() -> CalendarSemanticsEvidence:
    return CalendarSemanticsEvidence(
        status=EligibilityEvidenceState.PASS,
        policy_version="synthetic-complete-session-v1",
        reason_code="SYNTHETIC_SESSION_AND_CALENDAR_COMPLETE",
    )


def synthetic_eligible_m5_frame() -> pd.DataFrame:
    count = 100
    timestamps = pd.date_range(
        "2025-01-06T05:30:00Z",
        periods=count,
        freq="5min",
        tz="UTC",
    )
    rows = [
        {
            "timestamp": timestamp,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 100.0,
        }
        for timestamp in timestamps
    ]
    rows[60].update(open=100.0, high=110.0, low=99.0, close=106.0)
    rows[80].update(open=100.0, high=101.0, low=90.0, close=94.0)
    return pd.DataFrame(rows)


def synthetic_eligible_m1_frame() -> pd.DataFrame:
    rows = []
    for target in synthetic_eligible_m5_frame().itertuples(index=False):
        for minute in range(5):
            close = float(target.close) if minute == 4 else float(target.open)
            high = (
                float(target.high)
                if minute == 0
                else max(float(target.open), close)
            )
            low = (
                float(target.low)
                if minute == 0
                else min(float(target.open), close)
            )
            rows.append(
                {
                    "timestamp": target.timestamp + pd.Timedelta(minutes=minute),
                    "open": float(target.open),
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": float(target.volume) / 5.0,
                }
            )
    return pd.DataFrame(rows)


def synthetic_eligible_policy(
    policy: ResearchPolicyBundle,
) -> ResearchPolicyBundle:
    dataset = PilotDatasetPolicy(
        dataset_id="synthetic-kan13-eligible-m1-v1",
        dataset_path="tests/fixtures/synthetic-kan13-eligible-m1.csv",
        source_timeframe="M1",
        event_timeframe="M5",
        reconciliation_path="tests/fixtures/synthetic-kan13-reconciliation-m5.csv",
        diagnostic_timeframe="H1",
        market="ABSHODEH_FIXTURE",
        symbol="SYNTHETIC",
    )
    return policy.model_copy(update={"dataset": dataset})


def synthetic_eligible_manifest(
    policy: ResearchPolicyBundle,
) -> tuple[dict[str, object], dict[str, object]]:
    frame = synthetic_eligible_m1_frame()
    record = {key: "evidence" for key in RECORD_KEYS}
    record.update(
        {
            "path": policy.dataset.dataset_path,
            "sha256": SYNTHETIC_SOURCE_SHA256,
            "bytes": 12345,
            "row_count": len(frame),
            "first_timestamp": str(frame["timestamp"].iloc[0]),
            "last_timestamp": str(frame["timestamp"].iloc[-1]),
            "parser_schema_version": PARSER_SCHEMA_VERSION,
            "parser_decision": {
                "value": "IN_MEMORY_DATAFRAME",
                "evidence_status": "DECLARED",
            },
        }
    )
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "datasets": [record],
    }
    return manifest, record


def synthetic_canonical_policy() -> CanonicalizationPolicy:
    return CanonicalizationPolicy(
        timestamp=TimestampSemantics(
            timezone="UTC",
            timezone_evidence=CanonicalEvidenceStatus.DECLARED,
            period_semantics=PeriodSemantics.PERIOD_START,
            period_evidence=CanonicalEvidenceStatus.DECLARED,
        ),
        calendar=CalendarPolicy(
            policy_version="synthetic-continuous-utc-v1",
            behavior=CalendarBehavior.CONTINUOUS,
            expected_interval_seconds=60,
            timezone="UTC",
        ),
    )


def synthetic_resampling_policy() -> ResamplingPolicy:
    return ResamplingPolicy(
        policy_version="synthetic-m1-to-m5-v1",
        source_timeframe="M1",
        target_timeframe="M5",
        source_period_semantics=PeriodSemantics.PERIOD_START,
        timestamp_label=BoundaryConvention.LEFT,
        closed_boundary=BoundaryConvention.LEFT,
        origin="epoch",
        timezone="UTC",
        calendar_behavior=CalendarBehavior.CONTINUOUS,
        calendar_version="synthetic-continuous-utc-v1",
        incomplete_bin_policy=IncompleteBinPolicy.REJECT,
        volume_aggregation=VolumeAggregation.SUM,
    )


def _base_future(outcome: OutcomeClass) -> list[tuple[float, float, float, float]]:
    neutral = (100.0, 100.05, 99.95, 100.0)
    values = [neutral for _ in range(12)]
    if outcome is OutcomeClass.DIRECT_CONTINUATION:
        values[0] = (100.0, 101.2, 99.95, 101.1)
    elif outcome is OutcomeClass.ACCEPTANCE_THEN_EXPANSION:
        values[0] = (100.0, 100.25, 99.95, 100.2)
        values[1] = (100.2, 100.35, 100.1, 100.3)
        values[2] = (100.3, 101.2, 100.2, 101.1)
    elif outcome is OutcomeClass.SWEEP_PULLBACK_CONTINUATION:
        values[0] = (100.0, 100.2, 99.6, 99.7)
        values[1] = (99.7, 100.5, 99.65, 100.4)
        values[2] = (100.4, 101.2, 100.3, 101.1)
    elif outcome is OutcomeClass.FALSE_BREAK_REENTRY:
        values[0] = (100.0, 100.2, 99.8, 99.9)
        values[1] = (99.9, 100.0, 98.8, 98.9)
    elif outcome is OutcomeClass.FULL_RANGE_REVERSAL:
        values[0] = (100.0, 100.05, 98.8, 98.9)
    elif outcome is not OutcomeClass.NO_RESOLUTION:
        raise ValueError("unsupported resolved synthetic outcome")
    return values


def _reflect(
    values: list[tuple[float, float, float, float]]
) -> list[tuple[float, float, float, float]]:
    return [
        (200.0 - open_, 200.0 - low, 200.0 - high, 200.0 - close)
        for open_, high, low, close in values
    ]


def synthetic_outcome_frame(
    event: MarketEventIdentity,
    outcome: OutcomeClass,
) -> pd.DataFrame:
    values = _base_future(outcome)
    if event.direction is EventDirection.BELOW:
        values = _reflect(values)
    start = pd.Timestamp(event.first_feature_eligible_timestamp)
    timestamps = [start] + [
        start + pd.Timedelta(minutes=5 * index) for index in range(1, 13)
    ]
    rows = [(100.0, 100.05, 99.95, 100.0), *values]
    if event.direction is EventDirection.BELOW:
        rows[0] = _reflect([rows[0]])[0]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [row[0] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[3] for row in rows],
            "volume": [100.0] * len(rows),
        }
    )


def synthetic_ambiguous_frame(event: MarketEventIdentity) -> pd.DataFrame:
    frame = synthetic_outcome_frame(event, OutcomeClass.NO_RESOLUTION)
    if event.direction is EventDirection.ABOVE:
        frame.loc[1, ["high", "low"]] = [101.2, 98.8]
    else:
        frame.loc[1, ["high", "low"]] = [101.2, 98.8]
    return frame


def synthetic_censor_frame(
    event: MarketEventIdentity,
    reason: CensorReason,
) -> pd.DataFrame:
    frame = synthetic_outcome_frame(event, OutcomeClass.NO_RESOLUTION)
    if reason is CensorReason.DATASET_END:
        result = frame.iloc[:1].copy()
        result.loc[:, "timestamp"] = (
            result["timestamp"] - pd.Timedelta(minutes=5)
        )
        return result
    if reason is CensorReason.INSUFFICIENT_FUTURE_HORIZON:
        return frame.iloc[:6].copy()
    if reason is CensorReason.MISSING_BARS:
        frame.loc[5:, "timestamp"] = frame.loc[5:, "timestamp"] + pd.Timedelta(minutes=5)
        return frame
    if reason is CensorReason.SESSION_BOUNDARY:
        raise ValueError("session-boundary fixture requires a boundary-specific event")
    if reason is CensorReason.INTRABAR_PATH_AMBIGUOUS:
        return synthetic_ambiguous_frame(event)
    return frame


__all__ = [
    "synthetic_censor_frame",
    "synthetic_calendar_evidence",
    "synthetic_canonical_policy",
    "synthetic_eligible_m1_frame",
    "synthetic_eligible_m5_frame",
    "synthetic_eligible_manifest",
    "synthetic_eligible_policy",
    "synthetic_event",
    "synthetic_labeling_evidence",
    "synthetic_outcome_frame",
    "synthetic_resampling_policy",
    "synthetic_snapshot",
]
