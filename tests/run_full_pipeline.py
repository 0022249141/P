import sys, os, pandas as pd
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

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

# 1. بارگذاری داده اصلی
engine = MarketDataEngine.from_custom_csv(os.path.join(project_root, 'data', 'XAU_USD-15.csv'))
struct = StructuralEngine(engine)
struct.detect_swings(window=5)

# 2. موتورهای تحلیل
liq = LiquidityEngine(engine)
disp = DisplacementEngine(engine)
zone = ZoneEngine(engine, disp)
vp = VolumeProfileEngine(engine, lookback_candles=96)
ice = IcebergDetector(engine)

liq.detect_sweeps()
disp.score_all()
zone.detect_fvg()
zone.detect_ob()

# 3. MTF (مطمئن شوید فایل‌های H1 و Daily وجود دارند)
mtf = MTFAnalyzer(
    h1_csv=os.path.join(project_root, 'data', 'XAU_USD-60.csv'),
    h4_csv=None,
    daily_csv=os.path.join(project_root, 'data', 'XAU_USD-1D.csv')
)

# 4. Scoring (با وزن‌های پیش‌فرض)
scorer = ScoringEngine(liq, disp, zone, vp, ice, htf_bias=0.6)
scorer.htf_bias = mtf.get_htf_bias(engine.df['timestamp'].iloc[-1])

# 5. تولید سیگنال
executor = ExecutionLogic(scorer, engine, struct)
signals = executor.generate_signals(min_setup_score=70)
print(f"تعداد سیگنال: {len(signals)}")

# 6. گزارش فارسی برای آخرین سیگنال
if len(signals) > 0:
    explainer = SignalExplainer(scorer, mtf)
    last_signal = signals.iloc[-1]
    idx = engine.df.index[engine.df['timestamp'] == last_signal['timestamp']][0]
    explanation = explainer.explain_signal(idx)
    print("\n" + "="*60)
    print(explanation)
    print("="*60)
