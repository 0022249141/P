# 01_fix_data.py — نسخهٔ جدید با اعتبارسنجی کامل
import pandas as pd
import numpy as np

def validate_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """اصلاح و حذف کندل‌های نامعتبر"""
    # ۱. High باید بزرگترین و Low کوچکترین باشد
    valid_high = (df['high'] >= df[['open', 'close']].max(axis=1))
    valid_low  = (df['low']  <= df[['open', 'close']].min(axis=1))
    valid_range = df['high'] >= df['low']
    df = df[valid_high & valid_low & valid_range].copy()

    # ۲. حذف اسپایک‌ها (دامنه > ۵ برابر ATR قبلی)
    atr = df['high'] - df['low']  # True Range ساده
    atr_rolling = atr.rolling(14).mean()
    spike_mask = atr <= 5 * atr_rolling.shift(1)
    df = df[spike_mask]

    # ۳. تشخیص گپ زمانی غیرعادی (برای تایم‌فریم‌های ثابت)
    if 'timestamp' in df.columns:
        time_diff = df['timestamp'].diff()
        # اگر اختلاف بیش از ۱.۵ برابر تایم‌فریم معمول باشد، هشدار می‌دهد ولی حذف نمی‌کند
        typical = time_diff.median()
        gaps = time_diff > 1.5 * typical
        if gaps.any():
            print(f"⚠️ {gaps.sum()} گپ زمانی غیرعادی پیدا شد (ممکن است داده گم شده باشد).")

    return df

# ---------- مثال استفاده ----------
if __name__ == "__main__":
    # خواندن فایل خام و ذخیرهٔ تمیز
    raw = pd.read_csv("data/XAU_USD-15.csv")
    clean = validate_ohlc(raw)
    clean.to_csv("data_clean/XAU_USD-15_clean.csv", index=False)