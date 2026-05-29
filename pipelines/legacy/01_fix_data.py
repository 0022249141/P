# -*- coding: utf-8 -*-
"""
CSV Cleaner & Normalizer
Author: Pouria Workflow Edition

هدف:
تبدیل دیتای خام با فرمت:
YYYY.MM.DD,HH:MM,open,high,low,close,volume

به فرمت استاندارد:
timestamp,open,high,low,close,volume

نمونه خروجی:
2024-04-05 13:30:00,2291.085,2296.23,2290.825,2294.975,2077
"""

from pathlib import Path
import pandas as pd
import numpy as np

# =========================
# تنظیمات
# =========================

INPUT_FOLDER = "raw_data"
OUTPUT_FOLDER = "clean_data"

VALID_FILES = [
    "XAU_USD-60.csv",
    "XAU_USD-5.csv",
    "XAU_USD-30.csv",
    "XAU_USD-240.csv",
    "XAU_USD-1W.csv",
    "XAU_USD-1M.csv",
    "XAU_USD-1D.csv",
    "XAU_USD-15.csv",
    "XAU_USD-1.csv",

    "haratFardayi-60.csv",
    "haratFardayi-5.csv",
    "haratFardayi-30.csv",
    "haratFardayi-240.csv",
    "haratFardayi-1W.csv",
    "haratFardayi-1M.csv",
    "haratFardayi-1D.csv",
    "haratFardayi-15.csv",
    "haratFardayi-1.csv",

    "abshodeNaghdi-60.csv",
    "abshodeNaghdi-5.csv",
    "abshodeNaghdi-30.csv",
    "abshodeNaghdi-240.csv",
    "abshodeNaghdi-1W.csv",
    "abshodeNaghdi-1M.csv",
    "abshodeNaghdi-1D.csv",
    "abshodeNaghdi-15.csv",
    "abshodeNaghdi-1.csv"
]

# =========================
# ساخت پوشه خروجی
# =========================

Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

# =========================
# تابع پاکسازی
# =========================

def clean_csv(file_path, output_path):

    try:
        # -----------------------------------
        # خواندن فایل خام بدون هدر
        # -----------------------------------
        df = pd.read_csv(
            file_path,
            header=None,
            dtype=str,
            encoding="utf-8"
        )

        # -----------------------------------
        # بررسی تعداد ستون
        # فرمت خام باید 7 ستون باشد:
        # date,time,open,high,low,close,volume
        # -----------------------------------
        if df.shape[1] != 7:
            print(f"[SKIPPED] ستون نامعتبر: {file_path.name}")
            return

        df.columns = [
            "date",
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]

        # -----------------------------------
        # ساخت timestamp استاندارد
        # -----------------------------------
        df["timestamp"] = pd.to_datetime(
            df["date"].str.strip() + " " + df["time"].str.strip(),
            format="%Y.%m.%d %H:%M",
            errors="coerce"
        )

        # حذف ردیف‌های خراب
        df = df.dropna(subset=["timestamp"])

        # -----------------------------------
        # تبدیل timestamp
        # YYYY-MM-DD HH:MM:SS
        # -----------------------------------
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

        # -----------------------------------
        # تبدیل ستون‌های عددی
        # -----------------------------------
        numeric_cols = ["open", "high", "low", "close", "volume"]

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # حذف ردیف‌های خراب
        df = df.dropna(subset=numeric_cols)

        # -----------------------------------
        # حذف دیتای غیرمنطقی
        # -----------------------------------
        df = df[
            (df["high"] >= df["low"]) &
            (df["high"] >= df["open"]) &
            (df["high"] >= df["close"]) &
            (df["low"] <= df["open"]) &
            (df["low"] <= df["close"]) &
            (df["volume"] >= 0)
        ]

        # -----------------------------------
        # حذف duplicate timestamp
        # آخرین رکورد نگه داشته می‌شود
        # -----------------------------------
        df = df.drop_duplicates(
            subset=["timestamp"],
            keep="last"
        )

        # -----------------------------------
        # مرتب‌سازی زمانی
        # -----------------------------------
        df = df.sort_values("timestamp")

        # -----------------------------------
        # فقط ستون‌های استاندارد
        # -----------------------------------
        df = df[
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        ]

        # -----------------------------------
        # ذخیره خروجی
        # -----------------------------------
        df.to_csv(
            output_path,
            index=False,
            encoding="utf-8"
        )

        print(f"[DONE] {file_path.name} -> {output_path}")

        # -----------------------------------
        # گزارش کیفیت دیتا
        # -----------------------------------
        print(f"Rows: {len(df)}")
        print(f"From: {df['timestamp'].iloc[0]}")
        print(f"To  : {df['timestamp'].iloc[-1]}")
        print("-" * 50)

    except Exception as e:
        print(f"[ERROR] {file_path.name}")
        print(str(e))
        print("-" * 50)


# =========================
# اجرای کلی
# =========================

def main():

    input_dir = Path(INPUT_FOLDER)
    output_dir = Path(OUTPUT_FOLDER)

    print("=" * 60)
    print("START CLEANING DATA")
    print("=" * 60)

    for filename in VALID_FILES:

        input_file = input_dir / filename

        if not input_file.exists():
            print(f"[NOT FOUND] {filename}")
            continue

        output_file = output_dir / filename

        clean_csv(
            file_path=input_file,
            output_path=output_file
        )

    print("=" * 60)
    print("ALL TASKS FINISHED")
    print("=" * 60)


if __name__ == "__main__":
    main()
