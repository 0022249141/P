import pandas as pd
import numpy as np

def score_order_blocks(df, sweep_col='sweep_score', disp_col='displacement_score',
                       atr_col='atr', body_ratio_min=0.4, lookback=3):
    df = df.copy()
    df['ob_score'] = 0.0
    df['is_ob'] = False

    # محاسبه برداری body_ratio
    body = (df['close'] - df['open']).abs()
    rng = df['high'] - df['low']
    body_ratio = body / rng.replace(0, np.nan)
    
    # کندل‌های کاندید OB
    mask = (body_ratio >= body_ratio_min) & ((df[disp_col] >= 0.5) | (df.get('impulse_score', 0) >= 0.5))
    
    # محاسبه امتیاز پایه برای کاندیدها (برداری)
    df.loc[mask, 'ob_score'] = (body_ratio[mask] * 30 + 
                                 df.loc[mask, disp_col].clip(upper=1) * 30)
    
    # اضافه کردن امتیاز سوئیپ از lookback (با rolling max)
    sweep_series = df[sweep_col].where(df[sweep_col] > 0.5, 0)
    sweep_max = sweep_series.rolling(window=lookback+1, min_periods=1).max().shift(1)
    df['ob_score'] += sweep_max * 40
    df['ob_score'] = df['ob_score'].round(1)
    df['is_ob'] = df['ob_score'] >= 50
    return df

def score_breakers_vectorized(df, ob_col='is_ob', atr_col='atr', disp_col='displacement_score'):
    """
    نسخه برداری‌شده Breaker: برای هر کندل، آخرین OB قبلی را که به آن نزدیک شده بررسی می‌کند.
    """
    df = df.copy()
    df['breaker_score'] = 0.0
    df['is_breaker'] = False

    # لیست زمان‌های OB
    ob_times = df.index[df[ob_col]].tolist()
    if not ob_times:
        return df

    # برای هر OB، یک سطح (close آن) و زمان را نگه می‌داریم
    ob_levels = df.loc[ob_times, 'close'].values
    ob_idx = df.index.get_indexer(ob_times)  # موقعیت عددی

    # برای هر کندل، آخرین OB قبل از آن را پیدا می‌کنیم (با استفاده از searchsorted)
    # تبدیل ایندکس به آرایه عددی
    idx_arr = np.arange(len(df))
    # برای هر کندل، ایندکس آخرین OB قبل از آن
    last_ob_idx = np.searchsorted(ob_idx, idx_arr, side='right') - 1

    # فقط کندل‌هایی که حداقل یک OB قبل دارند
    valid = last_ob_idx >= 0
    if not valid.any():
        return df

    # سطح OB متناظر
    levels = ob_levels[last_ob_idx[valid]]
    # ATR برای کندل‌های معتبر
    atr_vals = df[atr_col].iloc[valid].values
    # فاصله قیمت تا سطح OB: min(|high - level|, |low - level|)
    high_vals = df['high'].iloc[valid].values
    low_vals = df['low'].iloc[valid].values
    distance = np.minimum(np.abs(high_vals - levels), np.abs(low_vals - levels))
    # شرط نزدیکی
    close_mask = distance < 0.5 * atr_vals

    # ترکیب نهایی
    final_mask = valid.copy()
    final_mask[valid] = close_mask

    # برای کندل‌های نزدیک، امتیاز Breaker
    if final_mask.any():
        # امتیاز: (1 - distance/(0.5*atr)) * 70 + displacement*30
        d_norm = 1 - distance[close_mask] / (0.5 * atr_vals[close_mask])
        disp_vals = df[disp_col].iloc[final_mask].values
        scores = d_norm * 70 + disp_vals * 30
        df.loc[final_mask, 'breaker_score'] = np.round(scores, 1)
        df.loc[final_mask, 'is_breaker'] = scores > 60

    return df

def compute_setup_score(df, sweep_col='sweep_score', disp_col='displacement_score',
                        ob_col='ob_score', breaker_col='breaker_score'):
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
    df = score_breakers_vectorized(df)
    df = compute_setup_score(df)

    df.to_csv(OUTPUT, index=False)

    obs = df['is_ob'].sum()
    breakers = df['is_breaker'].sum()
    setups = len(df[df['setup_score'] > 50])
    print(f"✅ OB: {obs} | Breaker: {breakers} | Setupهای بالای ۵۰: {setups}")
    print(f"📁 خروجی: {OUTPUT}")
