import sys
import os

# پیدا کردن مسیر ریشه پروژه (پوشه P)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# اضافه کردن پوشه src به مسیر جستجوی ماژول‌ها
sys.path.insert(0, os.path.join(project_root, 'src'))

from market_engine import MarketDataEngine
from structure_engine import StructuralEngine

# مسیر فایل داده
file_path = os.path.join(project_root, 'data', 'XAU_USD-15.csv')

print(f"بارگذاری: {file_path}")
engine = MarketDataEngine.from_custom_csv(file_path)

print(f"تعداد کندل: {len(engine.df)}")
print(f"از {engine.df['timestamp'].iloc[0]} تا {engine.df['timestamp'].iloc[-1]}")

struct = StructuralEngine(engine)
struct.detect_swings(window=5)

print("\nآخرین ۵ کندل:")
for idx in range(max(0, len(engine.df)-5), len(engine.df)):
    ts = engine.df['timestamp'].iloc[idx]
    reg = engine.get_regime(idx)
    atr = engine.df['ATR14'].iloc[idx]
    sw_high = struct.df['swing_high'].iloc[idx]
    sw_low = struct.df['swing_low'].iloc[idx]
    print(f"{ts} | رژیم: {reg:8s} | ATR: {atr:,.2f} | SwingHigh: {sw_high if not pd.isna(sw_high) else '---'} | SwingLow: {sw_low if not pd.isna(sw_low) else '---'}")