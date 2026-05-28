# 10_regime.py — طبقه‌بندی رژیم با استفاده از LiquidityEngine
import pandas as pd
import numpy as np
from core_constants import IMMUTABLE

def classify_regime(df: pd.DataFrame, market_name: str = "XAUUSD") -> pd.DataFrame:
    """
    افزودن ستون 'regime' و 'trend_direction' و 'manipulation_sweep'
    با استفاده از Sweep محاسبه‌شده توسط LiquidityEngine (بدون تکرار منطق Sweep)
    """
    df = df.copy()
    n = len(df)

    # پارامترهای پیش‌فرض
    params = {
        "AbshodeNaghdi": {"trending_min_bos": 3, "ranging_max_range_pct": 2.0, "compression_atr_ratio": 0.4,
                          "manipulation_max_candles": 8, "ranging_lookback": 20},
        "HaratUSD": {"trending_min_bos": 3, "ranging_max_range_pct": 2.0, "compression_atr_ratio": 0.4,
                     "manipulation_max_candles": 6, "ranging_lookback": 15},
        "XAUUSD": {"trending_min_bos": 3, "ranging_max_range_pct": 2.0, "compression_atr_ratio": 0.4,
                   "manipulation_max_candles": 8, "ranging_lookback": 20},
    }
    cfg = params.get(market_name, params["XAUUSD"])

    # ستون‌های خروجی
    df['regime'] = 'Unknown'
    df['trend_direction'] = ''
    df['range_pct'] = np.nan
    df['atr_ratio'] = np.nan
    df['manipulation_sweep'] = False

    # محاسبات پایه (ATR، BOS)
    if 'ATR14' not in df.columns:
        high, low, close = df['high'], df['low'], df['close']
        tr = np.maximum(high - low, np.abs(high - close.shift(1)), np.abs(low - close.shift(1)))
        df['ATR14'] = tr.ewm(span=IMMUTABLE["ATR_PERIOD"], adjust=False).mean()
    df['ATR_MA20'] = df['ATR14'].rolling(window=20, min_periods=1).mean()

    # BOS ساده (بدون نیاز به StructureEngine)
    window = 5
    sh = df['high'].rolling(window, min_periods=1).max().shift(1)
    sl = df['low'].rolling(window, min_periods=1).min().shift(1)
    df['bos_bull'] = (df['close'] > sh) & (df['close'].shift(1) <= sh.shift(1))
    df['bos_bear'] = (df['close'] < sl) & (df['close'].shift(1) >= sl.shift(1))

    # --- دریافت Sweep score از LiquidityEngine ---
    from liquidity_engine import LiquidityEngine
    # ایجاد یک نمونهٔ موقت از LiquidityEngine (نیاز به market_engine ندارد، فقط df)
    # برای سادگی: خودمان مستقیماً sweep_score را محاسبه می‌کنیم.
    # اما برای جلوگیری از تکرار کد، یک helper می‌سازیم:
    liq = LiquidityEngine.__new__(LiquidityEngine)
    liq.df = df
    liq.market_name = market_name
    liq.detect_sweeps()
    df['sweep_score'] = liq.df['sweep_score']
    # ------------------------------------------------

    ranging_lookback = cfg["ranging_lookback"]

    for i in range(ranging_lookback, n):
        window = df.iloc[i - ranging_lookback : i + 1]

        # Compressing
        atr_ratio = df['ATR14'].iloc[i] / (df['ATR_MA20'].iloc[i] + 1e-9)
        df.loc[df.index[i], 'atr_ratio'] = atr_ratio
        if atr_ratio < cfg["compression_atr_ratio"]:
            df.loc[df.index[i], 'regime'] = 'Compressing'
            continue

        # Ranging
        range_pct = (window['high'].max() - window['low'].min()) / window['close'].mean() * 100
        df.loc[df.index[i], 'range_pct'] = range_pct
        recent_bos = window['bos_bull'].any() or window['bos_bear'].any()
        if range_pct < cfg["ranging_max_range_pct"] and not recent_bos:
            df.loc[df.index[i], 'regime'] = 'Ranging'
            continue

        # Trending
        bos_bull = window['bos_bull']
        bos_bear = window['bos_bear']
        if bos_bull.sum() >= cfg["trending_min_bos"] and bos_bull.sum() > bos_bear.sum():
            df.loc[df.index[i], 'regime'] = 'Trending'
            df.loc[df.index[i], 'trend_direction'] = 'Bullish'
            continue
        elif bos_bear.sum() >= cfg["trending_min_bos"] and bos_bear.sum() > bos_bull.sum():
            df.loc[df.index[i], 'regime'] = 'Trending'
            df.loc[df.index[i], 'trend_direction'] = 'Bearish'
            continue

        # Manipulation (با استفاده از sweep_score واقعی)
        # شرط: sweep_score بالا (0.6+) در پنجرهٔ manipulation و بازگشت به zone
        if window['sweep_score'].max() >= 0.6:
            dr_high = window['high'].max()
            dr_low = window['low'].min()
            dr_range = dr_high - dr_low
            discount = dr_low + 0.382 * dr_range
            premium  = dr_low + 0.618 * dr_range
            current_close = df['close'].iloc[i]
            if discount <= current_close <= premium:
                df.loc[df.index[i], 'regime'] = 'Manipulation'
                df.loc[df.index[i], 'manipulation_sweep'] = True
                continue

        # پیش‌فرض
        df.loc[df.index[i], 'regime'] = 'Ranging'

    # حذف ستون‌های کمکی
    df.drop(['swing_high', 'swing_low', 'resistance', 'support', 'ATR_MA20',
             'bos_bull', 'bos_bear', 'sweep_bull', 'sweep_bear'], axis=1, inplace=True, errors='ignore')
    return df