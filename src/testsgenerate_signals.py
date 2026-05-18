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
from scoring_engine import ScoringEngine
from execution_logic import ExecutionLogic

# 1. Load data
file_path = os.path.join(project_root, 'data', 'XAU_USD-15.csv')
engine = MarketDataEngine.from_custom_csv(file_path)

# 2. Structure
struct = StructuralEngine(engine)
struct.detect_swings(window=5)

# 3. Analysis engines
liq = LiquidityEngine(engine)
disp = DisplacementEngine(engine)
zone = ZoneEngine(engine, disp)

liq.detect_sweeps()
disp.score_all()
zone.detect_fvg()
zone.detect_ob()

# 4. Scoring & Execution
scorer = ScoringEngine(liq, disp, zone, htf_bias=0.6)  # 0.6 = slightly bullish bias
executor = ExecutionLogic(scorer, engine, struct)

# 5. Generate signals
signals = executor.generate_signals(min_setup_score=70)
print(f"تعداد سیگنال‌های با کیفیت: {len(signals)}")

# 6. Save to CSV (for smc_validation)
output_path = os.path.join(project_root, 'data', 'generated_signals.csv')
signals.to_csv(output_path, index=False)
print(f"سیگنال‌ها در {output_path} ذخیره شدند.")

# نمایش ۱۰ سیگنال آخر
if len(signals) > 0:
    print("\nآخرین سیگنال‌ها:")
    print(signals.tail(10))
