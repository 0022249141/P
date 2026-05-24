"""Liquidity analysis - Detect equal highs and lows in market data."""
import pandas as pd
from pathlib import Path

DATA = Path("data_features")

THRESHOLD = 0.0005

def liquidity(df):
    """Detect equal highs and lows in price data."""
    df["equal_highs"] = False
    df["equal_lows"] = False

    for i in range(1, len(df)):

        h1 = df["high"].iloc[i-1]
        h2 = df["high"].iloc[i]

        l1 = df["low"].iloc[i-1]
        l2 = df["low"].iloc[i]

        if abs(h1-h2)/h1 < THRESHOLD:
            df.loc[df.index[i], "equal_highs"] = True

        if abs(l1-l2)/l1 < THRESHOLD:
            df.loc[df.index[i], "equal_lows"] = True

    return df

def main():
    """Process all CSV files and add liquidity features."""
    for file in DATA.glob("*.csv"):

        df = pd.read_csv(file)

        df = liquidity(df)

        df.to_csv(file, index=False)

        print("LIQUIDITY:", file.name)

if __name__ == "__main__":
    main()
