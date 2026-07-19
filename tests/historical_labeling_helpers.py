from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pipelines.historical_labeling.artifact import (
    HistoricalLabelingFixtureArtifact,
    build_fixture_artifact,
)
from pipelines.historical_labeling.policies import ResearchPolicyBundle, load_policy


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = (
    REPOSITORY_ROOT
    / "configs"
    / "research"
    / "abshodeh-historical-labeling-v1.json"
)
ARTIFACT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "audits"
    / "artifacts"
    / "KAN-13-market-event-labeling-fixture.json"
)


@lru_cache(maxsize=1)
def policy() -> ResearchPolicyBundle:
    return load_policy(POLICY_PATH)


@lru_cache(maxsize=1)
def artifact() -> HistoricalLabelingFixtureArtifact:
    return build_fixture_artifact(policy(), REPOSITORY_ROOT)
