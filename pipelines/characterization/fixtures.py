"""Small deterministic synthetic fixtures used by the KAN-11 audit."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from pipelines.characterization.contracts import FixtureEvidence


@dataclass(frozen=True)
class SyntheticFixture:
    fixture_id: str
    frame: pd.DataFrame
    purpose: str
    context: dict[str, Any] = field(default_factory=dict)

    def sha256(self) -> str:
        records: list[dict[str, Any]] = []
        for timestamp, row in self.frame.iterrows():
            record: dict[str, Any] = {"timestamp": _timestamp(timestamp)}
            for column in sorted(self.frame.columns):
                value = row[column]
                if pd.isna(value):
                    record[column] = None
                elif isinstance(value, bool):
                    record[column] = value
                elif isinstance(value, (int, float)):
                    record[column] = float(value)
                else:
                    record[column] = str(value)
            records.append(record)
        payload = {
            "context": _json_value(self.context),
            "fixture_id": self.fixture_id,
            "records": records,
        }
        encoded = json.dumps(
            payload, allow_nan=False, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()

    def evidence(self) -> FixtureEvidence:
        return FixtureEvidence(
            fixture_id=self.fixture_id,
            fixture_sha256=self.sha256(),
            row_count=len(self.frame),
            first_timestamp=_timestamp(self.frame.index[0]),
            last_timestamp=_timestamp(self.frame.index[-1]),
            purpose=self.purpose,
        )


def _timestamp(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError("synthetic fixture timestamps must be timezone-aware")
    return timestamp.tz_convert("UTC").isoformat().replace("+00:00", "Z")


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return _timestamp(value)
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _frame(
    day: str,
    high: list[float],
    low: list[float],
    close: list[float],
    *,
    open_: list[float] | None = None,
    atr: list[float] | None = None,
    volume: list[float] | None = None,
) -> pd.DataFrame:
    count = len(high)
    if len(low) != count or len(close) != count:
        raise ValueError("OHLC fixture vectors must have equal lengths")
    opens = open_ if open_ is not None else [(low[i] + close[i]) / 2 for i in range(count)]
    atr_values = atr if atr is not None else [2.0] * count
    volumes = volume if volume is not None else [100.0] * count
    index = pd.date_range(day, periods=count, freq="5min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": opens,
            "high": high,
            "low": low,
            "close": close,
            "volume": volumes,
            "ATR14": atr_values,
            "avg_volume_20": [100.0] * count,
            "atr_14": atr_values,
        },
        index=index,
    )
    frame["body"] = (frame["close"] - frame["open"]).abs()
    frame["range"] = frame["high"] - frame["low"]
    return frame


def fixture_catalog() -> dict[str, SyntheticFixture]:
    confirmed = SyntheticFixture(
        fixture_id="structure-confirmed-pivots-v1",
        frame=_frame(
            "2025-01-01",
            [10, 11, 12, 16, 13, 12, 11, 12, 13],
            [8, 9, 10, 11, 10, 7, 9, 10, 11],
            [9.5, 10.5, 11.5, 12.5, 11, 9, 10.5, 11.5, 12.5],
            open_=[9, 10, 11, 12, 12, 10, 10, 11, 12],
        ),
        purpose="Confirmed high/low pivots and duplicate-engine divergence.",
        context={"window": 2, "layer2_min_strength": 0.0},
    )
    insufficient = SyntheticFixture(
        fixture_id="structure-insufficient-right-confirmation-v1",
        frame=_frame(
            "2025-01-02",
            [10, 11, 12, 13, 16, 12],
            [8, 8.5, 9, 9.5, 11, 10],
            [9.5, 10, 11, 12, 13, 11],
            open_=[9, 9.5, 10, 10.5, 12, 11],
        ),
        purpose="Candidate pivot with only one right-side candle.",
        context={"candidate_index": 4, "window": 2},
    )
    atr_leakage = SyntheticFixture(
        fixture_id="structure-future-atr-leakage-v1",
        frame=_frame(
            "2025-01-03",
            [9, 9.5, 10, 11, 10.5, 10.2, 10, 9.8, 9.7, 9.6],
            [8.5, 9, 9.2, 9.5, 9.4, 9.3, 9.2, 9.1, 9, 8.9],
            [8.9, 9.3, 9.7, 10.5, 9.9, 9.7, 9.6, 9.4, 9.3, 9.2],
            open_=[8.8, 9.2, 9.5, 10, 10, 9.8, 9.7, 9.5, 9.4, 9.3],
            atr=[2, 2, 2, 2, 2, 2, 20, 20, 20, 20],
        ),
        purpose="Whole-series ATR mean changes a previously confirmable pivot.",
        context={"candidate_index": 3, "prefix_end_index": 5, "window": 2},
    )
    simple_bos = _frame(
        "2025-01-04",
        [101, 101, 102, 161, 42],
        [99, 99, 98, 159, 39],
        [100, 100, 100, 160, 40],
    )
    simple_bos["swing_high"] = [100.0, float("nan"), float("nan"), float("nan"), float("nan")]
    simple_bos["swing_low"] = [float("nan"), 100.0, float("nan"), float("nan"), float("nan")]
    bos_fixture = SyntheticFixture(
        fixture_id="structure-simple-bos-v1",
        frame=simple_bos,
        purpose="Bullish and bearish simple-engine BOS at its configured displacement.",
        context={
            "evaluations": [
                {"direction": "bullish", "index": 3, "pivot_index": 0},
                {"direction": "bearish", "index": 4, "pivot_index": 1},
            ]
        },
    )
    future_level = _frame(
        "2025-01-05",
        [101, 101, 102, 161, 162, 201],
        [99, 99, 98, 159, 158, 199],
        [100, 100, 100, 160, 160, 200],
    )
    future_level["swing_high"] = [100.0, float("nan"), float("nan"), float("nan"), float("nan"), 200.0]
    future_level["swing_low"] = float("nan")
    future_level_fixture = SyntheticFixture(
        fixture_id="structure-future-level-selection-v1",
        frame=future_level,
        purpose="Later swing changes simple BOS evaluation at an earlier candle.",
        context={"direction": "bullish", "evaluation_index": 3, "later_swing_index": 5},
    )
    breaks = SyntheticFixture(
        fixture_id="structure-layer2-break-sequence-v1",
        frame=_frame(
            "2025-01-06",
            [100, 105, 100, 106, 107, 104, 103],
            [95, 99, 94, 98, 100, 93, 96],
            [98, 102, 96, 104, 105, 95, 99],
        ),
        purpose="Bearish/bullish BOS and both CHoCH transitions.",
        context={
            "swing_highs": [
                {"index": 1, "price": 105.0, "confirmation_index": 2}
            ],
            "swing_lows": [
                {"index": 0, "price": 95.0, "confirmation_index": 1}
            ],
        },
    )
    mss_valid = SyntheticFixture(
        fixture_id="structure-mss-valid-sequence-v1",
        frame=breaks.frame.copy(deep=True),
        purpose="A candidate CHoCH/new-swing/BOS sequence for missing MSS capability.",
        context={"sequence": ["CHOCH", "NEW_SWING", "BOS"]},
    )
    mss_incomplete = SyntheticFixture(
        fixture_id="structure-mss-incomplete-sequence-v1",
        frame=breaks.frame.iloc[:5].copy(deep=True),
        purpose="A candidate CHoCH/new-swing sequence without confirming BOS.",
        context={"sequence": ["CHOCH", "NEW_SWING"]},
    )
    equal_levels = SyntheticFixture(
        fixture_id="liquidity-equal-levels-v1",
        frame=_frame(
            "2025-02-01",
            [100, 100.1, 99.9, 100.05, 102, 103],
            [90, 90.1, 89.9, 90.05, 88, 87],
            [95, 95.1, 95, 95.2, 100, 99],
            atr=[1] * 6,
        ),
        purpose="Three prior equal highs and lows within ATR tolerance.",
        context={"lookback": 3, "tolerance_atr": 0.15},
    )
    pools = SyntheticFixture(
        fixture_id="liquidity-pool-registration-v1",
        frame=_frame(
            "2025-02-02",
            [98, 100, 99, 98, 97],
            [92, 91, 90, 92, 93],
            [95, 96, 94, 95, 95],
            atr=[1] * 5,
        ),
        purpose="Unswept high/low pools and adapter BSL/SSL registration mapping.",
        context={
            "swing_highs": [
                {"index": 1, "price": 100.0, "confirmation_index": 2}
            ],
            "swing_lows": [
                {"index": 2, "price": 90.0, "confirmation_index": 3}
            ],
        },
    )
    bearish_wick = SyntheticFixture(
        fixture_id="liquidity-bearish-wick-raid-v1",
        frame=_frame(
            "2025-02-03",
            [98, 99, 99, 101, 99, 98],
            [94, 95, 95, 96, 94, 93],
            [96, 97, 97, 99, 98, 96],
            atr=[1] * 6,
        ),
        purpose="High-side wick raid with next-candle bearish reversal.",
        context={
            "swing_highs": [
                {"index": 1, "price": 100.0, "confirmation_index": 2}
            ],
            "swing_lows": [],
        },
    )
    bearish_close = SyntheticFixture(
        fixture_id="liquidity-bearish-close-through-v1",
        frame=_frame(
            "2025-02-04",
            [98, 99, 99, 102, 99.5, 99],
            [94, 95, 95, 98, 96, 95],
            [96, 97, 97, 101, 99, 97],
            atr=[1] * 6,
        ),
        purpose="High-side close-through followed by next-candle bearish reversal.",
        context={
            "swing_highs": [
                {"index": 1, "price": 100.0, "confirmation_index": 2}
            ],
            "swing_lows": [],
        },
    )
    bullish_wick = SyntheticFixture(
        fixture_id="liquidity-bullish-wick-raid-v1",
        frame=_frame(
            "2025-02-05",
            [96, 95, 95, 94, 96, 97],
            [92, 91, 91, 89, 91, 92],
            [94, 93, 93, 91, 92, 95],
            atr=[1] * 6,
        ),
        purpose="Low-side raid with next-candle bullish reversal.",
        context={
            "swing_highs": [],
            "swing_lows": [
                {"index": 1, "price": 90.0, "confirmation_index": 2}
            ],
        },
    )
    ranking = SyntheticFixture(
        fixture_id="liquidity-multiple-destinations-v1",
        frame=_frame(
            "2025-02-06",
            [98, 100, 99, 105, 101, 102],
            [92, 91, 90, 94, 93, 89],
            [95, 96, 94, 101, 98, 95],
            atr=[1] * 6,
        ),
        purpose="Multiple unswept candidate levels with no source ranking contract.",
        context={
            "swing_highs": [
                {"index": 1, "price": 100.0, "confirmation_index": 2},
                {"index": 3, "price": 105.0, "confirmation_index": 4},
            ],
            "swing_lows": [
                {"index": 2, "price": 90.0, "confirmation_index": 3},
                {"index": 5, "price": 89.0, "confirmation_index": 5},
            ],
        },
    )
    fixtures = (
        confirmed,
        insufficient,
        atr_leakage,
        bos_fixture,
        future_level_fixture,
        breaks,
        mss_valid,
        mss_incomplete,
        equal_levels,
        pools,
        bearish_wick,
        bearish_close,
        bullish_wick,
        ranking,
    )
    return {fixture.fixture_id: fixture for fixture in fixtures}


def fixture_evidence(fixtures: dict[str, SyntheticFixture]) -> tuple[FixtureEvidence, ...]:
    return tuple(fixtures[key].evidence() for key in sorted(fixtures))


def timestamp_at(fixture: SyntheticFixture, index: int) -> str:
    return _timestamp(fixture.frame.index[index])
