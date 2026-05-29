# 02_resample_mtf.py — نسخهٔ جدید با فیلتر سشن
import pandas as pd
from pathlib import Path

def resample_file(file: Path, market_name: str):
    df = pd.read_csv(file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    # ----- فیلتر سشن تهران -----
    if market_name in ["AbshodeNaghdi", "HaratUSD"]:
        # تنظیم timezone
        df.index = df.index.tz_localize('Asia/Tehran')
        # نگهداشتن فقط ساعات ۹ تا ۲۲
        df = df.between_time('09:00', '22:00')
    # ---------------------------

    # نقشه تایم‌فریم‌ها (همان‌طور که از market_params می‌آید)
    from market_params import TIMEFRAMES_BY_MARKET
    rules = TIMEFRAMES_BY_MARKET[market_name]["rules"]

    for tf_code, tf_name in rules.items():
        r = df.resample(tf_code).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        })
        r = r.dropna()
        print(f"RESAMPLED [{market_name}]: {tf_name} -> {r.shape}")
        yield tf_name, r