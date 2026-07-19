from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from pipelines.historical_labeling.contracts import EventType
from pipelines.historical_labeling.event_source import (
    EventSourceEligibilityError,
    generate_confirmed_swing_events,
    require_kan11_eligible,
)
from pipelines.historical_labeling.features import build_asof_feature_snapshot
from tests.historical_labeling_helpers import REPOSITORY_ROOT, policy


def _source_frame() -> pd.DataFrame:
    count = 100
    close = np.full(count, 100.0)
    open_ = np.full(count, 100.0)
    high = np.full(count, 101.0)
    low = np.full(count, 99.0)
    open_[60], close[60], high[60], low[60] = 100.0, 106.0, 110.0, 99.0
    open_[80], close[80], high[80], low[80] = 100.0, 94.0, 101.0, 90.0
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2025-01-06T08:00:00Z", periods=count, freq="5min"
            ),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(count, 100.0),
        }
    )


def _events(frame: pd.DataFrame):
    configured = policy()
    return generate_confirmed_swing_events(
        frame,
        repository_root=REPOSITORY_ROOT,
        policy=configured.event_source,
        market="ABSHODEH_FIXTURE",
        symbol="SYNTHETIC",
        timeframe="M5",
        source_timeframe="M1",
        source_dataset_id="synthetic-source-v1",
        source_sha256="a" * 64,
    )


def test_swing_adapter_emits_only_confirmed_high_low_events() -> None:
    frame = _source_frame()
    events = _events(frame)

    assert {event.event_type for event in events} == {
        EventType.SWING_HIGH,
        EventType.SWING_LOW,
    }
    assert all(
        event.first_feature_eligible_timestamp
        == event.confirmation_or_availability_timestamp
        > event.level_origin_timestamp
        for event in events
    )
    assert all(
        event.source_parameters
        == ("event_bar_seconds=300", "lookback=2", "min_strength=0.6")
        for event in events
    )
    for event in events:
        origin_index = frame.index[
            frame["timestamp"] == pd.Timestamp(event.level_origin_timestamp)
        ][0]
        confirmation_start = frame["timestamp"].iloc[origin_index + 2]
        assert event.first_feature_eligible_timestamp == (
            confirmation_start + pd.Timedelta(minutes=5)
        ).to_pydatetime()


def test_event_source_is_prefix_invariant_at_declared_confirmation() -> None:
    frame = _source_frame()
    full = _events(frame)
    assert full
    for event in full:
        confirmation = pd.Timestamp(event.first_feature_eligible_timestamp)
        prefix = frame.loc[
            frame["timestamp"] + pd.Timedelta(minutes=5) <= confirmation
        ]
        prefix_events = _events(prefix)
        assert event in prefix_events


def test_event_source_rejects_insufficient_confirmation_and_hash_drift() -> None:
    frame = _source_frame()
    high_origin = frame["timestamp"].iloc[60]
    insufficient = frame.loc[frame["timestamp"] <= high_origin + pd.Timedelta(minutes=5)]
    assert all(event.event_type is not EventType.SWING_HIGH for event in _events(insufficient))

    wrong_policy = policy().event_source.model_copy(
        update={"source_sha256": "b" * 64}
    )
    with pytest.raises(EventSourceEligibilityError, match="source hash differs"):
        generate_confirmed_swing_events(
            frame,
            repository_root=REPOSITORY_ROOT,
            policy=wrong_policy,
            market="ABSHODEH_FIXTURE",
            symbol="SYNTHETIC",
            timeframe="M5",
            source_timeframe="M1",
            source_dataset_id="synthetic-source-v1",
            source_sha256="a" * 64,
        )


def test_kan11_ineligible_observation_is_rejected() -> None:
    with pytest.raises(EventSourceEligibilityError, match="INELIGIBLE"):
        require_kan11_eligible(
            SimpleNamespace(eligibility_classification="INELIGIBLE")
        )
    require_kan11_eligible(
        SimpleNamespace(eligibility_classification="POST_CONFIRMATION")
    )


def test_feature_snapshot_is_prefix_invariant_and_future_mutation_safe() -> None:
    frame = _source_frame()
    event = next(event for event in _events(frame) if event.event_type is EventType.SWING_HIGH)
    cutoff = pd.Timestamp(event.first_feature_eligible_timestamp)
    prefix = frame.loc[frame["timestamp"] <= cutoff].copy()
    full_snapshot = build_asof_feature_snapshot(
        frame,
        event,
        feature_policy=policy().features,
        session_policy=policy().session,
    )
    prefix_snapshot = build_asof_feature_snapshot(
        prefix,
        event,
        feature_policy=policy().features,
        session_policy=policy().session,
    )
    mutated = frame.copy()
    mutated.loc[mutated["timestamp"] > cutoff, ["high", "low", "close"]] = [
        10000.0,
        1.0,
        5000.0,
    ]
    mutated_snapshot = build_asof_feature_snapshot(
        mutated,
        event,
        feature_policy=policy().features,
        session_policy=policy().session,
    )

    assert full_snapshot == prefix_snapshot == mutated_snapshot
    assert full_snapshot.atr_lookback_bars == 14
    assert full_snapshot.herat_status.value == "NOT_EVALUATED"
    assert full_snapshot.xauusd_status.value == "NOT_EVALUATED"


def test_htf_location_uses_only_last_available_completed_bar() -> None:
    frame = _source_frame()
    event = next(event for event in _events(frame) if event.event_type is EventType.SWING_HIGH)
    cutoff = pd.Timestamp(event.first_feature_eligible_timestamp)
    htf = pd.DataFrame(
        {
            "timestamp": [cutoff - pd.Timedelta(hours=1), cutoff + pd.Timedelta(hours=1)],
            "open": [90.0, 0.0],
            "high": [120.0, 10000.0],
            "low": [80.0, 0.0],
            "close": [100.0, 5000.0],
            "volume": [1.0, 1.0],
        }
    )
    snapshot = build_asof_feature_snapshot(
        frame,
        event,
        feature_policy=policy().features,
        session_policy=policy().session,
        htf_frame=htf,
    )

    assert snapshot.htf_location_status.value == "DERIVED"
    assert snapshot.htf_location == pytest.approx(0.75)


def test_feature_source_contains_no_forbidden_future_operations() -> None:
    source = (
        Path(REPOSITORY_ROOT) / "pipelines/historical_labeling/features.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("shift(-", "center=True", ".bfill(", "backfill"):
        assert forbidden not in source
