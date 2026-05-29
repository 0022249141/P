# -*- coding: utf-8 -*-
"""
run_fixed.py — پایپ‌لاین اصلاح‌شده نسخه ۴
همه لایه‌ها vectorized — بدون حلقه Python روی کل داده
"""

import sys, importlib
import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "src"))

disp_mod  = importlib.import_module("pipelines.legacy.08_displacement")
zone_mod  = importlib.import_module("pipelines.legacy.09_zone_scoring")
state_mod = importlib.import_module("pipelines.legacy.10_state_machine")
exec_mod  = importlib.import_module("pipelines.legacy.11_execution")

detect_displacement       = disp_mod.detect_displacement
score_order_blocks        = zone_mod.score_order_blocks
score_breakers_vectorized = zone_mod.score_breakers_vectorized
compute_setup_score       = zone_mod.compute_setup_score
apply_state_machine       = state_mod.apply_state_machine
compute_trade_parameters  = exec_mod.compute_trade_parameters


# ── لایه ۰: شاخص‌ها ──────────────────────────
def add_indicators(df):
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("datetime").reset_index(drop=True)
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"]  - df["close"].shift(1)).abs()
    df["ATR14"] = pd.concat([hl, hc, lc], axis=1).max(axis=1) \
                    .ewm(span=14, min_periods=14, adjust=False).mean()
    df["atr"]           = df["ATR14"]
    df["avg_volume_20"] = df["volume"].rolling(20, min_periods=1).mean()
    return df.dropna(subset=["ATR14"]).reset_index(drop=True)


# ── لایه ۱: Swing (vectorized) ───────────────
def detect_swings_vectorized(df, window=5):
    df = df.copy()
    h, lo = df["high"], df["low"]
    lmh = h.rolling(window, min_periods=window).max().shift(1)
    lml = lo.rolling(window, min_periods=window).min().shift(1)
    rmh = h.shift(-1).combine(h.shift(-2), max)
    rml = lo.shift(-1).combine(lo.shift(-2), min)
    avg_atr   = df["atr"].mean()
    dyn       = (0.8 + 0.5 * df["atr"] / avg_atr).fillna(1.0)
    atr_safe  = df["atr"].replace(0, np.nan)
    df["swing_high"] = np.where((h >= lmh) & (h >= rmh) &
                                ((h - lml) / atr_safe >= dyn), h, 0.0)
    df["swing_low"]  = np.where((lo <= lml) & (lo <= rml) &
                                ((lmh - lo) / atr_safe >= dyn), lo, 0.0)
    print(f"   SH: {(df['swing_high']>0).sum():,}  SL: {(df['swing_low']>0).sum():,}")
    return df


# ── لایه ۲: Sweep (vectorized) ───────────────
def detect_sweeps_vectorized(df, lookback=20):
    """
    جاروب برداری: کندلی که از آخرین سوئینگ عبور کرده ولی بسته نشده بالاتر/پایین‌تر.
    """
    df = df.copy()
    df["sweep_score"] = 0.0
    df["sweep_type"]  = "none"

    # آخرین سطح سوئینگ در پنجره rolling
    sh = df["swing_high"].replace(0, np.nan)
    sl = df["swing_low"].replace(0, np.nan)
    last_sh = sh.rolling(lookback, min_periods=1).max()
    last_sl = sl.rolling(lookback, min_periods=1).min()

    atr_safe = df["atr"].replace(0, np.nan)

    # bearish sweep: high از سطح عبور کرده ولی close پایین‌تر بسته شده
    bear_mask = (df["high"] > last_sh) & (df["close"] < last_sh) & last_sh.notna()
    pen_bear  = ((df["high"] - last_sh) / atr_safe).clip(0, 1)
    wick_bear = ((df["high"] - df["close"]) / (df["high"] - df["low"] + 1e-10)).clip(0, 1)
    df.loc[bear_mask, "sweep_score"] = (pen_bear[bear_mask] * 0.5 + wick_bear[bear_mask] * 0.5).round(3)
    df.loc[bear_mask, "sweep_type"]  = "bearish"

    # bullish sweep: low از سطح عبور کرده ولی close بالاتر بسته شده
    bull_mask = (df["low"] < last_sl) & (df["close"] > last_sl) & last_sl.notna()
    pen_bull  = ((last_sl - df["low"]) / atr_safe).clip(0, 1)
    wick_bull = ((df["close"] - df["low"]) / (df["high"] - df["low"] + 1e-10)).clip(0, 1)
    df.loc[bull_mask, "sweep_score"] = (pen_bull[bull_mask] * 0.5 + wick_bull[bull_mask] * 0.5).round(3)
    df.loc[bull_mask, "sweep_type"]  = "bullish"

    n = (df["sweep_score"] > 0).sum()
    print(f"   سوئیپ: {n:,}  (Bear: {bear_mask.sum():,}  Bull: {bull_mask.sum():,})")
    return df


