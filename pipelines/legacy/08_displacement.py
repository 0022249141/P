import pandas as pd
import numpy as np

def detect_displacement(df, atr_col='atr', vol_col='volume',
                        body_ratio_weight=0.35, range_to_atr_weight=0.35,
                        volume_weight=0.30, min_score=0.5):
    """
    محاسبه displacement_score برای هر کندل.
    displacement = قدرت جابجایی + عدم تعادل (FVG)
    """
    df = df.copy()
    df['impulse_score'] = 0.0
    df['displacement_score'] = 0.0
    df['fvg'] = 0

    # میانگین حجم غلتان
    avg_vol = df[vol_col].rolling(window=20, min_periods=1).mean()

    for idx in range(len(df)):
        row = df.iloc[idx]
        atr = row[atr_col]
        if atr == 0:
            continue

        # Impulse Score
        body = abs(row['close'] - row['open'])
        rng = row['high'] - row['low']
        body_ratio = body / rng if rng > 0 else 0
        range_to_atr = rng / atr
        vol_ratio = row[vol_col] / avg_vol.iloc[idx] if avg_vol.iloc[idx] > 0 else 1.0

        impulse = (body_ratio * body_ratio_weight +
                   min(1.0, range_to_atr) * range_to_atr_weight +
                   min(1.0, vol_ratio) * volume_weight)
        df.at[idx, 'impulse_score'] = round(impulse, 4)

        # تشخیص FVG (الزاماً نیاز به سه کندل متوالی دارد)
        fvg_detected = 0
        if idx >= 2:
            prev2 = df.iloc[idx-2]
            prev1 = df.iloc[idx-1]
            # FVG صعودی: low کندل فعلی > high دو کندل قبل
            if row['low'] > prev2['high']:
                gap = row['low'] - prev2['high']
                if gap > 0.3 * atr:
                    fvg_detected = 1
            # FVG نزولی: high کندل فعلی < low دو کندل قبل
            elif row['high'] < prev2['low']:
                gap = prev2['low'] - row['high']
                if gap > 0.3 * atr:
                    fvg_detected = -1

        df.at[idx, 'fvg'] = fvg_detected

        # Displacement Score = Impulse * FVG تأییدی
        if fvg_detected != 0:
            df.at[idx, 'displacement_score'] = round(impulse, 4)
        else:
            df.at[idx, 'displacement_score'] = round(impulse * 0.3, 4)

    return df

if __name__ == "__main__":
    # تست روی خروجی Sweep (که شامل ستون‌های اصلی + sweep_score است)
    INPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\sweep_XAU_USD-15_v2.csv"
    OUTPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\disp_XAU_USD-15.csv"

    df_in = pd.read_csv(INPUT)
    df_out = detect_displacement(df_in)
    df_out.to_csv(OUTPUT, index=False)

    high_disp = len(df_out[df_out['displacement_score'] >= 0.6])
    fvg_count = len(df_out[df_out['fvg'] != 0])
    print(f"✅ FVG detected: {fvg_count} | Displacement بالا: {high_disp}")
    print(f"📁 خروجی: {OUTPUT}")
