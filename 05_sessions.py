import pandas as pd
from pathlib import Path

DATA = Path("data_features")

def classify(hour):

    if 0 <= hour < 7:
        return "asia"

    elif 7 <= hour < 13:
        return "london"

    return "newyork"

def main():

    for file in DATA.glob("*.csv"):

        df = pd.read_csv(file)

        ts = pd.to_datetime(df["timestamp"])

        df["session"] = ts.dt.hour.apply(classify)

        df.to_csv(file, index=False)

        print("SESSION:", file.name)

if __name__ == "__main__":
    main()