from __future__ import annotations

import builtins
import io
import os
from pathlib import Path
from typing import Any, Callable

import pytest

from core.dataset_manifest import PROTECTED_DIRECTORIES


TESTS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = TESTS_ROOT.parent
RESEARCH_ROOT = TESTS_ROOT / "research"
PROTECTED_ROOTS = tuple(
    (REPOSITORY_ROOT / directory).resolve() for directory in PROTECTED_DIRECTORIES
)


def _module_has_research_mark(item: pytest.Item) -> bool:
    module_marks = getattr(item.module, "pytestmark", ())
    if not isinstance(module_marks, (list, tuple)):
        module_marks = (module_marks,)
    return any(getattr(mark, "name", None) == "research" for mark in module_marks)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Enforce the research directory and module-level marker convention."""

    for item in items:
        item_path = Path(item.path).resolve()
        in_research_directory = RESEARCH_ROOT in item_path.parents
        has_research_marker = item.get_closest_marker("research") is not None
        has_module_mark = _module_has_research_mark(item)

        if in_research_directory and not has_module_mark:
            raise pytest.UsageError(
                f"{item_path} must declare module-level pytestmark = pytest.mark.research"
            )
        if not in_research_directory and has_research_marker:
            raise pytest.UsageError(
                f"{item_path} uses the research marker outside tests/research"
            )


def _is_protected_path(file: object) -> bool:
    if not isinstance(file, (str, bytes, os.PathLike)):
        return False
    try:
        candidate = Path(os.fsdecode(file))
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        candidate = candidate.resolve()
    except (OSError, TypeError, ValueError):
        return False
    return any(candidate.is_relative_to(root) for root in PROTECTED_ROOTS)


def _guarded_open(original: Callable[..., Any]) -> Callable[..., Any]:
    def open_without_research(file: object, *args: object, **kwargs: object) -> Any:
        if _is_protected_path(file):
            raise AssertionError(
                "protected corpus access requires a module-level research marker "
                "under tests/research"
            )
        return original(file, *args, **kwargs)

    return open_without_research


@pytest.fixture(autouse=True)
def block_protected_corpus_for_ordinary_tests(request, monkeypatch) -> None:
    """Prevent unit and integration tests from opening the research corpus."""

    if request.node.get_closest_marker("research") is not None:
        return
    monkeypatch.setattr(builtins, "open", _guarded_open(builtins.open))
    monkeypatch.setattr(io, "open", _guarded_open(io.open))
