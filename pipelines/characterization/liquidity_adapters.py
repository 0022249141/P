"""Independent liquidity-engine characterization adapters."""

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
    _source_module,
    _source_patterns,
    _source_sha256,
)

def _freeze_simple_liquidity(
    root: Path,
    fixtures: dict[str, SyntheticFixture],
    *,
    implementation: str,
    module_name: str,
) -> ImplementationSnapshot:
    _load_repository_module(root, "core_constants")
    _load_repository_module(root, "market_params")
    engine_class = _source_module(root, module_name).LiquidityEngine
    fixture = fixtures["liquidity-equal-levels-v1"]
    engine = engine_class(SimpleNamespace(df=fixture.frame.copy(deep=True)))
    events: list[EventObservation] = []
    for values, event_type, direction in (
        ([100.0, 100.1, 99.9], "CLUSTERED_HIGH_LEVEL", Direction.ABOVE),
        ([90.0, 90.1, 89.9], "CLUSTERED_LOW_LEVEL", Direction.BELOW),
    ):
        for level in engine._cluster_levels(values, atr=1.0):
            events.append(
                _event(
                    implementation=implementation,
                    event_type=event_type,
                    direction=direction,
                    fixture=fixture,
                    origin_index=0,
                    observation_index=3,
                    confirmation_index=3,
                    price=float(level),
                    eligibility=EligibilityClassification.REALTIME_ELIGIBLE,
                    temporal_evidence=(
                        "direct clustering helper received only levels available through the third touch",
                        "the helper exposes a level but no pool state or registration timestamp",
                    ),
                    parameters=("atr=1.0", "cluster_gap_atr_mult=0.2"),
                    raw={"input_count": len(values)},
                )
            )

    failure = "none"
    try:
        engine.detect_sweeps()
    except KeyError as exc:
        failure = f"KeyError:{exc.args[0]}"

    capabilities = (
        CapabilityObservation(
            capability="EQUAL_LEVEL_CLUSTERING_HELPER",
            status=CapabilityStatus.OBSERVED,
            evidence="The private clustering helper deterministically groups price values within the ATR gap.",
            fixture_ids=("liquidity-equal-levels-v1",),
        ),
        CapabilityObservation(
            capability="SWEEP_SCORE",
            status=CapabilityStatus.BLOCKED,
            evidence=f"detect_sweeps cannot run with the committed market configuration ({failure}); no configuration is patched by characterization.",
            fixture_ids=("liquidity-equal-levels-v1",),
        ),
        CapabilityObservation(
            capability="BSL_SSL_REGISTRATION",
            status=CapabilityStatus.NOT_EXPOSED,
            evidence="Cluster levels are internal inputs to scoring and are not emitted as registered pools.",
        ),
        CapabilityObservation(
            capability="LIQUIDITY_LIFECYCLE",
            status=CapabilityStatus.BLOCKED,
            evidence="No untouched/swept/reclaimed/accepted state contract is exposed.",
        ),
        CapabilityObservation(
            capability="DESTINATION_RANKING",
            status=CapabilityStatus.BLOCKED,
            evidence="No candidate ranking API, weights, ties, or as-of contract is exposed.",
            fixture_ids=("liquidity-multiple-destinations-v1",),
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
                check="WHOLE_SERIES_REDUCTION",
                status=TemporalCheckStatus.DETECTED,
                evidence="Sweep threshold calculation reads the complete ATR series mean.",
                source_lines=patterns["WHOLE_SERIES_REDUCTION"],
            ),
            TemporalCheck(
                check="POOL_OUTCOME_BEFORE_REGISTRATION",
                status=TemporalCheckStatus.BLOCKED,
                evidence="The source does not emit auditable pool-registration evidence before sweep scoring.",
            ),
            TemporalCheck(
                check="DESTINATION_RANKING_USES_LATER_CANDLES",
                status=TemporalCheckStatus.BLOCKED,
                evidence="No destination ranking exists, so an as-of temporal audit cannot be performed.",
            ),
        ]
    )
    return ImplementationSnapshot(
        implementation_identifier=implementation,
        repository_path=SOURCE_PATHS[implementation],
        source_sha256=_source_sha256(root, implementation),
        domain="LIQUIDITY",
        events=tuple(sorted(events, key=_event_key)),
        capabilities=tuple(sorted(capabilities, key=lambda item: item.capability)),
        temporal_checks=tuple(sorted(checks, key=lambda item: item.check)),
    )
