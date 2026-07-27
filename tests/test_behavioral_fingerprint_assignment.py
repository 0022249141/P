from __future__ import annotations

from inspect import signature

from pipelines.behavioral_fingerprint.assignment import build_feature_assignments
from tests.behavioral_fingerprint_helpers import (
    TEST_CODE_REVISION,
    extraction,
    fingerprint_policy,
)


def _coordinate(assignment):
    return (
        assignment.event_id,
        assignment.view_id,
        assignment.event_type,
        assignment.direction,
        assignment.neutral_session_bucket,
        assignment.feature_buckets,
    )


def test_assignment_api_has_no_label_namespace() -> None:
    parameters = set(signature(build_feature_assignments).parameters)

    assert "labels" not in parameters
    assert "outcomes" not in parameters
    assert parameters == {"events", "features", "policy", "code_revision"}


def test_assignments_are_exact_under_input_permutation() -> None:
    source = extraction()
    first = build_feature_assignments(
        source.events,
        source.features,
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )
    second = build_feature_assignments(
        tuple(reversed(source.events)),
        tuple(reversed(source.features)),
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )

    assert first == second
    assert len(first) == source.event_count * len(fingerprint_policy().views)


def test_retained_prefix_events_keep_the_same_feature_coordinates() -> None:
    source = extraction()
    cutoff = max(1, source.event_count // 2)
    retained_events = tuple(
        sorted(
            source.events,
            key=lambda item: (
                item.first_feature_eligible_timestamp,
                item.event_id,
            ),
        )[:cutoff]
    )
    retained_ids = {event.event_id for event in retained_events}
    retained_features = tuple(
        feature
        for feature in source.features
        if feature.event_id in retained_ids
    )
    full = build_feature_assignments(
        source.events,
        source.features,
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )
    prefix = build_feature_assignments(
        retained_events,
        retained_features,
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )

    assert {_coordinate(item) for item in prefix} == {
        _coordinate(item) for item in full if item.event_id in retained_ids
    }


def test_label_mutation_cannot_change_assignment() -> None:
    source = extraction()
    before = build_feature_assignments(
        source.events,
        source.features,
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )
    mutated_labels = tuple(
        label.model_copy(update={"conflict_status": "MUTATED_RETROSPECTIVE_ONLY"})
        for label in source.labels
    )
    after = build_feature_assignments(
        source.events,
        source.features,
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )

    assert mutated_labels != source.labels
    assert before == after
