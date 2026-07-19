"""Research-only confirmed-swing adapter for the characterized layer-2 engine."""

from __future__ import annotations

import hashlib
import importlib.util
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from pipelines.historical_labeling.contracts import (
    EventDirection,
    EventType,
    MarketEventIdentity,
)
from pipelines.historical_labeling.policies import EventSourcePolicy


REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


class EventSourceEligibilityError(ValueError):
    pass


def require_kan11_eligible(observation: Any) -> None:
    classification = getattr(observation, "eligibility_classification", None)
    value = getattr(classification, "value", classification)
    if value == "INELIGIBLE":
        raise EventSourceEligibilityError(
            "KAN-11 INELIGIBLE observations cannot become historical market events"
        )
    if value not in {"REALTIME_ELIGIBLE", "POST_CONFIRMATION"}:
        raise EventSourceEligibilityError("KAN-11 eligibility evidence is unavailable")


def _approved_source(root: Path, policy: EventSourcePolicy) -> Path:
    resolved_root = root.resolve()
    package_root = Path(__file__).resolve().parents[2]
    if resolved_root != package_root:
        raise EventSourceEligibilityError(
            "repository_root must match the checkout that loaded KAN-13"
        )
    source = (resolved_root / policy.repository_path).resolve()
    expected = resolved_root.joinpath(*policy.repository_path.split("/")).resolve()
    if source != expected or not source.is_file():
        raise EventSourceEligibilityError("approved layer-2 source path is unavailable")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != policy.source_sha256:
        raise EventSourceEligibilityError(
            "layer-2 source hash differs from the approved characterization evidence"
        )
    return source


def _load_approved_engine(root: Path, policy: EventSourcePolicy) -> type[Any]:
    source = _approved_source(root, policy)
    spec = importlib.util.spec_from_file_location(
        "_kan13_hash_pinned_layer2_structural_engine",
        source,
    )
    if spec is None or spec.loader is None:
        raise EventSourceEligibilityError("approved layer-2 source cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loaded_path = Path(str(module.__file__)).resolve()
    if loaded_path != source:
        raise EventSourceEligibilityError(
            "loaded layer-2 module does not match the approved source path"
        )
    engine = getattr(module, "StructuralEngine", None)
    if engine is None:
        raise EventSourceEligibilityError("approved layer-2 engine class is unavailable")
    return engine


def _prepared_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise EventSourceEligibilityError(f"event source is missing columns: {missing}")
    prepared = frame.loc[:, REQUIRED_COLUMNS].copy(deep=True)
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], utc=True)
    if prepared["timestamp"].isna().any():
        raise EventSourceEligibilityError("event timestamps must be parseable UTC instants")
    if prepared["timestamp"].duplicated().any():
        raise EventSourceEligibilityError("event timestamps must be unique")
    if not prepared["timestamp"].is_monotonic_increasing:
        raise EventSourceEligibilityError("event timestamps must be increasing")
    return prepared.set_index("timestamp")


def generate_confirmed_swing_events(
    frame: pd.DataFrame,
    *,
    repository_root: Path,
    policy: EventSourcePolicy,
    market: str,
    symbol: str,
    timeframe: str,
    source_timeframe: str,
    source_dataset_id: str,
    source_sha256: str,
) -> tuple[MarketEventIdentity, ...]:
    """Map unchanged layer-2 pivots to explicitly delayed event identities."""

    prepared = _prepared_frame(frame)
    engine_type = _load_approved_engine(repository_root, policy)
    engine = engine_type(min_strength=float(policy.min_strength))
    parameters = policy.parameter_strings()
    parameter_hash = policy.parameter_sha256()
    events: list[MarketEventIdentity] = []

    observations = (
        (
            engine.detect_swing_highs(prepared.copy(deep=True), lookback=policy.lookback),
            EventType.SWING_HIGH,
            EventDirection.ABOVE,
        ),
        (
            engine.detect_swing_lows(prepared.copy(deep=True), lookback=policy.lookback),
            EventType.SWING_LOW,
            EventDirection.BELOW,
        ),
    )
    for swings, event_type, direction in observations:
        for swing in swings:
            origin_index = int(swing["index"])
            confirmation_index = origin_index + policy.lookback
            if confirmation_index >= len(prepared):
                continue
            origin = prepared.index[origin_index].to_pydatetime()
            confirmation = (
                prepared.index[confirmation_index]
                + pd.Timedelta(seconds=policy.event_bar_seconds)
            ).to_pydatetime()
            events.append(
                MarketEventIdentity.create(
                    schema_version="1.0.0",
                    event_policy_version=policy.policy_version,
                    market=market,
                    symbol=symbol,
                    timeframe=timeframe,
                    source_timeframe=source_timeframe,
                    source_dataset_id=source_dataset_id,
                    source_sha256=source_sha256,
                    implementation_identifier=policy.implementation_identifier,
                    source_parameters=parameters,
                    source_parameter_sha256=parameter_hash,
                    event_type=event_type,
                    direction=direction,
                    level_type=event_type.value,
                    level_price=Decimal(str(swing["price"])),
                    level_origin_timestamp=origin,
                    observation_timestamp=origin,
                    confirmation_or_availability_timestamp=confirmation,
                    first_feature_eligible_timestamp=confirmation,
                )
            )
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event.first_feature_eligible_timestamp,
                event.level_origin_timestamp,
                event.event_type.value,
                event.event_id,
            ),
        )
    )


__all__ = [
    "EventSourceEligibilityError",
    "generate_confirmed_swing_events",
    "require_kan11_eligible",
]
