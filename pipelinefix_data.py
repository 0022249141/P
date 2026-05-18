import pandas as pd
from pathlib import Path

RAW = Path("data")
CLEAN = Path("data_clean")
CLEAN.mkdir(exist_ok=True)

def fix(file):
    df = pd.read_csv(file, header=None)

    # بروکر format: date,time,open,high,low,close,volume
    if df.shape[1] >= 6:
        df.columns = ["date","time","open","high","low","close","volume"]

        df["timestamp"] = df["date"].astype(str) + " " + df["time"].astype(str)

        df = df[["timestamp","open","high","low","close","volume"]]

        out = CLEAN / file.name
        df.to_csv(out, index=False)

        print("FIXED:", file.name)

def main():
    for f in RAW.glob("*.csv"):
        if "signals" in f.name:
            continue
        fix(f)

if __name__ == "__main__":
    main()