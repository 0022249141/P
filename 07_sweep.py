import pandas as pd
import numpy as np

def identify_liquidity_levels(df, atr_col='atr', swing_high_col='swing_high', swing_low_col='swing_low',
                              cluster_atr=0.5, min_strength=1):
    """
    سطوح نقدینگی را از swing_high/swing_low موجود در دیتافریم استخراج و خوشه‌بندی می‌کند.
    """
    highs = df[df[swing_high_col] > 0][['datetime', 'high', swing_high_col, atr_col]].copy()
    lows  = df[df[swing_low_col] > 0][['datetime', 'low', swing_low_col, atr_col]].copy()

    liq_highs = pd.DataFrame()
    liq_lows  = pd.DataFrame()

    # خوشه‌بندی highs
    if not highs.empty:
        highs = highs.sort_values('high')
        clusters = []
        current = [highs.iloc[0]]
        for i in range(1, len(highs)):
            row = highs.iloc[i]
            if row['high'] - current[-1]['high'] <= cluster_atr * row[atr_col]:
                current.append(row)
            else:
                clusters.append(current)
                current = [row]
        clusters.append(current)
        liq_highs = pd.DataFrame([{
            'level': np.mean([r['high'] for r in cl]),
            'weight': len(cl),
            'atr': np.mean([r[atr_col] for r in cl])
        } for cl in clusters if len(cl) >= min_strength])

    # خوشه‌بندی lows
    if not lows.empty:
        lows = lows.sort_values('low')
        clusters = []
        current = [lows.iloc[0]]
        for i in range(1, len(lows)):
            row = lows.iloc[i]
            if row['low'] - current[-1]['low'] <= cluster_atr * row[atr_col]:
                current.append(row)
            else:
                clusters.append(current)
                current = [row]
        clusters.append(current)
        liq_lows = pd.DataFrame([{
            'level': np.mean([r['low'] for r in cl]),
            'weight': len(cl),
            'atr': np.mean([r[atr_col] for r in cl])
        } for cl in clusters if len(cl) >= min_strength])

    return liq_highs, liq_lows

def rolling_percentile(series, window=50, percentile=80):
    """محاسبه پرسنتیل غلتان حجم."""
    return series.rolling(window=window, min_periods=1).apply(
        lambda x: np.percentile(x, percentile), raw=False
    )

def detect_sweeps(df, atr_col='atr', vol_col='volume',
                  penetration_max_atr=0.5, rejection_wick_min=0.6,
                  close_relocation_atr=0.2, vol_percentile=80,
                  cluster_atr=0.5, min_swing_strength=1):
    """
    تشخیص سوئیپ‌های تطبیقی و افزودن ستون‌های sweep_score و sweep_type به دیتافریم.
    """
    df = df.copy()
    df['sweep_score'] = 0.0
    df['sweep_type'] = 'none'

    # اطمینان از وجود ستون‌های ضروری
    if atr_col not in df.columns:
        raise ValueError(f"ستون {atr_col} در دیتافریم نیست.")

    liq_highs, liq_lows = identify_liquidity_levels(df, atr_col=atr_col,
                                                    cluster_atr=cluster_atr,
                                                    min_strength=min_swing_strength)
    if liq_highs.empty and liq_lows.empty:
        return df

    vol_thresh = rolling_percentile(df[vol_col], window=50, percentile=vol_percentile)

    for idx, row in df.iterrows():
        atr = row[atr_col]
        if atr == 0:
            continue

        best_score = 0.0
        best_type = 'none'

        # Sweep نزولی (خرید) → نفوذ به پایین سطح نقدینگی فروش
        if not liq_lows.empty:
            for _, lvl in liq_lows.iterrows():
                level = lvl['level']
                if row['low'] < level < row['high']:
                    depth = (row['high'] - level) / atr
                    if depth > penetration_max_atr:
                        continue
                    lower_wick = row['close'] - row['low']
                    body_range = row['high'] - row['low']
                    rejection = lower_wick / body_range if body_range > 0 else 0
                    if rejection < rejection_wick_min:
                        continue
                    if abs(row['close'] - level) > close_relocation_atr * atr:
                        continue
                    if row[vol_col] < vol_thresh.loc[idx]:
                        continue
                    score = min(1.0, rejection) * 0.4 + min(1.0, depth/penetration_max_atr) * 0.3 + min(1.0, row[vol_col]/(vol_thresh.loc[idx]+0.01)) * 0.3
                    if score > best_score:
                        best_score = score
                        best_type = 'bullish'

        # Sweep صعودی (فروش) → نفوذ به بالای سطح نقدینگی خرید
        if not liq_highs.empty:
            for _, lvl in liq_highs.iterrows():
                level = lvl['level']
                if row['low'] < level < row['high']:
                    depth = (level - row['low']) / atr
                    if depth > penetration_max_atr:
                        continue
                    upper_wick = row['high'] - row['close']
                    body_range = row['high'] - row['low']
                    rejection = upper_wick / body_range if body_range > 0 else 0
                    if rejection < rejection_wick_min:
                        continue
                    if abs(row['close'] - level) > close_relocation_atr * atr:
                        continue
                    if row[vol_col] < vol_thresh.loc[idx]:
                        continue
                    score = min(1.0, rejection) * 0.4 + min(1.0, depth/penetration_max_atr) * 0.3 + min(1.0, row[vol_col]/(vol_thresh.loc[idx]+0.01)) * 0.3
                    if score > best_score:
                        best_score = score
                        best_type = 'bearish'

        df.at[idx, 'sweep_score'] = round(best_score, 4)
        df.at[idx, 'sweep_type'] = best_type

    return df

if __name__ == "__main__":
    # تست سریع روی فایل Stage2 طلا ۱۵ دقیقه
    INPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\struct_processed_XAU_USD-15.csv"
    OUTPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\sweep_XAU_USD-15_v2.csv"

    df_in = pd.read_csv(INPUT)
    df_out = detect_sweeps(df_in)
    df_out.to_csv(OUTPUT, index=False)
    bulls = len(df_out[df_out['sweep_type']=='bullish'])
    bears = len(df_out[df_out['sweep_type']=='bearish'])
    print(f"✅ Sweep صعودی: {bulls} | Sweep نزولی: {bears}")
    print(f"📁 خروجی: {OUTPUT}")
