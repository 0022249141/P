import pandas as pd
from pathlib import Path
import sys
import importlib

# مسیر پروژه
sys.path.insert(0, str(Path(__file__).parent))

# ایمپورت ماژول‌های عددی با importlib
adaptive_sweep_mod = importlib.import_module('adaptive_sweep')
disp_mod = importlib.import_module('08_displacement')
zone_mod = importlib.import_module('09_zone_scoring')
state_mod = importlib.import_module('10_state_machine')
exec_mod = importlib.import_module('11_execution')

AdaptiveSweepDetector = adaptive_sweep_mod.AdaptiveSweepDetector
detect_displacement = disp_mod.detect_displacement
score_order_blocks = zone_mod.score_order_blocks
score_breakers_vectorized = zone_mod.score_breakers_vectorized
compute_setup_score = zone_mod.compute_setup_score
apply_state_machine = state_mod.apply_state_machine
compute_trade_parameters = exec_mod.compute_trade_parameters

# بازارها و تایم‌فریم‌ها
markets = {
    "XAU_USD": "XAU_USD-15",
    "abshodeNaghdi": "abshodeNaghdi-15",
    "haratFardayi": "haratFardayi-15"
}

BASE_INPUT = Path(r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2")
BASE_OUTPUT = BASE_INPUT

for market, tf in markets.items():
    print(f"\n{'='*50}")
    print(f"در حال پردازش {market} ({tf})...")
    input_file = BASE_INPUT / f"struct_processed_{tf}.csv"
    if not input_file.exists():
        print(f"⚠️ فایل {input_file} یافت نشد. رد می‌شود.")
        continue

    df = pd.read_csv(input_file)

    # لایه‌ها
    detector = AdaptiveSweepDetector()
    df = detector.detect(df)
    df = detect_displacement(df)
    df = score_order_blocks(df)
    df = score_breakers_vectorized(df)
    df = compute_setup_score(df)
    df = apply_state_machine(df)

    final_output = BASE_OUTPUT / f"final_{tf}.csv"
    df.to_csv(final_output, index=False)
    print(f"✅ سیگنال‌های نهایی ذخیره شد: {final_output}")

    trades = compute_trade_parameters(df, risk_percent=1.0, account_balance=10000,
                                      atr_sl_mult=1.5, rr_ratio=1.5)
    trade_output = BASE_OUTPUT / f"execution_plan_{tf}.csv"
    trades.to_csv(trade_output, index=False)
    print(f"✅ برنامه اجرایی ذخیره شد: {trade_output}")
    print(f"   سیگنال‌ها: {len(trades)} (Long: {len(trades[trades['direction']=='LONG'])} | Short: {len(trades[trades['direction']=='SHORT'])})")

print("\n🎯 پایان پردازش همه بازارها.")
