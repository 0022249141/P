import pandas as pd
from pathlib import Path

RAW = Path("data")
CLEAN = Path("data_clean")

CLEAN.mkdir(exist_ok=True)

def clean_file(file):

    df = pd.read_csv(file, header=None)

    df.columns = [
        "date",
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    df["timestamp"] = pd.to_datetime(
        df["date"].astype(str) + " " + df["time"].astype(str),
        errors="coerce"
    )

    df = df.dropna()

    numeric = ["open","high","low","close","volume"]

    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna()

    df = df.sort_values("timestamp")

    df = df[
        ["timestamp","open","high","low","close","volume"]
    ]

    out = CLEAN / file.name

    df.to_csv(out, index=False)

    print("CLEANED:", file.name)

def main():

    for file in RAW.glob("*.csv"):

        if "signals" in file.name:
            continue

        clean_file(file)

if __name__ == "__main__":
    main()