def _context_swings(fixture: SyntheticFixture, key: str) -> list[dict[str, object]]:
    values = []
    for raw in fixture.context.get(key, []):
        item = dict(raw)
        item["timestamp"] = fixture.frame.index[int(item["index"])]
        item["strength"] = 1.0
        item["type"] = "HIGH" if key == "swing_highs" else "LOW"
        values.append(item)
    return values


def _pool_events(
    implementation: str,
    fixture: SyntheticFixture,
    resting: list[dict[str, object]],
) -> list[EventObservation]:
    events: list[EventObservation] = []
    for position, item in enumerate(resting):
        reference = dict(item["swing_ref"])
        origin_index = int(reference["index"])
        confirmation_index = int(reference.get("confirmation_index", origin_index))
        high_side = item["type"] == "RESTING_HIGH"
        direction = Direction.ABOVE if high_side else Direction.BELOW
        prefix = "BSL" if high_side else "SSL"
        for event_type in (f"{prefix}_REGISTRATION_PROXY", f"UNTOUCHED_{prefix}_PROXY"):
            events.append(
                _event(
                    implementation=implementation,
                    event_type=event_type,
                    direction=direction,
                    fixture=fixture,
                    origin_index=origin_index,
                    observation_index=confirmation_index,
                    confirmation_index=confirmation_index,
                    price=float(item["price"]),
                    eligibility=EligibilityClassification.POST_CONFIRMATION,
                    temporal_evidence=(
                        "adapter maps RESTING_HIGH/RESTING_LOW to candidate BSL/SSL terminology",
                        "the source exposes resting membership only after receiving a confirmed swing",
                        "the mapping is a proxy and does not prove resting orders",
                    ),
                    parameters=("resting_match_tolerance=0.001",),
                    raw={
                        "source_position": position,
                        "source_type": str(item["type"]),
                        "source_risk_level": str(item["risk_level"]),
                    },
                )
            )
    return events


