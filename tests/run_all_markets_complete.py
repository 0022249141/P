# run_all_markets_complete.py — تحلیل همزمان سه بازار با انتقال بین‌بازاری
# مسیر: tests/run_all_markets_complete.py
# این فایل همه ماژول‌های پروژه را فراخوانی کرده و خروجی نهایی را تولید می‌کند.

import sys, os, pandas as pd, json

# 1. تنظیم مسیرها
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, project_root)

# 2. ایمپورت‌های اصلی
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

# 3. ایمپورت ماژول‌های تحلیلی (در ریشهٔ پروژه)
from fvg import detect_fvg
from order_blocks import detect_order_blocks
from dealing_range import detect_dealing_range
from regime import classify_regime
from cross_market import cross_market_analysis   # 11_cross_market.py

# 4. تنظیمات بازارها
markets_to_process = [
    {"name": "XAUUSD",        "csv": "XAU_USD-15.csv",       "h1": "XAU_USD-60.csv",       "daily": "XAU_USD-1D.csv"},
    {"name": "HaratUSD",      "csv": "haratFardayi-15.csv",  "h1": "haratFardayi-60.csv",  "daily": "haratFardayi-1D.csv"},
    {"name": "AbshodeNaghdi", "csv": "abshodeNaghdi-15.csv", "h1": "abshodeNaghdi-60.csv", "daily": "abshodeNaghdi-1D.csv"},
]

# 5. بارگذاری وزن‌های بهینه (اختیاری)
weights_path = os.path.join(project_root, 'data', 'best_weights.json')
optimized_weights = None
if os.path.exists(weights_path):
    with open(weights_path) as f:
        optimized_weights = json.load(f)
    print(f"⚖️ وزن‌های بهینه بارگذاری شد: {optimized_weights}\n")

# 6. پردازش هر بازار و ذخیره DataFrameها برای تحلیل بین‌بازاری
market_dfs = {}
market_engines = {}
market_signals = []

for mkt in markets_to_process:
    name = mkt["name"]
    print(f"{'='*60}")
    print(f"  تحلیل بازار: {name}")
    print(f"{'='*60}")

    # ۶.۱ بارگذاری داده
    engine = MarketDataEngine.from_custom_csv(os.path.join(project_root, 'data', mkt["csv"]))
    print(f"  📊 تعداد کندل: {len(engine.df)}")

    # ۶.۲ اعمال تحلیل‌های پایه
    engine.df = detect_fvg(engine.df, market_name=name)
    engine.df = detect_order_blocks(engine.df, market_name=name)
    engine.df = detect_dealing_range(engine.df, market_name=name)
    engine.df = classify_regime(engine.df, market_name=name)

    # ۶.۳ ساختار بازار
    struct = StructuralEngine(engine, market_name=name)
    struct.detect_swings(window=5)

    # ۶.۴ موتورهای تحلیلی
    liq = LiquidityEngine(engine, market_name=name)
    disp = DisplacementEngine(engine)
    zone = ZoneEngine(engine, disp)
    vp = VolumeProfileEngine(engine, lookback_candles=96)
    ice = IcebergDetector(engine)
    liq.detect_sweeps()
    disp.score_all()
    zone.detect_fvg()
    zone.detect_ob()

    # ۶.۵ تحلیل چندتایم‌فریمی
    mtf = MTFAnalyzer(
        os.path.join(project_root, 'data', mkt["h1"]),
        None,
        os.path.join(project_root, 'data', mkt["daily"])
    )
    htf_bias = mtf.get_htf_bias(engine.df['timestamp'].iloc[-1]) if mtf.daily else 0.5

    # ۶.۶ امتیازدهی و تولید سیگنال‌ها
    scorer = ScoringEngine(liq, disp, zone, vp, ice, htf_bias=htf_bias, weights=optimized_weights)
    executor = ExecutionLogic(scorer, engine, struct)
    signals = executor.generate_signals(min_setup_score=70)

    # ذخیره‌سازی برای تحلیل بین‌بازاری
    market_dfs[name] = engine.df.set_index('timestamp')[['close']]
    market_engines[name] = engine
    market_signals.append(signals.assign(market=name))

    print(f"  ✅ سیگنال‌های {name}: {len(signals)}")

# 7. تحلیل بین‌بازاری
print("\n" + "="*60)
print("  🌐 تحلیل انتقال بین‌بازاری")
print("="*60)
try:
    cross_df = cross_market_analysis(
        market_dfs["XAUUSD"],
        market_dfs["HaratUSD"],
        market_dfs["AbshodeNaghdi"]
    )
    last_align = cross_df['alignment_score'].iloc[-1]
    print(f"  امتیاز هم‌سویی نهایی: {last_align}/3")
    print(f"  رژیم انتقال: {cross_df['regime'].iloc[-1]}")
except Exception as e:
    print(f"  ⚠️ خطا در تحلیل بین‌بازاری: {e}")
    last_align = 0

# 8. تصمیم‌گیری نهایی بر اساس هم‌سویی
if last_align >= 2:
    print("\n✅ بازارها هم‌جهت هستند. سیگنال‌ها تأیید می‌شوند.")
    final_signals = pd.concat(market_signals, ignore_index=True)
    final_signals.to_csv(os.path.join(project_root, 'data', 'all_markets_signals.csv'), index=False)
    print(f"💾 مجموع سیگنال‌های معتبر: {len(final_signals)}")
else:
    print("\n⚠️ بازارها واگرا هستند (alignment_score < 2). سیگنال‌ها مسدود شدند.")
    pd.DataFrame().to_csv(os.path.join(project_root, 'data', 'all_markets_signals.csv'), index=False)
    print("💾 فایل سیگنال خالی ذخیره شد (واگرایی).")

# 9. گزارش فارسی آخرین سیگنال طلا (در صورت هم‌سویی)
if last_align >= 2 and len(market_signals[0]) > 0:
    print("\n📋 گزارش آخرین سیگنال طلا:")
    # ساخت موقت ScoringEngine برای توضیح
    explainer = SignalExplainer(
        ScoringEngine(
            LiquidityEngine(market_engines["XAUUSD"], market_name="XAUUSD"),
            DisplacementEngine(market_engines["XAUUSD"]),
            ZoneEngine(market_engines["XAUUSD"], DisplacementEngine(market_engines["XAUUSD"])),
            VolumeProfileEngine(market_engines["XAUUSD"], lookback_candles=96),
            IcebergDetector(market_engines["XAUUSD"]),
            htf_bias=0.5
        ),
        MTFAnalyzer(
            os.path.join(project_root, 'data', 'XAU_USD-60.csv'),
            None,
            os.path.join(project_root, 'data', 'XAU_USD-1D.csv')
        )
    )
    last_sig = market_signals[0].iloc[-1]
    idx = market_engines["XAUUSD"].df.index[
        market_engines["XAUUSD"].df['timestamp'] == last_sig['timestamp']
    ][0]
    print(explainer.explain_signal(idx))