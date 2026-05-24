# 07_fvg.py — تشخیص Fair Value Gap (شکاف ارزش منصفانه)
# نسخه ۱.۰ — سازگار با چارچوب SMC/ICT
# خروجی: ستون‌های fvg_bull, fvg_bear, fvg_high, fvg_low, fvg_status

import pandas as pd
import numpy as np
from pathlib import Path

# -------------------------------------------------------------------
# ۱. پارامترهای حداقل اندازه FVG برای هر بازار (درصدی از قیمت)
# -------------------------------------------------------------------
FVG_MIN_PCT = {
    "AbshodeNaghdi": 0.0015,   # ۰.۱۵٪
    "HaratUSD":      0.0010,   # ۰.۱۰٪
    "XAUUSD":        0.0015,   # ۰.۱۵٪
}

# -------------------------------------------------------------------
# ۲. تابع اصلی تشخیص FVG
# -------------------------------------------------------------------
def detect_fvg(df: pd.DataFrame, market_name: str) -> pd.DataFrame:
    """
    تشخیص FVG صعودی و نزولی در یک DataFrame دارای ستون‌های:
    'timestamp', 'open', 'high', 'low', 'close', 'volume'
    (ATR14 نیز می‌تواند وجود داشته باشد اما ضروری نیست)

    خروجی: همان DataFrame با ستون‌های اضافه‌شده زیر:
        - fvg_bull:   bool (True اگر یک FVG صعودی در این کندل آغاز شود)
        - fvg_bear:   bool (True اگر FVG نزولی آغاز شود)
        - fvg_high:   float (بالاترین محدودهٔ FVG)
        - fvg_low:    float (پایین‌ترین محدودهٔ FVG)
        - fvg_status: str ('Open', 'Partially_Filled', 'Closed')
    """

    df = df.copy()
    n = len(df)

    # ستون‌های خروجی را با مقدار پیش‌فرض پر می‌کنیم
    df['fvg_bull']   = False
    df['fvg_bear']   = False
    df['fvg_high']   = np.nan
    df['fvg_low']    = np.nan
    df['fvg_status'] = ''

    # حداقل شکاف به درصد (از دیکشنری بالا می‌خوانیم، در غیر اینصورت ۰.۱۵٪)
    min_pct = FVG_MIN_PCT.get(market_name, 0.0015)

    # برای هر سه کندل متوالی (i-1, i, i+1) که در آن i کندل جاری (Displacement) است،
    # اما طبق تعریف استاندارد ICT، FVG بین کندل اول و سوم (با فاصله یک کندل) ایجاد می‌شود.
    # پیاده‌سازی دقیق: اگر high کندل i-1 کمتر از low کندل i+1 باشد → FVG صعودی.
    for i in range(1, n - 1):
        # FVG صعودی
        if df['high'].iloc[i-1] < df['low'].iloc[i+1]:
            gap = df['low'].iloc[i+1] - df['high'].iloc[i-1]
            # حداقل اندازه شکاف نسبت به قیمت فعلی (میانه محدوده)
            ref_price = (df['high'].iloc[i-1] + df['low'].iloc[i+1]) / 2
            if gap / ref_price >= min_pct:
                df.loc[df.index[i], 'fvg_bull'] = True
                df.loc[df.index[i], 'fvg_high'] = df['low'].iloc[i+1]
                df.loc[df.index[i], 'fvg_low']  = df['high'].iloc[i-1]

        # FVG نزولی
        if df['low'].iloc[i-1] > df['high'].iloc[i+1]:
            gap = df['low'].iloc[i-1] - df['high'].iloc[i+1]
            ref_price = (df['low'].iloc[i-1] + df['high'].iloc[i+1]) / 2
            if gap / ref_price >= min_pct:
                df.loc[df.index[i], 'fvg_bear'] = True
                df.loc[df.index[i], 'fvg_high'] = df['low'].iloc[i-1]
                df.loc[df.index[i], 'fvg_low']  = df['high'].iloc[i+1]

    # -------------------------------------------------------------------
    # ۳. تعیین وضعیت هر FVG (Open / Partially_Filled / Closed)
    #    با نگاه به آینده (حرکت قیمت بعد از تشکیل FVG)
    # -------------------------------------------------------------------
    for i in range(n):
        if df['fvg_bull'].iloc[i] or df['fvg_bear'].iloc[i]:
            high_level = df['fvg_high'].iloc[i]
            low_level  = df['fvg_low'].iloc[i]
            status = "Open"
            # جستجو از کندل بعدی تا آخرین کندل
            for j in range(i+1, n):
                candle_high = df['high'].iloc[j]
                candle_low  = df['low'].iloc[j]
                # اگر قیمت به هر شکلی وارد محدوده شده باشد
                if candle_low <= high_level and candle_high >= low_level:
                    # بررسی پر شدن کامل: اگر قیمت کاملاً از محدوده عبور کرده باشد
                    if (df['fvg_bull'].iloc[i] and candle_low <= low_level) or \
                       (df['fvg_bear'].iloc[i] and candle_high >= high_level):
                        status = "Closed"
                        break
                    else:
                        status = "Partially_Filled"
                        # ممکن است بعداً بسته شود، ادامه می‌دهیم
            df.loc[df.index[i], 'fvg_status'] = status

    return df


# -------------------------------------------------------------------
# ۴. بلوک اصلی برای اجرای مستقل (اختیاری)
# -------------------------------------------------------------------
if __name__ == "__main__":
    # نمونه: اجرا روی یک فایل CSV
    import argparse

    parser = argparse.ArgumentParser(description="تشخیص Fair Value Gap در داده‌های OHLCV")
    parser.add_argument("input", help="مسیر فایل CSV ورودی")
    parser.add_argument("--market", default="XAUUSD", help="نام بازار (AbshodeNaghdi, HaratUSD, XAUUSD)")
    parser.add_argument("--output", default="output_fvg.csv", help="مسیر فایل خروجی")
    args = parser.parse_args()

    # خواندن داده (فرض می‌کنیم فایل تمیز شده و دارای timestamp باشد)
    df = pd.read_csv(args.input)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    # اجرای تشخیص
    result = detect_fvg(df, args.market)

    # ذخیره
    result.to_csv(args.output, index=False)
    print(f"✅ FVG‌ها در {args.output} ذخیره شدند.")
    print(f"   FVG صعودی: {result['fvg_bull'].sum()} | FVG نزولی: {result['fvg_bear'].sum()}")