# ─────────────────────────────────────────────
MARKETS = {
    "abshodeNaghdi": "abshodeNaghdi-15",
    "haratFardayi":  "haratFardayi-15",
    "XAU_USD":       "XAU_USD-15",
}
DATA_DIR   = BASE / "data_clean"
OUTPUT_DIR = BASE / "output_fixed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run():
    summary = []

    for market, tf in MARKETS.items():
        print(f"\n{'='*55}")
        print(f"  بازار: {market}  |  تایم‌فریم: {tf}")
        print(f"{'='*55}")

        fp = DATA_DIR / f"{tf}.csv"
        if not fp.exists():
            print(f"⚠️  فایل یافت نشد: {fp}")
            continue

        df = pd.read_csv(fp)
        print(f"✅ بارگذاری: {len(df):,} کندل")

        df = add_indicators(df)
        print(f"✅ شاخص‌ها  |  معتبر: {len(df):,}")

        df = detect_swings_vectorized(df)
        print("✅ Swing")

        df = detect_sweeps_vectorized(df)
        print("✅ Sweep")

        try:
            df = detect_displacement(df)
            print(f"✅ Displacement  |  قوی: {(df['displacement_score']>0.5).sum():,}")
        except Exception as e:
            print(f"⚠️  Displacement: {e}")
            for c in ["displacement_score","impulse_score","fvg"]:
                if c not in df.columns: df[c] = 0.0

        try:
            df = score_order_blocks(df)
            print(f"✅ Order Block  |  OB: {df['is_ob'].sum():,}")
        except Exception as e:
            print(f"⚠️  OB: {e}")
            df["ob_score"] = 0.0; df["is_ob"] = False

        try:
            df = score_breakers_vectorized(df)
            print(f"✅ Breaker  |  موارد: {df['is_breaker'].sum():,}")
        except Exception as e:
            print(f"⚠️  Breaker: {e}")
            df["breaker_score"] = 0.0; df["is_breaker"] = False

        try:
            df = compute_setup_score(df)
            print(f"✅ Setup Score  |  معتبر(≥50): {(df['setup_score']>=50).sum():,}")
        except Exception as e:
            print(f"⚠️  Setup: {e}")
            df["setup_score"] = 0.0

        try:
            df = apply_state_machine(df)
            print(f"✅ State Machine  |  سیگنال: {df['entry_signal'].abs().sum():,}")
        except Exception as e:
            print(f"⚠️  State Machine: {e}")
            df["market_state"] = 0; df["entry_signal"] = 0; df["state_change"] = ""

        out = OUTPUT_DIR / f"processed_{tf}.csv"
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"💾 {out.name}")

        try:
            trades = compute_trade_parameters(df, risk_percent=1.0,
                         account_balance=10_000, atr_sl_mult=1.5, rr_ratio=1.5)
            if trades.empty:
                print("   سیگنال اجرایی: ۰")
                summary.append(dict(market=market, tf=tf, candles=len(df), signals=0, long=0, short=0))
            else:
                trades.to_csv(OUTPUT_DIR / f"execution_{tf}.csv", index=False, encoding="utf-8-sig")
                nl = (trades["direction"]=="LONG").sum()
                ns = (trades["direction"]=="SHORT").sum()
                print(f"📊 معاملات: {len(trades)}  L:{nl}  S:{ns}")
                summary.append(dict(market=market, tf=tf, candles=len(df),
                                     signals=len(trades), long=nl, short=ns))
        except Exception as e:
            print(f"⚠️  Execution: {e}")
            summary.append(dict(market=market, tf=tf, candles=len(df), signals=0, long=0, short=0))

    print(f"\n{'='*55}")
    print("  خلاصه نهایی")
    print(f"{'='*55}")
    for r in summary:
        print(f"  {r['market']:20s}  کندل:{r['candles']:>6,}  سیگنال:{r['signals']:>4}  L:{r['long']}  S:{r['short']}")
    print(f"\n✅ خروجی: {OUTPUT_DIR}")


if __name__ == "__main__":
    run()
