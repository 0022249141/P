"""Tests for the institutional data quality engine."""

from __future__ import annotations

import pandas as pd

from core.schemas import Market, TimeFrame
from validators.data_quality_engine import DataQualityEngine


def _valid_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01 00:00:00", periods=5, freq="5min"),
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [10, 11, 12, 13, 14],
        }
    )


def test_valid_dataframe_scores_cleanly_and_does_not_mutate_input() -> None:
    engine = DataQualityEngine()
    df = _valid_ohlcv()
    original = df.copy(deep=True)

    report = engine.validate_dataframe(df, Market.XAUUSD, TimeFrame.M5)

    assert report.quality_score == 1.0
    assert report.integrity_score == 1.0
    assert report.warnings == []
    assert report.missing_candles == 0
    pd.testing.assert_frame_equal(df, original)


def test_detects_missing_duplicate_corrupted_and_invalid_ohlc_rows() -> None:
    engine = DataQualityEngine()
    df = _valid_ohlcv().drop(index=2).reset_index(drop=True)
    duplicate = df.iloc[[1]].copy()
    duplicate.loc[:, "high"] = 99.0
    duplicate.loc[:, "volume"] = -1
    df = pd.concat([df, duplicate], ignore_index=True)
    df.loc[0, "close"] = float("inf")

    report = engine.validate_dataframe(df, Market.ABSHODEH, TimeFrame.M5)

    assert report.quality_score < 1.0
    assert report.integrity_score < report.quality_score
    assert report.missing_candles == 1
    assert report.duplicate_timestamps == 1
    assert report.corrupted_rows == 1
    assert report.invalid_ohlc_rows == 1
    assert any("NaN/inf" in warning for warning in report.warnings)
    assert any("invalid OHLC" in warning for warning in report.warnings)


def test_missing_required_price_columns_returns_failure_report() -> None:
    engine = DataQualityEngine()
    df = _valid_ohlcv().drop(columns=["close"])

    report = engine.validate_dataframe(df, Market.HARAT, TimeFrame.M15)

    assert report.quality_score == 0.0
    assert report.integrity_score == 0.0
    assert report.warnings == ["Missing required columns: close"]


def test_volume_column_is_optional_but_warned() -> None:
    engine = DataQualityEngine()
    df = _valid_ohlcv().drop(columns=["volume"])

    report = engine.validate_dataframe(df, Market.HARAT, TimeFrame.M15)

    assert report.quality_score < 1.0
    assert report.volume_spikes == 0
    assert report.warnings == ["Volume column missing; skipped volume validation"]


def test_robust_outlier_detection_catches_single_extreme_candle() -> None:
    engine = DataQualityEngine()
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01 00:00:00", periods=20, freq="5min"),
            "open": [100.0] * 20,
            "high": [101.0] * 19 + [140.0],
            "low": [99.0] * 20,
            "close": [100.0] * 20,
            "volume": [10] * 20,
        }
    )

    report = engine.validate_dataframe(df, Market.XAUUSD, TimeFrame.M5)

    assert report.outliers_detected == 1
    assert any("outlier spikes" in warning for warning in report.warnings)
