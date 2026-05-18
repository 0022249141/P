import pandas as pd
from pathlib import Path

SRC = Path("data_clean")
OUT = Path("data_features")

OUT.mkdir(exist_ok=True)

TIMEFRAMES = {
    "5T": "5m",
    "15T": "15m",
    "1H": "1h",
    "4H": "4h",
    "1D": "1d"
}

def resample_file(file):

    df = pd.read_csv(file)

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df = df.set_index("timestamp")

    for tf, name in TIMEFRAMES.items():

        r = df.resample(tf).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        })

        r = r.dropna()

        out = OUT / f"{file.stem}_{name}.csv"

        r.to_csv(out)

        print("RESAMPLED:", out.name)

def main():

    for file in SRC.glob("*-1.csv"):
        resample_file(file)

if __name__ == "__main__":
    main()