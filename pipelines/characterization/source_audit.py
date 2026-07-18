"""Source loading and static temporal checks for KAN-11."""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys
from typing import Iterable

from pipelines.characterization.contracts import (
    Direction,
    EligibilityClassification,
    EventObservation,
    TemporalCheck,
    TemporalCheckStatus,
)
from pipelines.characterization.fixtures import SyntheticFixture, timestamp_at

SOURCE_PATHS = {
    "legacy-structure": "pipelines/legacy/03_structure.py",
    "vector-structure": "src/structure_engine.py",
    "layer2-structure": "src/layer2_structural_engine.py",
    "legacy-liquidity": "pipelines/legacy/04_liquidity.py",
    "vector-liquidity": "src/liquidity_engine.py",
    "layer3-liquidity": "src/layer3_liquidity_engine.py",
    "zone-engine": "src/zone_engine.py",
}

EXPECTED_SOURCE_SHA256 = {
    "legacy-structure": "da7fcd74639dd6f08dc7db2031bae99ff614e1304b752353894b28a8581cb435",
    "vector-structure": "9244891f9caf9100b255b1f7f410b3f3a3d5b53ce8272151c496261953709a3e",
    "layer2-structure": "74406477903916ababd4db7ce25b4e459e576e4bcce15bf52ff4a6ebb44d2310",
    "legacy-liquidity": "c42c1c76948f35b1091222e8ea3f1d46d7517a934c5dca26554c67bd3c4c5679",
    "vector-liquidity": "c42c1c76948f35b1091222e8ea3f1d46d7517a934c5dca26554c67bd3c4c5679",
    "layer3-liquidity": "f7f8b34135bcd4e6e9badd8f2c3024fbb73c08716cf6627ad0bf5600c51ce04c",
    "zone-engine": "fde09c7776f2e0b449c06f3b9191f35e5ddf7b0362ddb32ba659d55fbb9e8e37",
}


def _source_sha256(root: Path, implementation: str) -> str:
    return hashlib.sha256((root / SOURCE_PATHS[implementation]).read_bytes()).hexdigest()


