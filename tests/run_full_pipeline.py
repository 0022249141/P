# run_full_pipeline.py (نسخه نهایی)
# مسیر: tests/run_full_pipeline.py
# همه ماژول‌ها: FVG, Order Block, Dealing Range, Regime, پارامترهای کالیبره‌شده

import sys
import os
import pandas as pd
import json

# =========================================================
# ۱. تنظیم مسیرها
# =========================================================
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))   # برای import از src/
sys.path.insert(0, project_root)                       # برای import از ریشه (fvg.py, order_blocks.py, ...)

# =========================================================
# ۲. وارد کردن کتابخانه‌های پروژه
# =========================================================
from market_engine import MarketDataEngine
from structure_engine import StructuralEngine
from liquidity_engine import LiquidityEngine
from displacement_engine import DisplacementEngine
from zone_engine import ZoneEngine
from volume_profile import VolumeProfileEngine
from iceberg_detector import IcebergDetector
from scoring_engine import ScoringEngine
from execution_logic import ExecutionLogic
from mtf_analyzer import MTFAnalyzer
from signal_explainer import SignalExplainer
from market_params import MARKETS

# ماژول‌های جدید (در ریشه)
from fvg import detect_fvg
from order_blocks import detect_order_blocks
from dealing_range import detect_dealing_range
from regime import classify_regime

# =========================================================
# ۳. انتخاب بازار
# =========================================================
MARKET_NAME = "XAUUSD"          # می‌توانید به "AbshodeNaghdi" یا "HaratUSD" تغییر دهید
CSV_FILE   = "XAU_USD-15.csv"   # فایل متناسب با بازار

# =========================================================
# ۴. بارگذاری وزن‌های بهینه (اگر وجود داشته باشد)
# =========================================================
weights_path = os.path.join(project_root, 'data', 'best_weights.json')
optimized_weights = None
if os.path.exists(weights_path):
    with open(weights_path) as f:
        optimized_weights = json.load(f)
    print(f"⚖️ وزن‌های بهینه بارگذاری شد: {optimized_weights}")
else:
    print("⚖️ از وزن‌های پیش‌فرض استفاده می‌شود.")

# =========================================================
# ۵. بارگذاری و آماده‌سازی داده
# =========================================================
data_path = os.path.join(project_root, 'data', CSV_FILE)
print(f"📂 بارگذاری داده از {data_path} ...")
engine = MarketDataEngine.from_custom_csv(data_path)
print(f"   تعداد کندل: {len(engine.df)}")

# =========================================================
# ۶. اعمال FVG
# =========================================================
print("🔍 تشخیص FVG...")
engine.df = detect_fvg(engine.df, market_name=MARKET_NAME)
bull_fvg = engine.df['fvg_bull'].sum()
bear_fvg = engine.df['fvg_bear'].sum()
print(f"   FVG صعودی: {bull_fvg} | FVG نزولی: {bear_fvg}")

# =========================================================
# ۷. تشخیص Order Block
# =========================================================
print("🧊 تشخیص Order Block...")
engine.df = detect_order_blocks(engine.df, market_name=MARKET_NAME)
ob_bull = engine.df['ob_bull'].notna().sum()
ob_bear = engine.df['ob_bear'].notna().sum()
print(f"   OB صعودی: {ob_bull} | OB نزولی: {ob_bear}")

# =========================================================
# ۸. محاسبه Dealing Range
# =========================================================
print("📊 محاسبه محدوده معاملاتی (Dealing Range)...")
engine.df = detect_dealing_range(engine.df, market_name=MARKET_NAME)
last_pos = engine.df['position_pct'].iloc[-1]
print(f"   موقعیت فعلی در محدوده: {last_pos:.1f}٪")

# =========================================================
# ۹. طبقه‌بندی رژیم بازار
# =========================================================
print("🧠 طبقه‌بندی رژیم بازار...")
engine.df = classify_regime(engine.df, market_name=MARKET_NAME)
regime_counts = engine.df['regime'].value_counts().to_dict()
print(f"   توزیع رژیم: {regime_counts}")

# =========================================================
# ۱۰. محاسبه ساختار بازار (بدون نشت آینده)
# =========================================================
print("🏗️  محاسبه ساختار بازار...")
struct = StructuralEngine(engine, market_name=MARKET_NAME)
struct.detect_swings(window=5)
print("   ✅ Swingها شناسایی شدند.")

# =========================================================
# ۱۱. راه‌اندازی موتورهای تحلیل
# =========================================================
print("⚙️  راه‌اندازی موتورهای تحلیل...")
liq = LiquidityEngine(engine, market_name=MARKET_NAME)
disp = DisplacementEngine(engine)
zone = ZoneEngine(engine, disp)
vp = VolumeProfileEngine(engine, lookback_candles=96)
ice = IcebergDetector(engine)

# =========================================================
# ۱۲. اجرای تحلیل‌ها
# =========================================================
print("🚀 اجرای تحلیل‌ها...")
liq.detect_sweeps()
disp.score_all()
zone.detect_fvg()
zone.detect_ob()
print("   ✅ تحلیل‌ها کامل شد.")

# =========================================================
# ۱۳. تحلیل چندتایم‌فریمی (MTF)
# =========================================================
print("🌐 تحلیل چندتایم‌فریمی...")
h1_csv = os.path.join(project_root, 'data', 'XAU_USD-60.csv')
dly_csv = os.path.join(project_root, 'data', 'XAU_USD-1D.csv')
mtf = MTFAnalyzer(h1_csv, None, dly_csv)
htf_bias = mtf.get_htf_bias(engine.df['timestamp'].iloc[-1]) if mtf.daily else 0.5
print(f"   سوگیری HTF: {htf_bias:.2f}")

# =========================================================
# ۱۴. امتیازدهی و تولید سیگنال
# =========================================================
print("📊 امتیازدهی و تولید سیگنال...")
scorer = ScoringEngine(liq, disp, zone, vp, ice, htf_bias=htf_bias, weights=optimized_weights)
executor = ExecutionLogic(scorer, engine, struct)
signals = executor.generate_signals(min_setup_score=70)

print(f"\n✅ تعداد سیگنال‌های {MARKET_NAME}: {len(signals)}")

# =========================================================
# ۱۵. ذخیرهٔ سیگنال‌ها
# =========================================================
signals_csv = os.path.join(project_root, 'data', 'generated_signals.csv')
signals.to_csv(signals_csv, index=False)
print(f"💾 سیگنال‌ها در {signals_csv} ذخیره شدند.")

# =========================================================
# ۱۶. گزارش فارسی آخرین سیگنال
# =========================================================
if len(signals) > 0:
    explainer = SignalExplainer(scorer, mtf)
    last_signal = signals.iloc[-1]
    ts = last_signal['timestamp']
    idx = engine.df.index[engine.df['timestamp'] == ts][0]
    explanation = explainer.explain_signal(idx)
    print("\n" + "=" * 60)
    print("📋 گزارش فارسی آخرین سیگنال")
    print("=" * 60)
    print(explanation)
    print("=" * 60)
else:
    print("⚠️ هیچ سیگنالی با امتیاز بالای ۷۰ یافت نشد.")