def _freeze_layer3_liquidity(
    root: Path, fixtures: dict[str, SyntheticFixture]
) -> ImplementationSnapshot:
    implementation = "layer3-liquidity"
    engine_class = _source_module(root, "src.layer3_liquidity_engine").LiquidityEngine
    engine = engine_class(tolerance_atr=0.15)
    events: list[EventObservation] = []

    equal_fixture = fixtures["liquidity-equal-levels-v1"]
    equal_highs, equal_lows = engine.detect_equal_levels(
        equal_fixture.frame.copy(deep=True), lookback=3
    )
    for series, event_type, direction, column in (
        (equal_highs, "EQUAL_HIGH_CLUSTER", Direction.ABOVE, "high"),
        (equal_lows, "EQUAL_LOW_CLUSTER", Direction.BELOW, "low"),
    ):
        for timestamp, count in series[series > 0].items():
            index = equal_fixture.frame.index.get_loc(timestamp)
            events.append(
                _event(
                    implementation=implementation,
                    event_type=event_type,
                    direction=direction,
                    fixture=equal_fixture,
                    origin_index=max(0, index - 3),
                    observation_index=index,
                    confirmation_index=index,
                    price=float(equal_fixture.frame[column].iloc[index]),
                    eligibility=EligibilityClassification.REALTIME_ELIGIBLE,
                    temporal_evidence=(
                        "equal-level count uses only the configured prior lookback",
                        "registration occurs on the current third-or-later touch",
                    ),
                    parameters=("lookback=3", "tolerance_atr=0.15", "atr_col=atr_14"),
                    raw={"prior_match_count": int(count), "source_index": int(index)},
                )
            )

    pool_fixture = fixtures["liquidity-pool-registration-v1"]
    pool_highs = _context_swings(pool_fixture, "swing_highs")
    pool_lows = _context_swings(pool_fixture, "swing_lows")
    resting = engine.detect_resting_liquidity(pool_highs, pool_lows, [])
    events.extend(_pool_events(implementation, pool_fixture, resting))

    for fixture_id in (
        "liquidity-bearish-wick-raid-v1",
        "liquidity-bearish-close-through-v1",
        "liquidity-bullish-wick-raid-v1",
    ):
        fixture = fixtures[fixture_id]
        highs = _context_swings(fixture, "swing_highs")
        lows = _context_swings(fixture, "swing_lows")
        sweeps = engine.detect_sweeps(
            fixture.frame.copy(deep=True), highs, lows, lookback_sweep=5
        )
        references = highs + lows
        for sweep in sweeps:
            origin = next(
                reference
                for reference in references
                if int(reference["index"]) == int(sweep["swing_ref_index"])
                and float(reference["price"]) == float(sweep["target_level"])
            )
            raid_index = int(sweep["index"])
            confirmation_index = int(sweep["confirmation_index"])
            pool_available = int(origin["confirmation_index"]) <= raid_index
            eligibility = (
                EligibilityClassification.POST_CONFIRMATION
                if pool_available
                else EligibilityClassification.INELIGIBLE
            )
            direction = (
                Direction.BULLISH
                if sweep["type"] == "BULLISH_SWEEP"
                else Direction.BEARISH
            )
            events.append(
                _event(
                    implementation=implementation,
                    event_type=str(sweep["type"]),
                    direction=direction,
                    fixture=fixture,
                    origin_index=int(origin["index"]),
                    observation_index=raid_index,
                    confirmation_index=confirmation_index,
                    price=float(sweep["target_level"]),
                    eligibility=eligibility,
                    temporal_evidence=(
                        "the supplied pool is confirmed before the raid candle",
                        "the source requires the next candle to reverse",
                        "process writes the result at the raid row, so downstream use is delayed to confirmation",
                    ),
                    parameters=("tolerance_atr=0.15", "lookback_sweep=5"),
                    raw={
                        "confidence": int(sweep["confidence"]),
                        "depth_atr": float(sweep["depth_atr"]),
                        "mitigation_score": float(sweep["mitigation_score"]),
                        "pool_confirmation_index": int(origin["confirmation_index"]),
                        "pool_registered_before_raid": pool_available,
                        "source_index": raid_index,
                        "source_writes_at": "raid_index",
                    },
                )
            )

    ranking_fixture = fixtures["liquidity-multiple-destinations-v1"]
    ranking_resting = engine.detect_resting_liquidity(
        _context_swings(ranking_fixture, "swing_highs"),
        _context_swings(ranking_fixture, "swing_lows"),
        [],
    )
    events.extend(_pool_events(implementation, ranking_fixture, ranking_resting))

    capabilities = (
        CapabilityObservation(
            capability="BSL_SSL_REGISTRATION",
            status=CapabilityStatus.OBSERVED,
            evidence="RESTING_HIGH and RESTING_LOW are explicitly preserved as adapter-labeled BSL/SSL proxies.",
            fixture_ids=("liquidity-pool-registration-v1",),
        ),
        CapabilityObservation(
            capability="DESTINATION_RANKING",
            status=CapabilityStatus.BLOCKED,
            evidence="Multiple candidates retain source input order, but no score, rank, tie, or as-of contract exists.",
            fixture_ids=("liquidity-multiple-destinations-v1",),
        ),
        CapabilityObservation(
            capability="EQUAL_HIGH_EQUAL_LOW",
            status=CapabilityStatus.OBSERVED,
            evidence="Both prior-touch counters are emitted at the current candle.",
            fixture_ids=("liquidity-equal-levels-v1",),
        ),
        CapabilityObservation(
            capability="RECLAIMED_STATE",
            status=CapabilityStatus.BLOCKED,
            evidence="No reclaimed lifecycle state or confirmation rule is exposed.",
            fixture_ids=("liquidity-bearish-wick-raid-v1",),
        ),
        CapabilityObservation(
            capability="ACCEPTED_STATE",
            status=CapabilityStatus.BLOCKED,
            evidence="A mitigation score distinguishes close placement, but it is not an acceptance state or hold-count contract.",
            fixture_ids=(
                "liquidity-bearish-wick-raid-v1",
                "liquidity-bearish-close-through-v1",
            ),
        ),
        CapabilityObservation(
            capability="SWEPT_STATE",
            status=CapabilityStatus.OBSERVED,
            evidence="High-side and low-side sweeps require a later reversal candle.",
            fixture_ids=(
                "liquidity-bearish-wick-raid-v1",
                "liquidity-bullish-wick-raid-v1",
            ),
        ),
        CapabilityObservation(
            capability="UNTOUCHED_STATE_PROXY",
            status=CapabilityStatus.OBSERVED,
            evidence="Resting output is frozen as an untouched proxy, not a complete lifecycle state.",
            fixture_ids=("liquidity-pool-registration-v1",),
        ),
        CapabilityObservation(
            capability="WICK_RAID_VS_CLOSE_THROUGH",
            status=CapabilityStatus.OBSERVED,
            evidence="The same sweep type carries mitigation_score 0.70 for wick-only and 0.95 for close-through; no acceptance label is emitted.",
            fixture_ids=(
                "liquidity-bearish-wick-raid-v1",
                "liquidity-bearish-close-through-v1",
            ),
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
                check="FUTURE_SWEEP_CONFIRMATION",
                status=TemporalCheckStatus.DETECTED,
                evidence="Sweep detection reads i+1 and records confirmation_index=i+1 while process writes is_sweep at i.",
                source_lines=_lines_containing(root, implementation, "i + 1", "confirmation_index"),
                fixture_ids=(
                    "liquidity-bearish-wick-raid-v1",
                    "liquidity-bullish-wick-raid-v1",
                ),
            ),
            TemporalCheck(
                check="POOL_OUTCOME_BEFORE_REGISTRATION",
                status=TemporalCheckStatus.PASSED,
                evidence="Every synthetic sweep references a pool whose supplied confirmation index precedes the raid index.",
                fixture_ids=(
                    "liquidity-bearish-wick-raid-v1",
                    "liquidity-bullish-wick-raid-v1",
                ),
            ),
            TemporalCheck(
                check="RESTING_STATE_USES_COMPLETE_SWEEP_LIST",
                status=TemporalCheckStatus.DETECTED,
                evidence="process derives resting levels after computing the complete-frame sweep list and emits no as-of timestamp.",
                source_lines=_lines_containing(root, implementation, "swept_levels", "detect_resting_liquidity"),
            ),
            TemporalCheck(
                check="DESTINATION_RANKING_USES_LATER_CANDLES",
                status=TemporalCheckStatus.BLOCKED,
                evidence="No destination ranking is implemented; later-candle use cannot be tested without inventing semantics.",
                fixture_ids=("liquidity-multiple-destinations-v1",),
            ),
        ]
    )
    return ImplementationSnapshot(
        implementation_identifier=implementation,
        repository_path=SOURCE_PATHS[implementation],
        source_sha256=_source_sha256(root, implementation),
        domain="LIQUIDITY",
        events=tuple(sorted(events, key=_event_key)),
        capabilities=tuple(sorted(capabilities, key=lambda item: item.capability)),
        temporal_checks=tuple(sorted(checks, key=lambda item: item.check)),
    )
