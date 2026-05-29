import pandas as pd
import numpy as np

def compute_trade_parameters(df, risk_percent=1.0, account_balance=10000,
                             atr_sl_mult=1.5, rr_ratio=1.5):
    """
    برای هر سیگنال ورود، حد ضرر تطبیقی، حد سود و حجم معامله را محاسبه می‌کند.
    پارامترها:
    - risk_percent: درصد ریسک از بالانس (مثلاً ۱٪)
    - account_balance: بالانس حساب به دلار
    - atr_sl_mult: ضریب ATR برای حد ضرر
    - rr_ratio: نسبت ریسک به ریوارد
    """
    trades = []
    for idx, row in df.iterrows():
        if row['entry_signal'] == 0:
            continue

        # برای ورود واقعی، از کندل بعدی استفاده می‌کنیم (Open کندل بعد)
        next_idx = idx + 1
        if next_idx >= len(df):
            continue
        next_row = df.iloc[next_idx]
        entry_price = next_row['open']  # ورود در Open کندل بعد از سیگنال
        atr = row['atr']  # ATR کندل سیگنال (می‌توان میانگین ATR سه کندل اخیر را گرفت)
        if atr == 0:
            continue

        direction = row['entry_signal']  # 1 = long, -1 = short

        # حد ضرر مبتنی بر ATR
        sl_distance = atr_sl_mult * atr
        if direction == 1:  # خرید
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + sl_distance * rr_ratio
        else:  # فروش
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - sl_distance * rr_ratio

        # محاسبه حجم معامله (XAU/USD: 1 lot = 100 oz)
        risk_amount = account_balance * (risk_percent / 100)
        # در معاملات طلا، حرکت یک دلاری در قیمت معادل یک دلار سود/زیان در هر اونس است
        position_size_oz = risk_amount / sl_distance  # تعداد اونس
        # تبدیل به لات استاندارد (هر لات = 100 اونس)
        lots = round(position_size_oz / 100, 2)
        if lots < 0.01:
            lots = 0.01  # حداقل لات مجاز

        trades.append({
            'signal_time': row['datetime'],
            'entry_time': next_row['datetime'],
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'atr': round(atr, 2),
            'lots': lots,
            'risk_amount': round(risk_amount, 2),
            'risk_percent': risk_percent
        })

    return pd.DataFrame(trades)

if __name__ == "__main__":
    INPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\final_signals_XAU_USD-15.csv"
    OUTPUT = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\execution_plan_XAU_USD-15.csv"

    df = pd.read_csv(INPUT)
    trades = compute_trade_parameters(df, risk_percent=1.0, account_balance=10000,
                                      atr_sl_mult=1.5, rr_ratio=1.5)

    trades.to_csv(OUTPUT, index=False)

    print(f"✅ تعداد معاملات: {len(trades)}")
    print(f"   خرید (Long):  {len(trades[trades['direction']=='LONG'])}")
    print(f"   فروش (Short): {len(trades[trades['direction']=='SHORT'])}")
    print(f"📁 خروجی: {OUTPUT}")
