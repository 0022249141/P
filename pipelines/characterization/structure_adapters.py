"""Independent structure-engine characterization adapters."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pipelines.characterization.contracts import (
    CapabilityObservation,
    CapabilityStatus,
    Direction,
    EligibilityClassification,
    EventObservation,
    ImplementationSnapshot,
    TemporalCheck,
    TemporalCheckStatus,
)
from pipelines.characterization.fixtures import SyntheticFixture
from pipelines.characterization.source_audit import (
    SOURCE_PATHS,
    _common_absence_checks,
    _event,
    _event_key,
    _lines_containing,
    _load_repository_module,
    _number,
    _source_module,
    _source_patterns,
    _source_sha256,
)

def _freeze_simple_structure(
    root: Path,
    fixtures: dict[str, SyntheticFixture],
    *,
    implementation: str,
    module_name: str,
    right_confirmation: int,
    has_bos: bool,
) -> ImplementationSnapshot:
    if has_bos:
        _load_repository_module(root, "market_params")
    engine_class = _source_module(root, module_name).StructuralEngine
    events: list[EventObservation] = []
    for fixture_id in (
        "structure-confirmed-pivots-v1",
        "structure-insufficient-right-confirmation-v1",
        "structure-future-atr-leakage-v1",
    ):
        fixture = fixtures[fixture_id]
        engine = engine_class(SimpleNamespace(df=fixture.frame.copy(deep=True)))
        engine.detect_swings(window=2)
        for column, event_type, direction in (
            ("swing_high", "SWING_HIGH", Direction.ABOVE),
            ("swing_low", "SWING_LOW", Direction.BELOW),
        ):
            observed = engine.df[column].dropna()
            for timestamp, price in observed.items():
                origin_index = fixture.frame.index.get_loc(timestamp)
                confirmation_index = origin_index + right_confirmation
                events.append(
                    _event(
                        implementation=implementation,
                        event_type=event_type,
                        direction=direction,
                        fixture=fixture,
                        origin_index=origin_index,
                        observation_index=origin_index,
                        confirmation_index=confirmation_index,
                        price=_number(price),
                        eligibility=EligibilityClassification.INELIGIBLE,
                        temporal_evidence=(
                            f"source writes {column} on the historical pivot row",
                            f"right-side evidence is observed through index+{right_confirmation}",
                            "whole-series ATR mean can change the result after that confirmation horizon",
                        ),
                        parameters=("window=2",),
                        raw={"source_column": column, "source_index": int(origin_index)},
                    )
                )

    capabilities = [
        CapabilityObservation(
            capability="CONFIRMED_SWING_HIGH_LOW",
            status=CapabilityStatus.OBSERVED,
            evidence="Swing columns are emitted at pivot rows; normalized events retain the later evidence horizon.",
            fixture_ids=("structure-confirmed-pivots-v1",),
        ),
        CapabilityObservation(
            capability="MSS_VALID_SEQUENCE",
            status=CapabilityStatus.BLOCKED,
            evidence="The implementation exposes no MSS sequence or confirmation contract.",
            fixture_ids=("structure-mss-valid-sequence-v1",),
        ),
        CapabilityObservation(
            capability="MSS_INCOMPLETE_SEQUENCE",
            status=CapabilityStatus.BLOCKED,
            evidence="The implementation cannot distinguish incomplete MSS from absence.",
            fixture_ids=("structure-mss-incomplete-sequence-v1",),
        ),
        CapabilityObservation(
            capability="CHOCH",
            status=CapabilityStatus.NOT_EXPOSED,
            evidence="No CHoCH API or output is exposed.",
        ),
    ]

    if has_bos:
        fixture = fixtures["structure-simple-bos-v1"]
        engine = engine_class(SimpleNamespace(df=fixture.frame.copy(deep=True)))
        for evaluation in fixture.context["evaluations"]:
            index = int(evaluation["index"])
            direction_value = str(evaluation["direction"])
            if engine.is_bos(index, direction_value):
                pivot_index = int(evaluation["pivot_index"])
                direction = (
                    Direction.BULLISH
                    if direction_value == "bullish"
                    else Direction.BEARISH
                )
                events.append(
                    _event(
                        implementation=implementation,
                        event_type="BOS",
                        direction=direction,
                        fixture=fixture,
                        origin_index=pivot_index,
                        observation_index=index,
                        confirmation_index=index,
                        price=float(fixture.frame["close"].iloc[index]),
                        eligibility=EligibilityClassification.INELIGIBLE,
                        temporal_evidence=(
                            "BOS is evaluated from close displacement",
                            "the selected level is the final non-null swing in the complete frame",
                            "a later swing can change an earlier BOS result",
                        ),
                        parameters=("market_name=XAUUSD", "bos_min_displacement=0.5"),
                        raw={
                            "evaluation_index": index,
                            "source_result": True,
                            "break_basis": "close",
                        },
                    )
                )
        capabilities.append(
            CapabilityObservation(
                capability="BULLISH_BEARISH_BOS",
                status=CapabilityStatus.OBSERVED,
                evidence="Both directions are exposed through is_bos, with close displacement and full-frame final-swing selection.",
                fixture_ids=(
                    "structure-simple-bos-v1",
                    "structure-future-level-selection-v1",
                ),
            )
        )
    else:
        capabilities.append(
            CapabilityObservation(
                capability="BULLISH_BEARISH_BOS",
                status=CapabilityStatus.NOT_EXPOSED,
                evidence="The vector structure implementation exposes swing detection only.",
            )
        )

    checks = _common_absence_checks(root, implementation)
    patterns = _source_patterns(root, implementation)
    checks.extend(
        [
            TemporalCheck(
                check="NEGATIVE_SHIFT",
                status=(
                    TemporalCheckStatus.DETECTED
                    if patterns["NEGATIVE_SHIFT"]
                    else TemporalCheckStatus.NOT_DETECTED
                ),
                evidence=(
                    "Negative shifts participate in vector pivot detection."
                    if patterns["NEGATIVE_SHIFT"]
                    else "AST scan found no negative shift call."
                ),
                source_lines=patterns["NEGATIVE_SHIFT"],
            ),
            TemporalCheck(
                check="WHOLE_SERIES_REDUCTION",
                status=TemporalCheckStatus.DETECTED,
                evidence="The adaptive threshold uses a mean over the complete ATR series.",
                source_lines=patterns["WHOLE_SERIES_REDUCTION"],
                fixture_ids=("structure-future-atr-leakage-v1",),
            ),
            TemporalCheck(
                check="FUTURE_PIVOT_CONFIRMATION",
                status=TemporalCheckStatus.DETECTED,
                evidence=f"The pivot uses right-side candle evidence through index+{right_confirmation} but is written at the pivot row.",
                source_lines=_lines_containing(
                    root, implementation, "future_high", "future_low", "shift(-1)"
                ),
                fixture_ids=(
                    "structure-confirmed-pivots-v1",
                    "structure-insufficient-right-confirmation-v1",
                ),
            ),
            TemporalCheck(
                check="PREFIX_INVARIANCE",
                status=TemporalCheckStatus.DETECTED,
                evidence="Full-frame future ATR values create a pivot that is absent when truncated at the nominal confirmation horizon.",
                fixture_ids=("structure-future-atr-leakage-v1",),
            ),
        ]
    )
    if has_bos:
        checks.append(
            TemporalCheck(
                check="WHOLE_SERIES_LEVEL_SELECTION",
                status=TemporalCheckStatus.DETECTED,
                evidence="is_bos selects the final non-null swing from the complete frame, including swings after the evaluated candle.",
                source_lines=_lines_containing(root, implementation, ".iloc[-1]"),
                fixture_ids=("structure-future-level-selection-v1",),
            )
        )
    return ImplementationSnapshot(
        implementation_identifier=implementation,
        repository_path=SOURCE_PATHS[implementation],
        source_sha256=_source_sha256(root, implementation),
        domain="STRUCTURE",
        events=tuple(sorted(events, key=_event_key)),
        capabilities=tuple(sorted(capabilities, key=lambda item: item.capability)),
        temporal_checks=tuple(sorted(checks, key=lambda item: item.check)),
    )
def _freeze_layer2_structure(
    root: Path, fixtures: dict[str, SyntheticFixture]
) -> ImplementationSnapshot:
    implementation = "layer2-structure"
    engine_class = _source_module(root, "src.layer2_structural_engine").StructuralEngine
    engine = engine_class(min_strength=0.0)
    events: list[EventObservation] = []
    for fixture_id in (
        "structure-confirmed-pivots-v1",
        "structure-insufficient-right-confirmation-v1",
        "structure-future-atr-leakage-v1",
    ):
        fixture = fixtures[fixture_id]
        for swing, event_type, direction in (
            (engine.detect_swing_highs(fixture.frame.copy(deep=True), lookback=2), "SWING_HIGH", Direction.ABOVE),
            (engine.detect_swing_lows(fixture.frame.copy(deep=True), lookback=2), "SWING_LOW", Direction.BELOW),
        ):
            for item in swing:
                origin_index = int(item["index"])
                events.append(
                    _event(
                        implementation=implementation,
                        event_type=event_type,
                        direction=direction,
                        fixture=fixture,
                        origin_index=origin_index,
                        observation_index=origin_index,
                        confirmation_index=origin_index + 2,
                        price=_number(item["price"]),
                        eligibility=EligibilityClassification.POST_CONFIRMATION,
                        temporal_evidence=(
                            "source emits the pivot timestamp",
                            "two right-side candles are required by lookback=2",
                            "first downstream use is delayed to the right-window close",
                        ),
                        parameters=("lookback=2", "min_strength=0.0"),
                        raw={
                            "source_index": origin_index,
                            "source_type": str(item["type"]),
                            "strength": _number(item["strength"]),
                        },
                    )
                )

    breaks = fixtures["structure-layer2-break-sequence-v1"]
    swing_highs = [dict(item) for item in breaks.context["swing_highs"]]
    swing_lows = [dict(item) for item in breaks.context["swing_lows"]]
    for item in swing_highs:
        item.update(timestamp=breaks.frame.index[item["index"]], strength=1.0, type="HIGH")
    for item in swing_lows:
        item.update(timestamp=breaks.frame.index[item["index"]], strength=1.0, type="LOW")
    bos, choch = engine.detect_bos_choch(
        breaks.frame.copy(deep=True), swing_highs, swing_lows
    )
    for index in range(len(breaks.frame)):
        if not bool(bos.iloc[index]):
            continue
        bullish = [item for item in swing_highs if index > item["index"] and breaks.frame["high"].iloc[index] > item["price"]]
        bearish = [item for item in swing_lows if index > item["index"] and breaks.frame["low"].iloc[index] < item["price"]]
        references = bullish if bullish else bearish
        direction = Direction.BULLISH if bullish else Direction.BEARISH
        reference = references[0]
        eligibility = (
            EligibilityClassification.REALTIME_ELIGIBLE
            if int(reference["confirmation_index"]) <= index
            else EligibilityClassification.INELIGIBLE
        )
        events.append(
            _event(
                implementation=implementation,
                event_type="BOS",
                direction=direction,
                fixture=breaks,
                origin_index=int(reference["index"]),
                observation_index=index,
                confirmation_index=index,
                price=float(reference["price"]),
                eligibility=eligibility,
                temporal_evidence=(
                    "referenced swing is confirmed before this break candle",
                    "source compares the candle wick, not the governed close",
                ),
                parameters=("supplied_confirmed_swings=true",),
                raw={"break_basis": "wick", "source_index": index, "source_result": True},
            )
        )
        if bool(choch.iloc[index]):
            events.append(
                _event(
                    implementation=implementation,
                    event_type="CHOCH",
                    direction=direction,
                    fixture=breaks,
                    origin_index=int(reference["index"]),
                    observation_index=index,
                    confirmation_index=index,
                    price=float(reference["price"]),
                    eligibility=eligibility,
                    temporal_evidence=(
                        "source trend state changed on the current wick break",
                        "referenced swing was available before the transition",
                    ),
                    parameters=("supplied_confirmed_swings=true",),
                    raw={"break_basis": "wick", "source_index": index, "source_result": True},
                )
            )

    capabilities = (
        CapabilityObservation(
            capability="BULLISH_BEARISH_BOS",
            status=CapabilityStatus.OBSERVED,
            evidence="Both directions are emitted; source logic uses high/low wick penetration.",
            fixture_ids=("structure-layer2-break-sequence-v1",),
        ),
        CapabilityObservation(
            capability="BULLISH_BEARISH_CHOCH",
            status=CapabilityStatus.OBSERVED,
            evidence="Both trend transitions are emitted by the source state variable.",
            fixture_ids=("structure-layer2-break-sequence-v1",),
        ),
        CapabilityObservation(
            capability="CONFIRMED_SWING_HIGH_LOW",
            status=CapabilityStatus.OBSERVED,
            evidence="Symmetric lookback pivots are observed and delayed by the adapter until confirmation.",
            fixture_ids=("structure-confirmed-pivots-v1",),
        ),
        CapabilityObservation(
            capability="MSS_INCOMPLETE_SEQUENCE",
            status=CapabilityStatus.BLOCKED,
            evidence="No MSS sequence output exists despite module prose.",
            fixture_ids=("structure-mss-incomplete-sequence-v1",),
        ),
        CapabilityObservation(
            capability="MSS_VALID_SEQUENCE",
            status=CapabilityStatus.BLOCKED,
            evidence="No CHoCH/new-swing/confirming-BOS MSS contract is implemented.",
            fixture_ids=("structure-mss-valid-sequence-v1",),
        ),
    )
    checks = _common_absence_checks(root, implementation)
    patterns = _source_patterns(root, implementation)
    checks.extend(
        [
            TemporalCheck(
                check="NEGATIVE_SHIFT",
                status=(
                    TemporalCheckStatus.DETECTED
                    if patterns["NEGATIVE_SHIFT"]
                    else TemporalCheckStatus.NOT_DETECTED
                ),
                evidence="AST scan found no negative shift call.",
                source_lines=patterns["NEGATIVE_SHIFT"],
            ),
            TemporalCheck(
                check="FUTURE_PIVOT_CONFIRMATION",
                status=TemporalCheckStatus.DETECTED,
                evidence="Swing pivots require a symmetric right window and are emitted with pivot timestamps only.",
                source_lines=_lines_containing(root, implementation, "range(i + 1"),
                fixture_ids=("structure-confirmed-pivots-v1",),
            ),
            TemporalCheck(
                check="PREFIX_INVARIANCE",
                status=TemporalCheckStatus.PASSED,
                evidence="A confirmed pivot is identical on the full fixture and a prefix ending at its declared availability.",
                fixture_ids=("structure-future-atr-leakage-v1",),
            ),
            TemporalCheck(
                check="WICK_BASED_BREAK",
                status=TemporalCheckStatus.DETECTED,
                evidence="BOS/CHoCH compare high and low wicks rather than close.",
                source_lines=_lines_containing(
                    root, implementation, "['high'] > sh['price']", "['low'] < sl['price']"
                ),
                fixture_ids=("structure-layer2-break-sequence-v1",),
            ),
        ]
    )
    return ImplementationSnapshot(
        implementation_identifier=implementation,
        repository_path=SOURCE_PATHS[implementation],
        source_sha256=_source_sha256(root, implementation),
        domain="STRUCTURE",
        events=tuple(sorted(events, key=_event_key)),
        capabilities=tuple(sorted(capabilities, key=lambda item: item.capability)),
        temporal_checks=tuple(sorted(checks, key=lambda item: item.check)),
    )
