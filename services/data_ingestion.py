from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import re

import pandas as pd

from core.schemas import DataQualityReport, Market, TimeFrame
from validators.data_quality_engine import DataQualityEngine


STANDARD_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class LoadedDataset:
    path: Path
    market: Market
    timeframe: TimeFrame
    dataframe: pd.DataFrame
    quality_report: DataQualityReport
    header_detected: bool


class DataIngestionError(ValueError):
    pass


class DataIngestionService:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.quality_engine = DataQualityEngine()

    def load_file(self, path: str | Path, min_quality_score: float = 0.0) -> LoadedDataset:
        csv_path = Path(path)
        if not csv_path.is_absolute():
            csv_path = self.data_dir / csv_path

        if not csv_path.exists():
            raise DataIngestionError(f"CSV file not found: {csv_path}")

        market, timeframe = self._parse_filename(csv_path.name)
        df, header_detected = self._read_csv_flexible(csv_path)
        df = self._clean_for_pipeline(df)

        report = self.quality_engine.validate_dataframe(df, market, timeframe)

        if report.quality_score < min_quality_score:
            raise DataIngestionError(
                f"Data quality below threshold: {csv_path.name}; "
                f"quality={report.quality_score}; warnings={report.warnings}"
            )

        return LoadedDataset(
            path=csv_path,
            market=market,
            timeframe=timeframe,
            dataframe=df,
            quality_report=report,
            header_detected=header_detected,
        )

    def audit_directory(self, pattern: str = "*.csv", min_quality_score: float = 0.0) -> list[dict]:
        rows: list[dict] = []

        for path in sorted(self.data_dir.glob(pattern)):
            if path.name.startswith(("output_", "struct_processed_", "quality_", "data_quality_")):
                continue

            try:
                loaded = self.load_file(path, min_quality_score=min_quality_score)
                report = loaded.quality_report
                rows.append(
                    {
                        "file": path.name,
                        "status": "ok",
                        "market": loaded.market.value,
                        "timeframe": loaded.timeframe.value,
                        "rows": len(loaded.dataframe),
                        "header_detected": loaded.header_detected,
                        "quality_score": report.quality_score,
                        "integrity_score": report.integrity_score,
                        "missing_candles": report.missing_candles,
                        "duplicate_timestamps": report.duplicate_timestamps,
                        "outliers_detected": report.outliers_detected,
                        "gaps_detected": report.gaps_detected,
                        "warnings": " | ".join(report.warnings),
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "file": path.name,
                        "status": "failed",
                        "market": "",
                        "timeframe": "",
                        "rows": 0,
                        "header_detected": "",
                        "quality_score": 0.0,
                        "integrity_score": 0.0,
                        "missing_candles": "",
                        "duplicate_timestamps": "",
                        "outliers_detected": "",
                        "gaps_detected": "",
                        "warnings": str(exc),
                    }
                )

        return rows

    def _parse_filename(self, filename: str) -> tuple[Market, TimeFrame]:
        stem = Path(filename).stem
        if "-" not in stem:
            raise DataIngestionError(f"Invalid filename format: {filename}")

        market_token, timeframe_token = stem.rsplit("-", 1)
        return self._resolve_market(market_token), self._resolve_timeframe(timeframe_token)

    def _resolve_market(self, token: str) -> Market:
        normalized = self._norm(token)

        aliases = {
            "xauusd": ["XAUUSD", "XAU_USD", "xauusd", "xau_usd"],
            "abshodenaghdi": ["ABSHODEH", "abshodeh", "abshodeNaghdi", "abshode_naghdi"],
            "haratfardayi": ["HARAT", "harat", "haratFardayi", "herat", "herat_fardayi"],
        }

        candidates = [token, *aliases.get(normalized, [])]
        return self._resolve_enum(Market, candidates, "Market")

    def _resolve_timeframe(self, token: str) -> TimeFrame:
        key = token.strip().upper()

        direct_map = {
            "1": "M1",
            "5": "M5",
            "15": "M15",
            "30": "M30",
            "60": "H1",
            "240": "H4",
            "1D": "D1",
            "1W": "W1",
            "1M": "MN1",
        }

        if key in direct_map and hasattr(TimeFrame, direct_map[key]):
            return getattr(TimeFrame, direct_map[key])

        return self._resolve_enum(TimeFrame, [token, key, token.lower()], "TimeFrame")

    def _resolve_enum(self, enum_cls, candidates: Iterable[str], enum_name: str):
        normalized_candidates = {self._norm(item) for item in candidates}

        for member in enum_cls:
            if self._norm(member.name) in normalized_candidates:
                return member
            if self._norm(member.value) in normalized_candidates:
                return member

        raise DataIngestionError(
            f"Unable to resolve {enum_name} from candidates: {sorted(normalized_candidates)}"
        )

    def _read_csv_flexible(self, path: Path) -> tuple[pd.DataFrame, bool]:
        header_df = pd.read_csv(path)
        header_df = self._standardize_headered_dataframe(header_df)

        if set(STANDARD_COLUMNS).issubset(header_df.columns):
            return header_df[STANDARD_COLUMNS].copy(), True

        raw_df = pd.read_csv(path, header=None).dropna(how="all")
        if raw_df.empty:
            raise DataIngestionError(f"CSV is empty: {path.name}")

        return self._standardize_headerless_dataframe(raw_df, path.name), False

    def _standardize_headered_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        normalized_to_original = {self._norm(col): col for col in df.columns}

        if "date" in normalized_to_original and "time" in normalized_to_original:
            date_col = normalized_to_original["date"]
            time_col = normalized_to_original["time"]
            df["timestamp"] = df[date_col].astype(str) + " " + df[time_col].astype(str)

        rename_map = {}

        for col in df.columns:
            key = self._norm(col)

            if key in {"timestamp", "datetime", "time"}:
                rename_map[col] = "timestamp"
            elif key in {"open", "openprice"}:
                rename_map[col] = "open"
            elif key in {"high", "highprice"}:
                rename_map[col] = "high"
            elif key in {"low", "lowprice"}:
                rename_map[col] = "low"
            elif key in {"close", "closeprice"}:
                rename_map[col] = "close"
            elif key in {"volume", "vol", "tickvolume", "tickvol", "realvolume"}:
                rename_map[col] = "volume"

        return df.rename(columns=rename_map)

    def _standardize_headerless_dataframe(self, df: pd.DataFrame, filename: str) -> pd.DataFrame:
        if df.shape[1] >= 7:
            combined_ts = pd.to_datetime(
                df.iloc[:, 0].astype(str) + " " + df.iloc[:, 1].astype(str),
                errors="coerce",
            )
            if float(combined_ts.notna().mean()) >= 0.8:
                return pd.DataFrame(
                    {
                        "timestamp": combined_ts,
                        "open": df.iloc[:, 2],
                        "high": df.iloc[:, 3],
                        "low": df.iloc[:, 4],
                        "close": df.iloc[:, 5],
                        "volume": df.iloc[:, 6],
                    }
                )[STANDARD_COLUMNS]

        if df.shape[1] >= 6:
            out = df.iloc[:, :6].copy()
            out.columns = STANDARD_COLUMNS
            return out

        if df.shape[1] == 5:
            out = df.iloc[:, :5].copy()
            out.columns = ["timestamp", "open", "high", "low", "close"]
            out["volume"] = 0.0
            return out[STANDARD_COLUMNS]

        raise DataIngestionError(
            f"Headerless CSV '{filename}' has {df.shape[1]} columns; expected at least 5."
        )

    def _clean_for_pipeline(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df[STANDARD_COLUMNS].copy()
        out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")

        for col in ["open", "high", "low", "close", "volume"]:
            out[col] = pd.to_numeric(out[col], errors="coerce")

        out = out.dropna(subset=STANDARD_COLUMNS)
        out = out.sort_values("timestamp").drop_duplicates(subset="timestamp").reset_index(drop=True)

        invalid = (
            (out["high"] < out[["open", "close", "low"]].max(axis=1))
            | (out["low"] > out[["open", "close", "high"]].min(axis=1))
            | (out["volume"] < 0)
        )

        return out.loc[~invalid].reset_index(drop=True)


    @staticmethod
    def _norm(value: object) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


DataLoader = DataIngestionService