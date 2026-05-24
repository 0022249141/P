# 10_regime.py — طبقه‌بندی رژیم بازار (Regime Classification)
# نسخه ۱.۰ — سازگار با چارچوب SMC/ICT
# خروجی: ستون‌های regime, trend_direction, range_pct, atr_ratio, manipulation_sweep

import pandas as pd
import numpy as np

# -------------------------------------------------------------------
# پارامترهای پیش‌فرض (قابل تنظیم از market_params)
# -------------------------------------------------------------------
DEFAULT_PARAMS = {
    "AbshodeNaghdi": {
        "trending_min_bos": 3,
        "ranging_max_range_pct": 2.0,
        "compression_atr_ratio": 0.4,
        "manipulation_max_candles": 8,
        "ranging_lookback": 20,
    },
    "HaratUSD": {
        "trending_min_bos": 3,
        "ranging_max_range_pct": 2.0,
        "compression_atr_ratio": 0.4,
        "manipulation_max_candles": 6,  # هرات سریع‌تر بازمی‌گردد
        "ranging_lookback": 15,
    },
    "XAUUSD": {
        "trending_min_bos": 3,
        "ranging_max_range_pct": 2.0,
        "compression_atr_ratio": 0.4,
        "manipulation_max_candles": 8,
        "ranging_lookback": 20,
    },
}

