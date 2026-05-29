import pandas as pd
import numpy as np

def apply_state_machine(df, setup_col='setup_score', sweep_col='sweep_score',
                        disp_col='displacement_score', ob_col='is_ob',
                        breaker_col='is_breaker', min_setup=50):
    """
    مدل کردن توالی بازار:
    State 0: Idle (منتظر سوئیپ)
    State 1: Sweep confirmed → منتظر Displacement
    State 2: Displacement → منتظر Retrace (OB یا Breaker)
    State 3: Setup ready (ورود)
    State 4: In Trade (مدیریت)
    """
    df = df.copy()
    df['market_state'] = 0
    df['entry_signal'] = 0  # 1 = long, -1 = short
    df['state_change'] = ''

    current_state = 0
    last_sweep_type = None

    for idx in range(len(df)):
        row = df.iloc[idx]
        sweep_score = row[sweep_col]
        disp_score = row[disp_col]
        setup_score = row[setup_col]
        is_ob = row[ob_col]
        is_breaker = row[breaker_col]
        sweep_type = row.get('sweep_type', 'none')

        # منطق انتقال حالت
        if current_state == 0:  # Idle
            if sweep_score > 0.5:
                current_state = 1
                last_sweep_type = sweep_type
                df.at[idx, 'state_change'] = f'IDLE→SWEEP({sweep_type})'

        elif current_state == 1:  # Sweep confirmed
            if disp_score > 0.5:
                current_state = 2
                df.at[idx, 'state_change'] = 'SWEEP→DISPLACEMENT'
            elif sweep_score > 0.5:  # سوئیپ جدید جایگزین
                last_sweep_type = sweep_type
                df.at[idx, 'state_change'] = f'SWEEP_RENEW({sweep_type})'
            # اگر ۵ کندل بگذرد و جابجایی نیاید → برگشت به Idle
            elif idx > 0 and df.at[idx-1, 'market_state'] == 1:
                # شمارش کندل‌های در انتظار (پیاده‌سازی ساده)
                if idx >= 2 and df.at[idx-2, 'market_state'] == 1:
                    current_state = 0
                    df.at[idx, 'state_change'] = 'TIMEOUT→IDLE'

        elif current_state == 2:  # Displacement done, waiting retrace
            if is_ob or is_breaker:
                if setup_score >= min_setup:
                    current_state = 3
                    df.at[idx, 'state_change'] = 'DISPLACEMENT→SETUP'
                    # تعیین جهت ورود بر اساس نوع سوئیپ اولیه
                    if last_sweep_type == 'bullish':  # سوئیپ فروش → خرید
                        df.at[idx, 'entry_signal'] = 1
                    elif last_sweep_type == 'bearish':  # سوئیپ خرید → فروش
                        df.at[idx, 'entry_signal'] = -1
                    current_state = 0  # بعد از سیگنال، برای ستاپ بعدی آماده شو
                    last_sweep_type = None
            elif disp_score < 0.3:  # قدرت از دست رفته
                current_state = 0
                df.at[idx, 'state_change'] = 'WEAK_DISP→IDLE'

        df.at[idx, 'market_state'] = current_state

    return df

if __name__ == "__main__":
    INPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\zone_XAU_USD-15.csv"
    OUTPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\final_signals_XAU_USD-15.csv"

    df = pd.read_csv(INPUT)
    df = apply_state_machine(df)
    df.to_csv(OUTPUT, index=False)

    longs = len(df[df['entry_signal'] == 1])
    shorts = len(df[df['entry_signal'] == -1])
    print(f"✅ Long signals: {longs} | Short signals: {shorts}")
    print(f"📁 خروجی: {OUTPUT}")
