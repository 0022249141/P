# live_data_server.py
# هر ۳۰ ثانیه یک‌بار فایل live_prices.json را بر اساس آخرین داده‌های CSV به‌روز می‌کند
import pandas as pd, json, time, os, random

XAU_PATH = os.path.join('data', 'XAU_USD-15.csv')
ABS_PATH = os.path.join('data', 'abshodeNaghdi-15.csv')

while True:
    try:
        # خواندن آخرین ردیف
        xau = pd.read_csv(XAU_PATH).iloc[-1]
        abs_df = pd.read_csv(ABS_PATH).iloc[-1]

        # شبیه‌سازی نوسانات زنده (۰.۱٪ تغییر)
        xau_price = xau['close'] * (1 + random.uniform(-0.001, 0.001))
        abs_price = abs_df['close'] * (1 + random.uniform(-0.001, 0.001))

        data = {
            'xauusd': {
                'price': round(xau_price, 2),
                'change_pct': round((xau_price - xau['close']) / xau['close'] * 100, 2),
                'high': xau['high'],
                'low': xau['low']
            },
            'abshode': {
                'price': round(abs_price, 2),
                'change_pct': round((abs_price - abs_df['close']) / abs_df['close'] * 100, 2),
                'high': abs_df['high'],
                'low': abs_df['low']
            }
        }

        with open('live_prices.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

        print(f'✅ به‌روزرسانی شد: XAU={xau_price:.2f}, ABS={abs_price:,.0f}')
    except Exception as e:
        print(f'⚠️ خطا: {e}')

    time.sleep(30)