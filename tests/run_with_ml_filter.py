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
from ml_filter import MLFilter

# 1. Load data (XAU_USD as example)
engine = MarketDataEngine.from_custom_csv(os.path.join(project_root, 'data', 'XAU_USD-15.csv'))
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
    h1_csv=os.path.join(project_root, 'data', 'XAU_USD-60.csv'),
    h4_csv=None,
    daily_csv=os.path.join(project_root, 'data', 'XAU_USD-1D.csv')
)
htf_bias = mtf.get_htf_bias(engine.df['timestamp'].iloc[-1]) if mtf.daily else 0.5

# Scoring (maybe with optimized weights)
weights_path = os.path.join(project_root, 'data', 'best_weights.json')
optimized_weights = None
if os.path.exists(weights_path):
    with open(weights_path) as f:
        optimized_weights = json.load(f)

scorer = ScoringEngine(liq, disp, zone, vp, ice, htf_bias=htf_bias, weights=optimized_weights)
executor = ExecutionLogic(scorer, engine, struct)
signals = executor.generate_signals(min_setup_score=70)
print(f"سیگنال‌های اولیه: {len(signals)}")

# 2. ML Filter: train on historical signals (walk-forward)
ml = MLFilter(liq, disp, zone, vp, ice)
# We'll use a simple training window: first 80% of data for training, rest for testing (time-series)
split_idx = int(len(engine.df) * 0.8)
# Generate signals for training period (before split_idx) to create training dataset
# But we need a separate scorer for that? Actually, we can generate signals on the whole dataset then split by timestamp.
# Simpler: generate signals on the entire history, then split them into train/test based on timestamp.
all_signals = executor.generate_signals(min_setup_score=60)  # lower threshold to get more samples for training
train_signals = all_signals[all_signals['timestamp'] <= engine.df['timestamp'].iloc[split_idx]]
test_signals = all_signals[all_signals['timestamp'] > engine.df['timestamp'].iloc[split_idx]]

if len(train_signals) > 50:
    print("آموزش مدل ML...")
    reports = ml.train_walk_forward(train_signals, engine.df)
    ml.is_trained = True
    # Predict on test signals
    filtered_test = []
    for _, sig in test_signals.iterrows():
        ts = sig['timestamp']
        idx = engine.df.index[engine.df['timestamp'] == ts][0]
        # Build feature dict (same as in build_dataset)
        feat = {
            'sweep': liq.get_sweep(idx),
            'disp': disp.get_score(idx),
            'zone': max(zone.get_fvg_score(idx), zone.get_ob_score(idx)),
            'vpoc_dist': 0.0,
            'iceberg': ice.get_iceberg(idx),
            'regime_low': 1 if engine.get_regime(idx) == 'LOW_VOL' else 0,
            'regime_normal': 1 if engine.get_regime(idx) == 'NORMAL' else 0,
            'regime_high': 1 if engine.get_regime(idx) == 'HIGH_VOL' else 0,
        }
        if vp:
            vpoc = vp.get_vpoc(idx)
            if vpoc is not None:
                feat['vpoc_dist'] = min(abs(engine.df['close'].iloc[idx] - vpoc) / engine.df['ATR14'].iloc[idx], 2.0)
        prob = ml.predict(feat)
        if prob > 0.6:
            filtered_test.append(sig)
    test_signals_filtered = pd.DataFrame(filtered_test)
    print(f"سیگنال‌های پس از فیلتر ML: {len(test_signals_filtered)}")
    # Combine train and test for final output? We'll just output test signals.
    final_signals = test_signals_filtered
else:
    print("تعداد نمونه‌های آموزشی کافی نیست. فیلتر ML اعمال نشد.")
    final_signals = test_signals

# Save final signals
final_signals.to_csv(os.path.join(project_root, 'data', 'XAU_USD_signals_ml_filtered.csv'), index=False)

# Explanation of last signal
if len(final_signals) > 0:
    explainer = SignalExplainer(scorer, mtf)
    last_sig = final_signals.iloc[-1]
    idx = engine.df.index[engine.df['timestamp'] == last_sig['timestamp']][0]
    print(explainer.explain_signal(idx))
