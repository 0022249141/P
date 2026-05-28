from __future__ import annotations

import pandas as pd

from core.schemas import Market, TimeFrame
from validators.data_quality_engine import DataQualityEngine


def _valid_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01 00:00:00", periods=5, freq="5min"),
            "open": [100, 101, 102, 103, 104],
            "high": [101, 102, 103, 104, 105],
            "low": [99, 100, 101, 102, 103],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [10, 11, 12, 13, 14],
        }
    )


def test_valid_dataframe_scores_clean_report() -> None:
    report = DataQualityEngine().validate_dataframe(_valid_df(), Market.XAU_USD, TimeFrame.M5)

    assert report.quality_score == 1.0
    assert report.integrity_score == 1.0
    assert report.warnings == []
    assert report.missing_candles == 0
    assert report.duplicate_timestamps == 0


def test_missing_columns_return_zero_score() -> None:
    df = _valid_df().drop(columns=["volume"])

    report = DataQualityEngine().validate_dataframe(df, Market.XAU_USD, TimeFrame.M5)

    assert report.quality_score == 0.0
    assert report.integrity_score == 0.0
    assert report.warnings == ["Missing required columns: volume"]


def test_corruption_duplicates_and_time_gaps_are_reported() -> None:
    df = _valid_df()
    df.loc[2, "timestamp"] = df.loc[1, "timestamp"]
    df.loc[3, "timestamp"] = pd.Timestamp("2026-01-01 00:10:00")
    df.loc[4, "timestamp"] = pd.Timestamp("2026-01-01 00:30:00")
    df.loc[4, "high"] = 99

    report = DataQualityEngine().validate_dataframe(df, Market.XAU_USD, TimeFrame.M5)

    assert report.quality_score < 1.0
    assert report.duplicate_timestamps == 1
    assert report.missing_candles == 1
    assert any("duplicate timestamps" in warning for warning in report.warnings)
    assert any("missing candles" in warning for warning in report.warnings)
    assert any("invalid OHLC" in warning for warning in report.warnings)
