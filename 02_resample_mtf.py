import pandas as pd
from pathlib import Path

# =========================
# PATHS
# =========================
SRC = Path("data_clean")
OUT = Path("data_features")
OUT.mkdir(exist_ok=True)

# =========================
# TIMEFRAME STANDARD (INSTITUTIONAL)
# =========================
TIMEFRAMES = {
    "5min": "5min",
    "15min": "15min",
    "30min": "30min",
    "60min": "60min",
    "240min": "240min",
    "1D": "1D",
    "1W": "1W",
    "1M": "1M"
}

# =========================
# VALIDATION LAYER
# =========================
def validate_df(df: pd.DataFrame):
    required_cols = {"open", "high", "low", "close", "volume"}

    if df.empty:
        raise ValueError("Empty dataframe")

    if not required_cols.issubset(df.columns):
        raise ValueError(f"Missing columns: {required_cols - set(df.columns)}")

    if df.isna().sum().sum() > 0:
        df = df.dropna()

    return df


# =========================
# RESAMPLE ENGINE
# =========================
def resample_engine(df: pd.DataFrame, rule: str):

    # ensure datetime index
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()

    # core resample (institutional OHLCV logic)
    r = df.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    })

    # remove incomplete candles
    r = r.dropna()

    return r


# =========================
# PIPELINE PER FILE
# =========================
def process_file(file: Path):

    df = pd.read_csv(file)
    df = validate_df(df)

    for tf_name, rule in TIMEFRAMES.items():

        r = resample_engine(df.copy(), rule)

        out_name = f"{file.stem}_{tf_name}.csv"
        out_path = OUT / out_name

        r.to_csv(out_path)

        print(f"[OK] {out_name} -> {r.shape}")


# =========================
# MAIN
# =========================
def main():
    files = list(SRC.glob("*.csv"))

    if not files:
        raise FileNotFoundError("No CSV files found in data_clean")

    for file in files:
        process_file(file)


if __name__ == "__main__":
    main()