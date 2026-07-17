"""Auditable downstream eligibility decisions and callback guard."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from .contracts import (
    EligibilityBlock,
    EligibilityDecision,
    EligibilityRequirement,
    GateId,
    GateReport,
    GateStatus,
)


T = TypeVar("T")


@dataclass(frozen=True)
class GuardedExecution(Generic[T]):
    decision: EligibilityDecision
    output: T | None


def evaluate_eligibility(
    report: GateReport,
    requirement: EligibilityRequirement,
) -> EligibilityDecision:
    """Require one unique PASS result for every requested gate."""

    by_gate = defaultdict(list)
    for result in report.results:
        by_gate[result.gate_id].append(result)

    blocks: list[EligibilityBlock] = []
    empty_g1 = next(
        (
            result
            for result in by_gate.get(GateId.G1_SCHEMA_PARSING, [])
            if result.checked_record_count == 0
            or any(
                finding.reason_code == "EMPTY_CANONICAL_INPUT"
                for finding in result.findings
            )
        ),
        None,
    )
    if empty_g1 is not None:
        blocks.append(
            EligibilityBlock(
                gate_id=GateId.G1_SCHEMA_PARSING,
                status=empty_g1.status,
                reason_code="EMPTY_DATASET",
                message="Downstream execution requires a non-empty canonical dataset.",
            )
        )
    for gate_id in requirement.required_gates:
        matches = by_gate.get(gate_id, [])
        if not matches:
            blocks.append(
                EligibilityBlock(
                    gate_id=gate_id,
                    status=None,
                    reason_code="MISSING_GATE_RESULT",
                    message="Required gate result is missing.",
                )
            )
            continue
        if len(matches) > 1:
            blocks.append(
                EligibilityBlock(
                    gate_id=gate_id,
                    status=None,
                    reason_code="DUPLICATE_GATE_RESULT",
                    message="Required gate has multiple results.",
                )
            )
            continue
        result = matches[0]
        if result.status is not GateStatus.PASS:
            blocks.append(
                EligibilityBlock(
                    gate_id=gate_id,
                    status=result.status,
                    reason_code=result.reason_code,
                    message=result.message,
                )
            )
    return EligibilityDecision(
        profile=requirement.profile,
        eligible=not blocks,
        evaluated_gates=requirement.required_gates,
        blocking_gates=tuple(blocks),
    )


def execute_if_eligible(
    report: GateReport,
    requirement: EligibilityRequirement,
    callback: Callable[[], T],
) -> GuardedExecution[T]:
    """Invoke a downstream callback only after eligibility succeeds."""

    decision = evaluate_eligibility(report, requirement)
    if not decision.eligible:
        return GuardedExecution(decision=decision, output=None)
    return GuardedExecution(decision=decision, output=callback())
