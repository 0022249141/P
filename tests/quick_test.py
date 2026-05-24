import sys, os, time
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

print("1. Importing libs...")
from market_engine import MarketDataEngine
from structure_engine import StructuralEngine
from liquidity_engine import LiquidityEngine
from displacement_engine import DisplacementEngine
from zone_engine import ZoneEngine
print("   Done")

print("2. Loading XAU_USD-15...")
engine = MarketDataEngine.from_custom_csv(os.path.join(project_root, 'data', 'XAU_USD-15.csv'))
print(f"   Candles: {len(engine.df)}")

print("3. Structure...")
struct = StructuralEngine(engine)
struct.detect_swings(window=5)
print("   Done")

print("4. Engines...")
liq = LiquidityEngine(engine)
disp = DisplacementEngine(engine)
zone = ZoneEngine(engine, disp)
print("   Done")

print("5. Sweeps...")
liq.detect_sweeps()
print("   Done")

print("6. Displacement...")
disp.score_all()
print("   Done")

print("7. Zones...")
zone.detect_fvg()
zone.detect_ob()
print("   Done")

print("\n✅ System OK.")