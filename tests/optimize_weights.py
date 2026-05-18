import sys, os, json
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

from market_engine import MarketDataEngine
from structure_engine import StructuralEngine
from liquidity_engine import LiquidityEngine
from displacement_engine import DisplacementEngine
from zone_engine import ZoneEngine
from volume_profile import VolumeProfileEngine
from iceberg_detector import IcebergDetector
from optimizer import Optimizer

# 1. Load data (only XAU_USD for optimization)
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

# 2. Set up optimizer
opt = Optimizer(engine, struct, liq, disp, zone, vp, ice)

# 3. Define parameter grid for grid search (you can adjust)
param_grid = {
    'w_sweep': [0.15, 0.25, 0.35],
    'w_disp': [0.20, 0.30, 0.40],
    'w_zone': [0.20, 0.25, 0.30],
    'w_htf': [0.05, 0.10, 0.15],
    'w_vpoc': [0.05],
    'w_iceberg': [0.05]
}

print("شروع Grid Search...")
best_grid = opt.grid_search(param_grid)
print(f"Grid Search بهترین: {best_grid['weights']} با امتیاز {best_grid['score']:.3f}")

# 4. Run genetic algorithm for finer tuning
print("شروع Genetic Algorithm...")
best_weights, best_score = opt.genetic_algorithm(pop_size=20, generations=5)
print(f"Genetic بهترین وزن‌ها: {best_weights} با امتیاز {best_score:.3f}")

# 5. Save best weights to file
output_path = os.path.join(project_root, 'data', 'best_weights.json')
with open(output_path, 'w') as f:
    json.dump(best_weights, f, indent=4)
print(f"وزن‌های بهینه در {output_path} ذخیره شدند.")
