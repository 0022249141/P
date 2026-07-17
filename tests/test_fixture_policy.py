from __future__ import annotations

import ast
import shlex
from pathlib import Path

import pytest

from core.dataset_manifest import PROTECTED_DIRECTORIES


pytest_plugins = ("pytester",)


def _is_research_marker(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "research"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    )


def _module_has_research_mark(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets):
            continue
        value = node.value
        if _is_research_marker(value):
            return True
        if isinstance(value, (ast.List, ast.Tuple)) and any(
            _is_research_marker(element) for element in value.elts
        ):
            return True
    return False


def _has_any_research_marker(tree: ast.Module) -> bool:
    return any(_is_research_marker(node) for node in ast.walk(tree))


def _protected_references(tree: ast.Module) -> set[str]:
    protected_names = ("raw" + "_data", "data" + "_clean", "data" + "_features")
    references: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        normalized = node.value.replace("\\", "/")
        parts = set(part for part in normalized.split("/") if part)
        references.update(name for name in protected_names if name in parts)
    return references


def test_integration_and_research_markers_are_registered(pytestconfig) -> None:
    markers = pytestconfig.getini("markers")

    assert any(marker.startswith("integration:") for marker in markers)
    assert any(marker.startswith("research:") for marker in markers)


def test_research_is_excluded_by_default(pytestconfig, request) -> None:
    configured_addopts = pytestconfig.getini("addopts")
    tokens = (
        list(configured_addopts)
        if isinstance(configured_addopts, list)
        else shlex.split(configured_addopts)
    )
    assert "-m" in tokens
    assert "not research" in tokens

    research_root = Path(__file__).resolve().parent / "research"
    assert all(research_root not in Path(item.path).resolve().parents for item in request.session.items)


def test_marker_expression_excludes_research_and_allows_explicit_selection(
    pytester,
) -> None:
    pytester.makeini(
        """[pytest]
addopts = -m "not research"
markers =
    research: tests intentionally selected for research execution
"""
    )
    pytester.makepyfile(
        """import pytest

def test_ordinary():
    assert True

@pytest.mark.research
def test_research():
    assert True
"""
    )

    default_result = pytester.runpytest("-q")
    default_result.assert_outcomes(passed=1, deselected=1)

    research_result = pytester.runpytest("-q", "-m", "research")
    research_result.assert_outcomes(passed=1, deselected=1)


def test_integration_or_marker_text_does_not_authorize_protected_access() -> None:
    protected_name = "raw" + "_data"
    integration_tree = ast.parse(
        "import pytest\n"
        "pytestmark = pytest.mark.integration\n"
        f'DATASET = "{protected_name}/sample.csv"\n'
    )
    marker_text_tree = ast.parse(
        'NOTE = "pytest.mark.research"\n'
        f'DATASET = "{protected_name}/sample.csv"\n'
    )

    assert _protected_references(integration_tree) == {protected_name}
    assert _module_has_research_mark(integration_tree) is False
    assert _protected_references(marker_text_tree) == {protected_name}
    assert _has_any_research_marker(marker_text_tree) is False


@pytest.mark.integration
def test_integration_marker_does_not_bypass_runtime_corpus_guard() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    protected_directory = repository_root / PROTECTED_DIRECTORIES[0]
    dataset = next(protected_directory.glob("*.csv"))

    with pytest.raises(AssertionError, match="requires a module-level research marker"):
        dataset.read_bytes()


def test_protected_corpus_access_requires_research_module_policy() -> None:
    tests_root = Path(__file__).resolve().parent
    research_root = tests_root / "research"
    violations: list[str] = []

    for test_file in sorted(tests_root.rglob("*.py")):
        tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=str(test_file))
        in_research_directory = research_root in test_file.resolve().parents
        module_marked = _module_has_research_mark(tree)
        references = _protected_references(tree)

        if in_research_directory and not module_marked:
            violations.append(f"{test_file.name}: missing module-level research marker")
        if not in_research_directory and _has_any_research_marker(tree):
            violations.append(f"{test_file.name}: research marker outside tests/research")
        if references and not (in_research_directory and module_marked):
            violations.append(
                f"{test_file.name}: protected references require tests/research module policy"
            )

    assert violations == []
