import sys
import os
import pandas as pd

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

from market_engine import MarketDataEngine
from structure_engine import StructuralEngine
from liquidity_engine import LiquidityEngine
from displacement_engine import DisplacementEngine
from zone_engine import ZoneEngine

# بارگذاری داده
file_path = os.path.join(project_root, 'data', 'XAU_USD-15.csv')
engine = MarketDataEngine.from_custom_csv(file_path)

# محاسبه ساختار (نیاز برای تشخیص سوئینگ‌ها)
struct = StructuralEngine(engine)
struct.detect_swings(window=5)

# راه‌اندازی موتورهای تحلیلی
liq = LiquidityEngine(engine)
disp = DisplacementEngine(engine)
zone = ZoneEngine(engine, disp)

# اجرای محاسبات
liq.detect_sweeps()
disp.score_all()
zone.detect_fvg()
zone.detect_ob()

# نمایش نتایج برای ۱۰ کندل آخر
print("\n" + "="*100)
print("تحلیل نقدینگی پیشرفته — ۱۰ کندل آخر")
print("="*100)
print(f"{'Timestamp':<20} {'Regime':<8} {'Sweep':<7} {'Disp':<7} {'FVG':<7} {'OB':<7}")
print("-"*100)

start_idx = max(0, len(engine.df) - 10)
for idx in range(start_idx, len(engine.df)):
    ts = str(engine.df['timestamp'].iloc[idx])[:19]
    reg = engine.get_regime(idx)
    sw = liq.get_sweep(idx)
    di = disp.get_score(idx)
    fv = zone.get_fvg_score(idx)
    ob = zone.get_ob_score(idx)
    
    print(f"{ts:<20} {reg:<8} {sw:<7.2f} {di:<7.2f} {fv:<7.2f} {ob:<7.2f}")

print("-"*100)
