from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pipelines.behavioral_fingerprint.aggregation import (
    build_behavioral_fingerprint,
)
from pipelines.behavioral_fingerprint.contracts import (
    BehavioralFingerprintArtifact,
)
from pipelines.behavioral_fingerprint.policies import (
    BehavioralFingerprintPolicy,
    load_policy,
)
from pipelines.canonical import ReconciliationTolerance
from pipelines.historical_labeling.contracts import (
    CalendarSemanticsEvidence,
    EligibilityEvidenceState,
    HistoricalExtractionResult,
)
from pipelines.historical_labeling.fixtures import (
    synthetic_calendar_evidence,
    synthetic_canonical_policy,
    synthetic_eligible_m1_frame,
    synthetic_eligible_m5_frame,
    synthetic_eligible_manifest,
    synthetic_eligible_policy,
    synthetic_resampling_policy,
)
from pipelines.historical_labeling.pilot import run_gated_pilot
from tests.historical_labeling_helpers import policy as historical_policy


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = (
    REPOSITORY_ROOT
    / "configs"
    / "research"
    / "abshodeh-behavioral-fingerprint-v1.json"
)
TEST_CODE_REVISION = "test-revision-kan15"


@lru_cache(maxsize=1)
def fingerprint_policy() -> BehavioralFingerprintPolicy:
    return load_policy(POLICY_PATH)


@lru_cache(maxsize=1)
def extraction() -> HistoricalExtractionResult:
    configured = synthetic_eligible_policy(historical_policy())
    manifest, record = synthetic_eligible_manifest(configured)
    execution = run_gated_pilot(
        synthetic_eligible_m1_frame(),
        reconciliation_table=synthetic_eligible_m5_frame(),
        manifest=manifest,
        manifest_record=record,
        policy=configured,
        canonical_policy=synthetic_canonical_policy(),
        resampling_policy=synthetic_resampling_policy(),
        reconciliation_tolerance=ReconciliationTolerance(),
        repository_root=REPOSITORY_ROOT,
        calendar_evidence=synthetic_calendar_evidence(),
    )
    assert execution.eligible_output is not None
    return execution.eligible_output


@lru_cache(maxsize=1)
def artifact() -> BehavioralFingerprintArtifact:
    return build_behavioral_fingerprint(
        extraction(),
        policy=fingerprint_policy(),
        code_revision=TEST_CODE_REVISION,
    )


def reorder_extraction(
    source: HistoricalExtractionResult,
) -> HistoricalExtractionResult:
    return HistoricalExtractionResult.create(
        source_dataset_id=source.source_dataset_id,
        source_sha256=source.source_sha256,
        policy_bundle_version=source.policy_bundle_version,
        policy_sha256=source.policy_sha256,
        eligibility_profile=source.eligibility_profile,
        gate_audit=tuple(reversed(source.gate_audit)),
        labeling_evidence=source.labeling_evidence,
        events=tuple(reversed(source.events)),
        features=tuple(reversed(source.features)),
        labels=tuple(reversed(source.labels)),
        censoring=tuple(reversed(source.censoring)),
        feature_ineligibility=tuple(reversed(source.feature_ineligibility)),
        catalog_generated=True,
    )
