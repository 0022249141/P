import sys, os, pandas as pd, json
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

markets = [
    {
        'name': 'XAU_USD',
        'tf15': 'data/XAU_USD-15.csv',
        'h1': 'data/XAU_USD-60.csv',
        'daily': 'data/XAU_USD-1D.csv'
    },
    {
        'name': 'abshodeNaghdi',
        'tf15': 'data/abshodeNaghdi-15.csv',
        'h1': 'data/abshodeNaghdi-60.csv',
        'daily': 'data/abshodeNaghdi-1D.csv'
    },
    {
        'name': 'haratFardayi',
        'tf15': 'data/haratFardayi-15.csv',
        'h1': 'data/haratFardayi-60.csv',
        'daily': 'data/haratFardayi-1D.csv'
    }
]

# Load optimized weights if available
weights_path = os.path.join(project_root, 'data', 'best_weights.json')
optimized_weights = None
if os.path.exists(weights_path):
    with open(weights_path) as f:
        optimized_weights = json.load(f)
    print(f"وزن‌های بهینه بارگذاری شد: {optimized_weights}")
else:
    print("از وزن‌های پیش‌فرض استفاده می‌شود.")

summary = []

for market in markets:
    print(f"\n{'='*60}")
    print(f"در حال پردازش {market['name']} ...")
    # Load main timeframe
    engine = MarketDataEngine.from_custom_csv(os.path.join(project_root, market['tf15']))
    struct = StructuralEngine(engine)
    struct.detect_swings(window=5)

    liq = LiquidityEngine(engine)
    disp = DisplacementEngine(engine)
    zone = ZoneEngine(engine, disp)
    vp = VolumeProfileEngine(engine, lookback_candles=96)
    ice = IcebergDetector(engine)

    liq.detect_sweeps()
    disp.score_all()
    zone.detect_fvg()
    zone.detect_ob()

    # MTF
    mtf = MTFAnalyzer(
        h1_csv=os.path.join(project_root, market['h1']),
        h4_csv=None,
        daily_csv=os.path.join(project_root, market['daily'])
    )
    htf_bias = mtf.get_htf_bias(engine.df['timestamp'].iloc[-1]) if mtf.daily else 0.5

    # Scoring
    scorer = ScoringEngine(liq, disp, zone, vp, ice, htf_bias=htf_bias, weights=optimized_weights)
    executor = ExecutionLogic(scorer, engine, struct)
    signals = executor.generate_signals(min_setup_score=70)

    # Save signals
    signals_csv = os.path.join(project_root, 'data', f'{market["name"]}_signals.csv')
    signals.to_csv(signals_csv, index=False)
    print(f"سیگنال‌ها در {signals_csv} ذخیره شد. تعداد: {len(signals)}")

    # Last signal explanation
    explainer = SignalExplainer(scorer, mtf)
    if len(signals) > 0:
        last_sig = signals.iloc[-1]
        idx = engine.df.index[engine.df['timestamp'] == last_sig['timestamp']][0]
        expl = explainer.explain_signal(idx)
        print(f"\nگزارش آخرین سیگنال {market['name']}:")
        print(expl)

    # Summary stats
    avg_score = signals['setup_score'].mean() if len(signals) > 0 else 0
    summary.append({
        'market': market['name'],
        'signal_count': len(signals),
        'avg_setup_score': avg_score,
        'last_signal_time': signals['timestamp'].iloc[-1] if len(signals) > 0 else None
    })

# Print comparison
print("\n" + "="*60)
print("مقایسه نهایی بازارها")
print("="*60)
sum_df = pd.DataFrame(summary)
print(sum_df.to_string(index=False))
