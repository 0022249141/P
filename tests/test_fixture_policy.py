from pathlib import Path


def test_integration_and_research_markers_are_registered(pytestconfig) -> None:
    markers = pytestconfig.getini("markers")

    assert any(marker.startswith("integration:") for marker in markers)
    assert any(marker.startswith("research:") for marker in markers)


def test_ordinary_test_sources_do_not_reference_protected_corpus() -> None:
    protected_names = ("raw" + "_data", "data" + "_clean", "data" + "_features")
    current_file = Path(__file__).resolve()
    violations: list[str] = []

    for test_file in sorted(current_file.parent.rglob("*.py")):
        if test_file.resolve() == current_file:
            continue
        source = test_file.read_text(encoding="utf-8")
        if "pytest.mark.integration" in source or "pytest.mark.research" in source:
            continue
        for protected_name in protected_names:
            if f"{protected_name}/" in source or f"{protected_name}\\" in source:
                violations.append(f"{test_file.name}: {protected_name}")

    assert violations == []
