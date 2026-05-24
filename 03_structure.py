import pandas as pd
from pathlib import Path

DATA = Path("data_features")

def structure(df):

    df["swing_high"] = (
        df["high"]
        ==
        df["high"].rolling(5, center=True).max()
    )

    df["swing_low"] = (
        df["low"]
        ==
        df["low"].rolling(5, center=True).min()
    )

    df["BOS"] = False
    df["CHOCH"] = False

    last_high = None
    last_low = None

    trend = None

    for i in range(len(df)):

        if df["swing_high"].iloc[i]:
            current_high = df["high"].iloc[i]

            if last_high and current_high > last_high:
                df.loc[df.index[i], "BOS"] = True

                if trend == "bear":
                    df.loc[df.index[i], "CHOCH"] = True

                trend = "bull"

            last_high = current_high

        if df["swing_low"].iloc[i]:

            current_low = df["low"].iloc[i]

            if last_low and current_low < last_low:

                df.loc[df.index[i], "BOS"] = True

                if trend == "bull":
                    df.loc[df.index[i], "CHOCH"] = True

                trend = "bear"

            last_low = current_low

    return df

def main():

    for file in DATA.glob("*.csv"):

        df = pd.read_csv(file)

        df = structure(df)

        df.to_csv(file, index=False)

        print("STRUCTURE:", file.name)

if __name__ == "__main__":
    main()