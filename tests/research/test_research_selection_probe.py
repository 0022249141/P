import pytest


pytestmark = pytest.mark.research


def test_research_selection_probe() -> None:
    """Prove the explicit research command selects research-marked tests."""

    assert True