# -------------------------------------------------------------------
# تابع کمکی: تشخیص BOS ساده بر اساس شکست سوئینگ‌های محلی
# -------------------------------------------------------------------
def detect_local_bos(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    تشخیص BOS صعودی/نزولی با مقایسه Close و آخرین سوئینگ محلی.
    خروجی: دو ستون boolean: 'bos_bull', 'bos_bear'
    """
    df = df.copy()
    # محاسبه swing highs/lows به صورت rolling
    df['swing_high'] = df['high'].rolling(window=window, min_periods=1).max().shift(1)
    df['swing_low']  = df['low'].rolling(window=window, min_periods=1).min().shift(1)

    df['bos_bull'] = (df['close'] > df['swing_high']) & (df['close'].shift(1) <= df['swing_high'].shift(1))
    df['bos_bear'] = (df['close'] < df['swing_low']) & (df['close'].shift(1) >= df['swing_low'].shift(1))
    return df

# -------------------------------------------------------------------
# تابع کمکی: تشخیص Sweep ساده (شکست سطح و برگشت)
# -------------------------------------------------------------------
def detect_sweep_simple(df: pd.DataFrame, atr_period: int = 14) -> pd.DataFrame:
    """
    تشخیص Sweep (جاروب) ساده:
    - صعودی: قیمت از یک مقاومت عبور کند سپس Close زیر آن برگردد.
    - نزولی: قیمت یک حمایت را بشکند سپس Close بالای آن برگردد.
    خروجی: 'sweep_bull', 'sweep_bear' (boolean)
    """
    df = df.copy()
    if 'ATR14' not in df.columns:
        high, low, close = df['high'], df['low'], df['close']
        tr = np.maximum(high - low, np.abs(high - close.shift(1)), np.abs(low - close.shift(1)))
        df['ATR14'] = tr.ewm(span=atr_period, adjust=False).mean()

    # استفاده از مقاومت/حمایت = high/low کندل قبلی (ساده)
    df['resistance'] = df['high'].shift(1)
    df['support']    = df['low'].shift(1)

    # Sweep نزولی (شکار فروشنده‌ها)
    df['sweep_bull'] = (df['low'] < df['support']) & (df['close'] > df['support'])
    # Sweep صعودی (شکار خریدارها)
    df['sweep_bear'] = (df['high'] > df['resistance']) & (df['close'] < df['resistance'])

    return df

# -------------------------------------------------------------------
# تابع اصلی: طبقه‌بندی رژیم
# -------------------------------------------------------------------
def classify_regime(df: pd.DataFrame, market_name: str = "XAUUSD") -> pd.DataFrame:
    """
    افزودن ستون 'regime' و ستون‌های کمکی به DataFrame.

    Parameters
    ----------
    df : DataFrame
        دارای ستون‌های OHLCV + timestamp
    market_name : str
        نام بازار (XAUUSD, AbshodeNaghdi, HaratUSD)

    Returns
    -------
    DataFrame با ستون‌های جدید:
        - regime: یکی از 'Trending', 'Ranging', 'Compressing', 'Manipulation', 'Unknown'
        - trend_direction: 'Bullish' / 'Bearish' (فقط در حالت Trending)
        - range_pct: درصد دامنه N کندل
        - atr_ratio: نسبت ATR فعلی به میانگین
        - manipulation_sweep: True اگر Manipulation شناسایی شود
    """
    params = DEFAULT_PARAMS.get(market_name, DEFAULT_PARAMS["XAUUSD"])

    df = df.copy()
    n = len(df)

    # ستون‌های خروجی
    df['regime'] = 'Unknown'
    df['trend_direction'] = ''
    df['range_pct'] = np.nan
    df['atr_ratio'] = np.nan
    df['manipulation_sweep'] = False

    # محاسبات پایه
    if 'ATR14' not in df.columns:
        high, low, close = df['high'], df['low'], df['close']
        tr = np.maximum(high - low, np.abs(high - close.shift(1)), np.abs(low - close.shift(1)))
        df['ATR14'] = tr.ewm(span=14, adjust=False).mean()
    df['ATR_MA20'] = df['ATR14'].rolling(window=20, min_periods=1).mean()  # میانگین بلندمدت

    # تشخیص BOS و Sweep
    df = detect_local_bos(df, window=5)
    df = detect_sweep_simple(df)

    # پارامترهای N
    ranging_lookback = params["ranging_lookback"]

    for i in range(ranging_lookback, n):
        window = df.iloc[i - ranging_lookback : i + 1]

        # ----- Compressing -----
        atr_ratio = df['ATR14'].iloc[i] / (df['ATR_MA20'].iloc[i] + 1e-9)
        df.loc[df.index[i], 'atr_ratio'] = atr_ratio
        if atr_ratio < params["compression_atr_ratio"]:
            df.loc[df.index[i], 'regime'] = 'Compressing'
            continue

        # ----- Ranging -----
        range_pct = (window['high'].max() - window['low'].min()) / window['close'].mean() * 100
        df.loc[df.index[i], 'range_pct'] = range_pct
        recent_bos = window['bos_bull'].any() or window['bos_bear'].any()
        if range_pct < params["ranging_max_range_pct"] and not recent_bos:
            df.loc[df.index[i], 'regime'] = 'Ranging'
            continue

        # ----- Trending -----
        # شمارش BOS متوالی در یک جهت
        bos_bull = window['bos_bull']
        bos_bear = window['bos_bear']
        # ساده: اگر تعداد BOS صعودی ≥ حداقل باشد و نزولی کمتر، روند صعودی
        if bos_bull.sum() >= params["trending_min_bos"] and bos_bull.sum() > bos_bear.sum():
            df.loc[df.index[i], 'regime'] = 'Trending'
            df.loc[df.index[i], 'trend_direction'] = 'Bullish'
            continue
        elif bos_bear.sum() >= params["trending_min_bos"] and bos_bear.sum() > bos_bull.sum():
            df.loc[df.index[i], 'regime'] = 'Trending'
            df.loc[df.index[i], 'trend_direction'] = 'Bearish'
            continue

        # ----- Manipulation -----
        # شرط: Sweep (bull یا bear) و سپس بازگشت سریع به محدوده ارزش
        if window['sweep_bull'].any() or window['sweep_bear'].any():
            # بررسی بازگشت به محدوده ۳۸.۲٪ تا ۶۱.۸٪ (منطقه ارزش)
            dr_high = window['high'].max()
            dr_low = window['low'].min()
            dr_range = dr_high - dr_low
            discount = dr_low + 0.382 * dr_range
            premium  = dr_low + 0.618 * dr_range
            current_close = df['close'].iloc[i]
            if discount <= current_close <= premium:
                # بررسی سرعت: Sweep در کمتر از N کندل قبل رخ داده؟
                # چک می‌کنیم آیا Sweep در ۸ کندل اخیر بوده
                recent_sweep = False
                for j in range(max(0, i - params["manipulation_max_candles"]), i+1):
                    if df['sweep_bull'].iloc[j] or df['sweep_bear'].iloc[j]:
                        recent_sweep = True
                        break
                if recent_sweep:
                    df.loc[df.index[i], 'regime'] = 'Manipulation'
                    df.loc[df.index[i], 'manipulation_sweep'] = True
                    continue

        # پیش‌فرض: Trending ضعیف یا Ranging
        df.loc[df.index[i], 'regime'] = 'Ranging'

    # حذف ستون‌های موقت (اختیاری)
    df.drop(['swing_high', 'swing_low', 'resistance', 'support', 'ATR_MA20',
             'bos_bull', 'bos_bear', 'sweep_bull', 'sweep_bear'], axis=1, inplace=True, errors='ignore')

    return df


# -------------------------------------------------------------------
# اجرای مستقل
# -------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="طبقه‌بندی رژیم بازار")
    parser.add_argument("input", help="مسیر فایل CSV ورودی")
    parser.add_argument("--market", default="XAUUSD", help="نام بازار")
    parser.add_argument("--output", default="output_regime.csv", help="مسیر خروجی")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    result = classify_regime(df, args.market)

    result.to_csv(args.output, index=False)
    print(f"✅ رژیم بازار در {args.output} ذخیره شد.")
    print(result['regime'].value_counts().to_string())