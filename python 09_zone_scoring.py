import pandas as pd
import numpy as np

def score_order_blocks(df, sweep_col='sweep_score', disp_col='displacement_score',
                       atr_col='atr', body_ratio_min=0.4, lookback=3):
    """
    شناسایی و امتیازدهی به Order Block‌های بالقوه.
    یک OB کاندید کندلی است که:
    1. displacement_score بالا داشته باشد (>= 0.5) یا impulse قابل توجه
    2. بدنه‌اش نسبت به range حداقل body_ratio_min باشد
    3. در نزدیکی یک سوئیپ معتبر (sweep_score بالا) امتیاز بیشتری بگیرد
    خروجی: ob_score بین 0 تا 100 (فقط برای کندل‌هایی که کاندید OB هستند)
    """
    df = df.copy()
    df['ob_score'] = 0.0
    df['is_ob'] = False

    for idx in range(len(df)):
        row = df.iloc[idx]
        rng = row['high'] - row['low']
        if rng == 0:
            continue
        body = abs(row['close'] - row['open'])
        body_ratio = body / rng

        # شرط اولیه OB
        if body_ratio < body_ratio_min:
            continue
        if row[disp_col] < 0.5 and row['impulse_score'] < 0.5:
            continue

        # پایه امتیاز
        score = body_ratio * 30  # max 30
        score += min(1.0, row[disp_col]) * 30  # max 30

        # بررسی سوئیپ در lookback کندل قبلی
        sweep_bonus = 0
        for i in range(max(0, idx - lookback), idx):
            sweep_val = df.iloc[i][sweep_col]
            if sweep_val > 0.5:
                sweep_bonus = max(sweep_bonus, sweep_val)
        score += sweep_bonus * 40  # max 40 → total 100

        df.at[idx, 'ob_score'] = round(score, 1)
        if score >= 50:
            df.at[idx, 'is_ob'] = True

    return df

def score_breakers(df, ob_col='is_ob', atr_col='atr'):
    """
    Breaker = OB قبلی که قیمت به آن برگشته و آن را نقض کرده (شکست و برگشت).
    ساده‌ترین تشخیص: کندل جاری جایی که OB قبلی (is_ob=True) با برخورد قیمت همراه باشد.
    امتیاز Breaker تابعی از فاصله تا OB و قدرت displacement.
    """
    df = df.copy()
    df['breaker_score'] = 0.0
    df['is_breaker'] = False

    # موقعیت‌های OB
    ob_indices = df.index[df[ob_col]].tolist()

    for idx in range(len(df)):
        if idx < 1:
            continue
        row = df.iloc[idx]
        # بررسی کندل‌های OB قبلی
        for ob_idx in ob_indices:
            if ob_idx >= idx:  # فقط OBهای گذشته
                continue
            ob_row = df.iloc[ob_idx]
            ob_level = ob_row['close']  # معمولاً بسته‌شدن OB سطح کلیدی است
            atr = row[atr_col]
            if atr == 0:
                continue
            # فاصله قیمت فعلی تا سطح OB
            distance = min(abs(row['high'] - ob_level), abs(row['low'] - ob_level))
            if distance > 0.5 * atr:
                continue
            # نشانه برگشت: بسته‌شدن کندل در جهت مخالف
            if ob_row['close'] > ob_row['open']:  # OB خرید
                if row['close'] < row['open'] and row['low'] < ob_level:
                    score = (1 - distance / (0.5 * atr)) * 70 + row['displacement_score'] * 30
                    df.at[idx, 'breaker_score'] = max(df.at[idx, 'breaker_score'], round(score, 1))
                    if score > 60:
                        df.at[idx, 'is_breaker'] = True
            else:  # OB فروش
                if row['close'] > row['open'] and row['high'] > ob_level:
                    score = (1 - distance / (0.5 * atr)) * 70 + row['displacement_score'] * 30
                    df.at[idx, 'breaker_score'] = max(df.at[idx, 'breaker_score'], round(score, 1))
                    if score > 60:
                        df.at[idx, 'is_breaker'] = True
    return df

def compute_setup_score(df, sweep_col='sweep_score', disp_col='displacement_score',
                        ob_col='ob_score', breaker_col='breaker_score'):
    """
    یک امتیاز ترکیبی برای کیفیت ستاپ (setup_score).
    وزن‌دهی به‌صورت مساوی: سوئیپ (30%) + جابجایی (30%) + OB (20%) + Breaker (20%).
    """
    df = df.copy()
    df['setup_score'] = (df[sweep_col] * 0.3 + df[disp_col] * 0.3 +
                         df[ob_col] * 0.2 / 100.0 + df[breaker_col] * 0.2 / 100.0) * 100
    df['setup_score'] = df['setup_score'].round(1)
    return df

if __name__ == "__main__":
    INPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\disp_XAU_USD-15.csv"
    OUTPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\zone_XAU_USD-15.csv"

    df = pd.read_csv(INPUT)
    df = score_order_blocks(df)
    df = score_breakers(df)
    df = compute_setup_score(df)

    df.to_csv(OUTPUT, index=False)

    obs = df['is_ob'].sum()
    breakers = df['is_breaker'].sum()
    setups = len(df[df['setup_score'] > 50])
    print(f"✅ OB: {obs} | Breaker: {breakers} | Setupهای بالای ۵۰: {setups}")
    print(f"📁 خروجی: {OUTPUT}")
