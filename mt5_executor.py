import MetaTrader5 as mt5
import pandas as pd
import time

# اتصال به متاتریدر (باید متاتریدر ۵ باز باشد و لاگین کرده باشی)
if not mt5.initialize():
    print("❌ اتصال به متاتریدر ناموفق بود.")
    quit()

print("✅ اتصال به متاتریدر برقرار شد.")

# خواندن برنامه اجرایی (فایل CSV)
plan_file = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\execution_plan_XAU_USD-15.csv"
trades = pd.read_csv(plan_file)

# مشخصات نماد (XAUUSD در لایت‌فایننس)
symbol = "XAUUSD"
if not mt5.symbol_select(symbol, True):
    print(f"❌ نماد {symbol} در دسترس نیست.")
    mt5.shutdown()
    quit()

print(f"📊 نماد {symbol} آماده است.")

# ارسال سفارشات (توجه: این فقط یکبار اجرا می‌شود، سفارشات pending یا market ارسال می‌کند)
for i, trade in trades.iterrows():
    direction = trade['direction']
    entry_price = trade['entry_price']
    sl = trade['stop_loss']
    tp = trade['take_profit']
    lots = trade['lots']

    # تعیین نوع سفارش
    if direction == 'LONG':
        order_type = mt5.ORDER_TYPE_BUY_STOP  # سفارش معلق خرید
        price = entry_price
    else:
        order_type = mt5.ORDER_TYPE_SELL_STOP  # سفارش معلق فروش
        price = entry_price

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lots,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 10,
        "magic": 123456,
        "comment": f"AI_Setup_{i}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"⚠️ خطا در سفارش {i}: {result.comment}")
    else:
        print(f"✅ سفارش {i} ({direction}) با موفقیت ارسال شد. Ticket: {result.order}")

mt5.shutdown()
