# run_analysis_final.py — تحلیل کامل سه بازار با تمام ماژول‌ها
import sys, os, pandas as pd, json, numpy as np

# ---- 1. مسیرها ----
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, project_root)

# ---- 2. ایمپورت‌های اصلی ----
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

from fvg import detect_fvg
from order_blocks import detect_order_blocks
from dealing_range import detect_dealing_range
from regime import classify_regime
from cross_market import cross_market_analysis
from config import LIQUIDITY_THRESHOLDS, BOS_MIN_DISPLACEMENT
from delivery_quality import evaluate_delivery

# ---- 3. تابع کمکی: افزودن ستون‌های BOS به DataFrame ----
def add_bos_columns(df, window=5):
    """اضافه کردن bos_bull و bos_bear با تشخیص ساده BOS"""
    df = df.copy()
    sh = df['high'].rolling(window, min_periods=1).max().shift(1)
    sl = df['low'].rolling(window, min_periods=1).min().shift(1)
    df['bos_bull'] = (df['close'] > sh) & (df['close'].shift(1) <= sh.shift(1))
    df['bos_bear'] = (df['close'] < sl) & (df['close'].shift(1) >= sl.shift(1))
    return df

# ---- 4. تنظیمات بازارها ----
markets_to_process = [
    {"name": "XAUUSD",        "csv": "XAU_USD-15.csv",       "h1": "XAU_USD-60.csv",       "daily": "XAU_USD-1D.csv"},
    {"name": "HaratUSD",      "csv": "haratFardayi-15.csv",  "h1": "haratFardayi-60.csv",  "daily": "haratFardayi-1D.csv"},
    {"name": "AbshodeNaghdi", "csv": "abshodeNaghdi-15.csv", "h1": "abshodeNaghdi-60.csv", "daily": "abshodeNaghdi-1D.csv"},
]

# ---- 5. وزن‌های بهینه (اختیاری) ----
weights_path = os.path.join(project_root, 'data', 'best_weights.json')
optimized_weights = None
if os.path.exists(weights_path):
    with open(weights_path) as f:
        optimized_weights = json.load(f)
    print(f"⚖️ وزن‌های بهینه: {optimized_weights}\n")

# ---- 6. پردازش هر بازار ----
market_dfs = {}
market_engines = {}
market_signals = []

for mkt in markets_to_process:
    name = mkt["name"]
    print(f"\n{'='*60}")
    print(f"  بازار: {name}")
    print(f"{'='*60}")

    engine = MarketDataEngine.from_custom_csv(os.path.join(project_root, 'data', mkt["csv"]))
    print(f"  کندل: {len(engine.df)}")

    # اعمال تحلیل‌های پایه
    engine.df = detect_fvg(engine.df, market_name=name)
    engine.df = detect_order_blocks(engine.df, market_name=name)
    engine.df = detect_dealing_range(engine.df, market_name=name)
    engine.df = classify_regime(engine.df, market_name=name)
    engine.df = add_bos_columns(engine.df)

    # کیفیت تحویل (روی BOSهای صعودی/نزولی)
    engine.df = evaluate_delivery(engine.df, 'bos_bull', 'bull')
    engine.df = evaluate_delivery(engine.df, 'bos_bear', 'bear')

    # ساختار بازار
    struct = StructuralEngine(engine, market_name=name)
    struct.detect_swings(window=5)

    # موتورهای تحلیلی
    liq = LiquidityEngine(engine, market_name=name)
    disp = DisplacementEngine(engine)
    zone = ZoneEngine(engine, disp)
    vp = VolumeProfileEngine(engine, lookback_candles=96)
    ice = IcebergDetector(engine)
    liq.detect_sweeps()
    disp.score_all()
    zone.detect_fvg()
    zone.detect_ob()

    # چندتایم‌فریمی
    mtf = MTFAnalyzer(
        os.path.join(project_root, 'data', mkt["h1"]),
        None,
        os.path.join(project_root, 'data', mkt["daily"])
    )
    htf_bias = mtf.get_htf_bias(engine.df['timestamp'].iloc[-1]) if mtf.daily else 0.5

    # امتیازدهی و سیگنال‌ها
    scorer = ScoringEngine(liq, disp, zone, vp, ice, htf_bias=htf_bias, weights=optimized_weights)
    executor = ExecutionLogic(scorer, engine, struct)
    signals = executor.generate_signals(min_setup_score=70)

    market_dfs[name] = engine.df.set_index('timestamp')[['close']]
    market_engines[name] = engine
    market_signals.append(signals.assign(market=name))

    print(f"  ✅ سیگنال: {len(signals)}")
    print(f"  میانگین delivery_score (BOS صعودی): {engine.df.loc[engine.df['bos_bull'], 'delivery_score'].mean():.2f}")

# ---- 7. تحلیل بین‌بازاری ----
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
    print(f"  امتیاز هم‌سویی: {last_align}/3")
    print(f"  رژیم انتقال: {cross_df['regime'].iloc[-1]}")
except Exception as e:
    print(f"  ⚠️ خطا: {e}")
    last_align = 0

# ---- 8. ذخیرهٔ سیگنال‌ها ----
if last_align >= 2:
    final_signals = pd.concat(market_signals, ignore_index=True)
    final_signals.to_csv(os.path.join(project_root, 'data', 'all_markets_signals.csv'), index=False)
    print(f"\n✅ بازارها هم‌جهت — سیگنال‌ها ذخیره شدند ({len(final_signals)} عدد)")
else:
    pd.DataFrame().to_csv(os.path.join(project_root, 'data', 'all_markets_signals.csv'), index=False)
    print("\n⚠️ واگرایی — فایل سیگنال خالی ذخیره شد")

# ---- 9. گزارش آخرین سیگنال طلا ----
if last_align >= 2 and len(market_signals[0]) > 0:
    print("\n📋 گزارش فارسی آخرین سیگنال طلا:")
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