from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from pipelines.historical_labeling.contracts import (
    CensorReason,
    EventDirection,
    OutcomeClass,
)
from pipelines.historical_labeling.fixtures import (
    synthetic_censor_frame,
    synthetic_event,
    synthetic_outcome_frame,
    synthetic_snapshot,
)
from pipelines.historical_labeling.labels import label_historical_outcome
from tests.historical_labeling_helpers import artifact, policy


RESOLVED_OUTCOMES = (
    OutcomeClass.DIRECT_CONTINUATION,
    OutcomeClass.SWEEP_PULLBACK_CONTINUATION,
    OutcomeClass.FALSE_BREAK_REENTRY,
    OutcomeClass.ACCEPTANCE_THEN_EXPANSION,
    OutcomeClass.FULL_RANGE_REVERSAL,
    OutcomeClass.NO_RESOLUTION,
)


@pytest.mark.parametrize("direction", tuple(EventDirection))
@pytest.mark.parametrize("outcome", RESOLVED_OUTCOMES)
def test_every_outcome_is_covered_with_high_low_symmetry(
    direction: EventDirection,
    outcome: OutcomeClass,
) -> None:
    event = synthetic_event(policy(), direction)
    result = label_historical_outcome(
        synthetic_outcome_frame(event, outcome),
        event,
        synthetic_snapshot(policy(), event),
        label_policy=policy().labels,
        session_policy=policy().session,
    )

    assert result.label.outcome_class is outcome
    assert result.label.horizon_status.value == "COMPLETE"
    assert result.censoring is None


def test_high_low_symmetric_cases_have_identical_metrics() -> None:
    for outcome in RESOLVED_OUTCOMES:
        labels = []
        for direction in EventDirection:
            event = synthetic_event(policy(), direction)
            labels.append(
                label_historical_outcome(
                    synthetic_outcome_frame(event, outcome),
                    event,
                    synthetic_snapshot(policy(), event),
                    label_policy=policy().labels,
                    session_policy=policy().session,
                ).label
            )
        fields = (
            "outcome_class",
            "penetration_depth_atr",
            "pullback_depth_atr",
            "mae_atr",
            "mfe_atr",
            "bars_outside_level",
            "time_to_destination_seconds",
            "final_destination_class",
        )
        assert tuple(getattr(labels[0], field) for field in fields) == tuple(
            getattr(labels[1], field) for field in fields
        )


def test_fixture_artifact_covers_every_outcome_and_censor_reason() -> None:
    results = artifact().fixture_results

    assert {item.observed_outcome for item in results} == set(OutcomeClass)
    assert {
        item.observed_censor_reason
        for item in results
        if item.observed_censor_reason is not None
    } == set(CensorReason)
    assert all(item.expected_outcome is item.observed_outcome for item in results)
    assert all(
        item.expected_censor_reason is item.observed_censor_reason for item in results
    )


def test_precedence_distinguishes_acceptance_sweep_direct_and_false_break() -> None:
    expected = {
        OutcomeClass.ACCEPTANCE_THEN_EXPANSION,
        OutcomeClass.SWEEP_PULLBACK_CONTINUATION,
        OutcomeClass.DIRECT_CONTINUATION,
        OutcomeClass.FALSE_BREAK_REENTRY,
    }
    observed = set()
    event = synthetic_event(policy(), EventDirection.ABOVE)
    snapshot = synthetic_snapshot(policy(), event)
    for outcome in expected:
        observed.add(
            label_historical_outcome(
                synthetic_outcome_frame(event, outcome),
                event,
                snapshot,
                label_policy=policy().labels,
                session_policy=policy().session,
            ).label.outcome_class
        )
    assert observed == expected


def test_intrabar_terminal_conflict_is_censored() -> None:
    event = synthetic_event(policy(), EventDirection.ABOVE)
    frame = synthetic_censor_frame(event, CensorReason.INTRABAR_PATH_AMBIGUOUS)
    result = label_historical_outcome(
        frame,
        event,
        synthetic_snapshot(policy(), event),
        label_policy=policy().labels,
        session_policy=policy().session,
    )

    assert result.label.outcome_class is OutcomeClass.CENSORED
    assert result.label.conflict_status == "INTRABAR_PATH_AMBIGUOUS"
    assert result.censoring is not None
    assert result.censoring.primary_reason is CensorReason.INTRABAR_PATH_AMBIGUOUS


def test_session_boundary_censors_before_outcome_resolution() -> None:
    event = synthetic_event(
        policy(),
        EventDirection.ABOVE,
        cutoff=datetime(2025, 1, 6, 18, 25, tzinfo=timezone.utc),
    )
    result = label_historical_outcome(
        synthetic_outcome_frame(event, OutcomeClass.DIRECT_CONTINUATION),
        event,
        synthetic_snapshot(policy(), event),
        label_policy=policy().labels,
        session_policy=policy().session,
    )

    assert result.label.outcome_class is OutcomeClass.CENSORED
    assert result.censoring is not None
    assert result.censoring.primary_reason is CensorReason.SESSION_BOUNDARY


def test_label_is_bounded_and_ignores_candles_after_the_horizon() -> None:
    event = synthetic_event(policy(), EventDirection.ABOVE)
    frame = synthetic_outcome_frame(event, OutcomeClass.NO_RESOLUTION)
    after = frame.iloc[-1].copy()
    after["timestamp"] = frame["timestamp"].iloc[-1] + pd.Timedelta(minutes=5)
    after["high"] = 10000.0
    after["low"] = 1.0
    after["close"] = 5000.0
    extended = pd.concat([frame, pd.DataFrame([after])], ignore_index=True)

    base = label_historical_outcome(
        frame,
        event,
        synthetic_snapshot(policy(), event),
        label_policy=policy().labels,
        session_policy=policy().session,
    )
    mutated = label_historical_outcome(
        extended,
        event,
        synthetic_snapshot(policy(), event),
        label_policy=policy().labels,
        session_policy=policy().session,
    )

    assert base == mutated
