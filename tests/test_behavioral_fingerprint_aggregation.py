from __future__ import annotations

from pipelines.behavioral_fingerprint.aggregation import build_behavioral_fingerprint
from pipelines.behavioral_fingerprint.contracts import EvidenceClassification
from tests.behavioral_fingerprint_helpers import (
    TEST_CODE_REVISION,
    artifact,
    extraction,
    fingerprint_policy,
    reorder_extraction,
)


def test_aggregation_is_byte_exact_under_collection_permutation() -> None:
    source = extraction()
    first = build_behavioral_fingerprint(
        source,
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )
    second = build_behavioral_fingerprint(
        reorder_extraction(source),
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )

    assert first.to_json_bytes() == second.to_json_bytes()


def test_counts_and_view_coverage_are_conserved() -> None:
    source = extraction()
    result = artifact()

    assert result.unique_eligible_event_count == source.event_count
    assert result.unique_resolved_label_count + result.unique_censored_label_count == (
        source.event_count
    )
    assert result.unassigned_feature_ineligible_count == (
        source.feature_ineligibility_count
    )
    assert sum(result.feature_ineligibility_reasons.values()) == (
        source.feature_ineligibility_count
    )
    assert result.cell_assignment_missing_semantics_count == 0
    assert all(
        view.assigned_event_count == source.event_count
        for view in result.view_coverage
    )
    assert all(
        cell.resolved_label_count + cell.censored_label_count
        == cell.eligible_event_count
        for cell in result.cells
    )
    assert all(
        sum(cell.outcome_counts.values()) == cell.eligible_event_count
        for cell in result.cells
    )


def test_sparse_support_fails_closed_without_dropping_cells() -> None:
    strict = fingerprint_policy().model_copy(
        update={
            "support": fingerprint_policy().support.model_copy(
                update={"minimum_cell_events": 1_000_000}
            )
        }
    )
    result = build_behavioral_fingerprint(
        extraction(),
        policy=strict,
        code_revision=TEST_CODE_REVISION,
    )

    assert result.cells
    assert all(
        cell.evidence_classification
        is EvidenceClassification.NOT_STATISTICALLY_ELIGIBLE
        for cell in result.cells
    )


def test_only_resolved_labels_enter_metric_and_frequency_denominators() -> None:
    result = artifact()

    for cell in result.cells:
        assert all(
            frequency.resolved_denominator == cell.resolved_label_count
            for frequency in cell.outcome_frequencies
        )
        assert all(
            summary.eligible_count <= cell.resolved_label_count
            for summary in cell.metric_summaries.values()
        )
        assert len(cell.chronological_partitions) == 3
        assert sum(
            partition.eligible_event_count
            for partition in cell.chronological_partitions
        ) == cell.eligible_event_count


def test_g6_pass_does_not_promote_g7_g8_or_g9() -> None:
    statuses = {gate.gate_id: gate.status for gate in artifact().gate_audit}

    assert statuses == {
        "G6_FEATURE_REPRODUCTION": "PASS",
        "G7_ANALYTICAL_ELIGIBILITY": "NOT_EVALUATED",
        "G8_STATISTICAL_ELIGIBILITY": "NOT_EVALUATED",
        "G9_EXECUTION_BACKTEST_ELIGIBILITY": "NOT_EVALUATED",
    }