def _load_repository_module(root: Path, module_name: str) -> None:
    """Load an unpackaged root module without mutating the import search path."""

    if module_name in sys.modules:
        return
    module_path = root / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load repository module {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise


def _source_module(root: Path, module_name: str):
    """Import a package module or load its exact repository source file."""

    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        top_level = module_name.split(".", maxsplit=1)[0]
        if exc.name not in {module_name, top_level}:
            raise
    module_path = root.joinpath(*module_name.split(".")).with_suffix(".py")
    audit_name = f"_kan11_{module_name.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(audit_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load source surface {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lines_containing(root: Path, implementation: str, *needles: str) -> tuple[int, ...]:
    lines = (root / SOURCE_PATHS[implementation]).read_text(encoding="utf-8").splitlines()
    return tuple(
        number
        for number, line in enumerate(lines, start=1)
        if any(needle in line for needle in needles)
    )


def _numeric_literal(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
    ):
        return -float(node.operand.value)
    return None


def _is_frame_name(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "df" or (
        isinstance(node, ast.Attribute)
        and node.attr == "df"
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _is_direct_series(node: ast.AST, series_names: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in series_names
    if isinstance(node, ast.Subscript):
        return _is_frame_name(node.value)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"astype", "copy", "dropna"}
    ):
        return _is_direct_series(node.func.value, series_names)
    return False


def scan_temporal_patterns(source: str) -> dict[str, tuple[int, ...]]:
    """Return conservative AST findings without inferring market semantics."""

    tree = ast.parse(source)
    series_names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if value is None or not _is_direct_series(value, series_names):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in series_names:
                    series_names.add(target.id)
                    changed = True

    findings: dict[str, set[int]] = {
        "NEGATIVE_SHIFT": set(),
        "CENTERED_ROLLING_WINDOW": set(),
        "BACKWARD_FILL": set(),
        "WHOLE_SERIES_REDUCTION": set(),
        "WHOLE_SERIES_EXTREMA": set(),
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attribute = node.func.attr
        if attribute == "shift":
            periods = node.args[0] if node.args else next(
                (keyword.value for keyword in node.keywords if keyword.arg == "periods"),
                None,
            )
            if periods is not None and (_numeric_literal(periods) or 0) < 0:
                findings["NEGATIVE_SHIFT"].add(node.lineno)
        if attribute == "rolling" and any(
            keyword.arg == "center"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            findings["CENTERED_ROLLING_WINDOW"].add(node.lineno)
        if attribute in {"bfill", "backfill"}:
            findings["BACKWARD_FILL"].add(node.lineno)
        if attribute == "fillna" and any(
            keyword.arg == "method"
            and isinstance(keyword.value, ast.Constant)
            and str(keyword.value.value).casefold() in {"bfill", "backfill"}
            for keyword in node.keywords
        ):
            findings["BACKWARD_FILL"].add(node.lineno)
        if attribute in {"mean", "min", "max"} and _is_direct_series(
            node.func.value, series_names
        ):
            category = (
                "WHOLE_SERIES_EXTREMA"
                if attribute in {"min", "max"}
                else "WHOLE_SERIES_REDUCTION"
            )
            findings[category].add(node.lineno)
    return {key: tuple(sorted(lines)) for key, lines in findings.items()}


def _source_patterns(root: Path, implementation: str) -> dict[str, tuple[int, ...]]:
    source = (root / SOURCE_PATHS[implementation]).read_text(encoding="utf-8")
    return scan_temporal_patterns(source)


def _number(value: object) -> float:
    return float(value)


def _event(
    *,
    implementation: str,
    event_type: str,
    direction: Direction,
    fixture: SyntheticFixture,
    origin_index: int,
    observation_index: int,
    confirmation_index: int,
    price: float,
    eligibility: EligibilityClassification,
    temporal_evidence: Iterable[str],
    parameters: Iterable[str] = (),
    raw: dict[str, str | int | float | bool | None] | None = None,
) -> EventObservation:
    eligible_timestamp = (
        None
        if eligibility is EligibilityClassification.INELIGIBLE
        else timestamp_at(fixture, confirmation_index)
    )
    return EventObservation(
        implementation_identifier=implementation,
        event_type=event_type,
        direction=direction,
        origin_or_pivot_timestamp=timestamp_at(fixture, origin_index),
        observation_timestamp=timestamp_at(fixture, observation_index),
        confirmation_or_availability_timestamp=timestamp_at(
            fixture, confirmation_index
        ),
        first_downstream_eligible_timestamp=eligible_timestamp,
        observed_price_or_level=float(price),
        eligibility_classification=eligibility,
        temporal_evidence=tuple(temporal_evidence),
        source_fixture=fixture.fixture_id,
        fixture_sha256=fixture.sha256(),
        source_parameters=tuple(parameters),
        raw_observation=raw or {},
    )


def _common_absence_checks(root: Path, implementation: str) -> list[TemporalCheck]:
    patterns = _source_patterns(root, implementation)
    checks = []
    evidence = {
        "CENTERED_ROLLING_WINDOW": "rolling call with center=True",
        "BACKWARD_FILL": "bfill/backfill operation",
        "WHOLE_SERIES_EXTREMA": "direct whole-series min/max call",
    }
    for category in (
        "CENTERED_ROLLING_WINDOW",
        "BACKWARD_FILL",
        "WHOLE_SERIES_EXTREMA",
    ):
        lines = patterns[category]
        checks.append(
            TemporalCheck(
                check=category,
                status=(
                    TemporalCheckStatus.DETECTED
                    if lines
                    else TemporalCheckStatus.NOT_DETECTED
                ),
                evidence=(
                    f"AST scan detected a {evidence[category]}."
                    if lines
                    else f"AST scan found no {evidence[category]}."
                ),
                source_lines=lines,
            )
        )
    return checks


def _event_key(event: EventObservation) -> tuple[object, ...]:
    return (
        event.source_fixture,
        event.observation_timestamp,
        event.event_type,
        event.direction.value,
        event.observed_price_or_level,
    )