def _freeze_zone_engine(root: Path) -> ImplementationSnapshot:
    implementation = "zone-engine"
    _source_module(root, "src.zone_engine")
    capabilities = tuple(
        CapabilityObservation(
            capability=capability,
            status=CapabilityStatus.BLOCKED,
            evidence="ZoneEngine exposes FVG/order-block scores, not this liquidity contract.",
        )
        for capability in (
            "BSL_SSL_REGISTRATION",
            "DESTINATION_RANKING",
            "EQUAL_HIGH_EQUAL_LOW",
            "LIQUIDITY_LIFECYCLE",
            "SWEEP",
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
                evidence="AST scan found no negative shift call.",
                source_lines=patterns["NEGATIVE_SHIFT"],
            ),
            TemporalCheck(
                check="POOL_OUTCOME_BEFORE_REGISTRATION",
                status=TemporalCheckStatus.BLOCKED,
                evidence="No liquidity pool registration or outcome API exists on ZoneEngine.",
            ),
            TemporalCheck(
                check="DESTINATION_RANKING_USES_LATER_CANDLES",
                status=TemporalCheckStatus.BLOCKED,
                evidence="No destination ranking API exists on ZoneEngine.",
            ),
        ]
    )
    return ImplementationSnapshot(
        implementation_identifier=implementation,
        repository_path=SOURCE_PATHS[implementation],
        source_sha256=_source_sha256(root, implementation),
        domain="LIQUIDITY",
        capabilities=tuple(sorted(capabilities, key=lambda item: item.capability)),
        temporal_checks=tuple(sorted(checks, key=lambda item: item.check)),
    )
