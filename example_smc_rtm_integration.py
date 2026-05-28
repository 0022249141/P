# example_smc_rtm_integration.py — نمونه استفاده SMC/RTM/Liquidity
"""
مثال عملی: چگونه SMC/RTM/Liquidity Invertor را در pipeline استفاده کنیم
"""

import pandas as pd
import numpy as np
from pathlib import Path
from src.smc_rtm_liquidity_enhancer import (
    SMCQuantifier, RTMQuantifier, LiquidityInvertor,
    apply_smc_rtm_liquidity_enhancement
)

# فرض: market_params از src/market_params.py
MARKET_XAUUSD = {
    "volatility": {"atr_period": 14},
    "structure": {"bos_min_displacement_pct": 0.0025},
    "liquidity": {"liquidity_sweep_threshold_pct": 0.0003},
}


def example_1_basic_smc_detection():
    """نمونه ۱: تشخیص اولیهٔ sweep و mitigate"""
    print("\n" + "="*60)
    print("Example 1: Basic SMC Detection")
    print("="*60)
    
    # Load sample data
    df = pd.read_csv("data/sample_xauusd_15m.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    smc = SMCQuantifier(MARKET_XAUUSD)
    
    sweeps = []
    mitigates = []
    
    for i in range(10, len(df)):
        # Detect sweeps
        is_sweep, conf = smc.detect_sweep_pattern(df, i, lookback=10)
        if is_sweep:
            sweeps.append({
                'time': df.index[i],
                'price': df.iloc[i]['close'],
                'confidence': conf
            })
            print(f"  ✓ SWEEP at {df.index[i]}: conf={conf:.2%}")
        
        # Detect mitigates
        is_mitigate, conf = smc.detect_mitigate_pattern(df, i, lookback=20)
        if is_mitigate:
            mitigates.append({
                'time': df.index[i],
                'price': df.iloc[i]['close'],
                'confidence': conf
            })
            print(f"  ✓ MITIGATE at {df.index[i]}: conf={conf:.2%}")
    
    print(f"\nSummary: {len(sweeps)} sweeps, {len(mitigates)} mitigates detected")
    return df


def example_2_retail_trap_detection():
    """نمونه ۲: شناسایی تله‌های Retail"""
    print("\n" + "="*60)
    print("Example 2: Retail Trap Detection")
    print("="*60)
    
    df = pd.read_csv("data/sample_xauusd_1h.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    rtm = RTMQuantifier(MARKET_XAUUSD)
    
    traps = {'long': [], 'short': []}
    exhaustion_points = []
    
    for i in range(2, len(df)):
        # Long traps
        is_trap, conf = rtm.detect_retail_trap(df, i, direction="long")
        if is_trap:
            traps['long'].append({
                'time': df.index[i],
                'price': df.iloc[i]['close'],
                'risk': conf
            })
            print(f"  ⚠ LONG TRAP at {df.index[i]}: risk={conf:.2%}")
        
        # Short traps
        is_trap, conf = rtm.detect_retail_trap(df, i, direction="short")
        if is_trap:
            traps['short'].append({
                'time': df.index[i],
                'price': df.iloc[i]['close'],
                'risk': conf
            })
            print(f"  ⚠ SHORT TRAP at {df.index[i]}: risk={conf:.2%}")
        
        # Exhaustion
        is_exh, conf = rtm.detect_retail_exhaustion(df, i, lookback=15)
        if is_exh:
            exhaustion_points.append({
                'time': df.index[i],
                'price': df.iloc[i]['close'],
                'confidence': conf
            })
            print(f"  ✓ RETAIL EXHAUSTION at {df.index[i]}: conf={conf:.2%}")
    
    print(f"\nSummary: {len(traps['long'])} long traps, {len(traps['short'])} short traps")
    print(f"         {len(exhaustion_points)} exhaustion points")
    return df


def example_3_liquidity_inversion():
    """نمونه ۳: شناسایی و معکوس کردن نقدینگی"""
    print("\n" + "="*60)
    print("Example 3: Liquidity Inversion")
    print("="*60)
    
    df = pd.read_csv("data/sample_xauusd_4h.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    lic = LiquidityInvertor(MARKET_XAUUSD)
    
    # شناسایی imbalances
    imbalances = lic.identify_imbalance_zones(df, min_gap_pct=0.02)
    print(f"\nIdentified {len(imbalances)} imbalance zones:")
    for imb in imbalances[-5:]:  # Last 5
        print(f"  {imb['type']:20} | Range: {imb['bottom']:.2f}-{imb['top']:.2f} | {imb['size_pct']:.3f}%")
    
    # معکوس کردن جریان
    inverted = lic.invert_liquidity_flow(df, imbalances)
    print(f"\nInverted priority levels (top 5):")
    for i, level in enumerate(inverted[:5]):
        print(f"  {i+1}. Price: {level['level']:.2f} | Fill: {level['fill_probability']:.2%} | Priority: {level['priority']:.3f}")
    
    return df, imbalances, inverted


def example_4_full_enhancement():
    """نمونه ۴: استفاده کامل SMC/RTM/Liquidity enhancement"""
    print("\n" + "="*60)
    print("Example 4: Full SMC/RTM/Liquidity Enhancement")
    print("="*60)
    
    df = pd.read_csv("data/sample_xauusd_15m.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # اعمال تمام بهترینی‌ها
    df_enhanced = apply_smc_rtm_liquidity_enhancement(df, MARKET_XAUUSD)
    
    # نتایج
    print("\nNew columns added:")
    print(f"  - smc_footprint: {df_enhanced['smc_footprint'].notna().sum()} signals")
    print(f"  - smc_confidence: avg={df_enhanced['smc_confidence'].mean():.2%}")
    print(f"  - retail_trap_risk: avg={df_enhanced['retail_trap_risk'].mean():.2%}")
    print(f"  - imbalance_proximity: avg={df_enhanced['imbalance_proximity'].mean():.3f}")
    
    # نمونه rows
    print("\nSample enhanced rows (SMC signals only):")
    smc_signals = df_enhanced[df_enhanced['smc_footprint'].notna()]
    for idx, row in smc_signals.tail(3).iterrows():
        print(f"  {idx} | {row['smc_footprint']:15} | Conf={row['smc_confidence']:.2%} | RTM_Risk={row['retail_trap_risk']:.2%}")
    
    return df_enhanced


def example_5_integration_with_state_machine():
    """نمونه ۵: ادغام با state machine"""
    print("\n" + "="*60)
    print("Example 5: Integration with State Machine")
    print("="*60)
    
    df = pd.read_csv("data/sample_xauusd_15m.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # ۱. SMC/RTM enhancement
    df = apply_smc_rtm_liquidity_enhancement(df, MARKET_XAUUSD)
    
    # ۲. State machine enhanced (فرض)
    # در عملی، state_machine_enhanced باید از liquidity levels استفاده کند
    
    print("State machine would use:")
    print("  - smc_confidence: برای weight سیگنال‌ها")
    print("  - retail_trap_risk: برای فیلتر کردن سیگنال‌های خطرناک")
    print("  - imbalance_proximity: برای تعیین liquidity target")
    
    # Example: Filter signals by confidence + retail risk
    high_quality_signals = df[
        (df['smc_confidence'] > 0.65) & 
        (df['retail_trap_risk'] < 0.5)
    ]
    
    print(f"\nFiltered to {len(high_quality_signals)} high-quality signals (from {len(df)})")
    
    return df


def generate_dashboard_data(df_enhanced):
    """توليد داده برای dashboard"""
    print("\n" + "="*60)
    print("Generating Dashboard Data")
    print("="*60)
    
    current = df_enhanced.iloc[-1]
    
    dashboard_data = {
        "price": current['close'],
        "change_pct": ((current['close'] - df_enhanced.iloc[-20]['close']) / df_enhanced.iloc[-20]['close']) * 100,
        "h24": df_enhanced['high'].tail(96).max(),  # 24h high (15m bars)
        "l24": df_enhanced['low'].tail(96).min(),
        "atr14": current.get('atr', 0),
        "volatility": "NORMAL" if current.get('atr', 0) < 15 else "HIGH",
        "smc_footprint": current['smc_footprint'],
        "smc_confidence": current['smc_confidence'],
        "retail_trap_risk": current['retail_trap_risk'],
        "imbalance_proximity": current['imbalance_proximity'],
    }
    
    import json
    dashboard_json = json.dumps(dashboard_data, indent=2, default=str)
    print("\nDashboard JSON:")
    print(dashboard_json)
    
    # Save for dashboard
    with open("data/dashboard_data.json", "w") as f:
        f.write(dashboard_json)
    
    print("✓ Saved to data/dashboard_data.json")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║      SMC/RTM/Liquidity Invertor Integration Examples       ║
    ║                                                            ║
    ║  مثال‌های عملی برای استفاده در پروژه               ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    print("\n📌 تنبیه: نمونه‌ها فرض می‌کنند data/sample_*.csv موجود است")
    print("   در عملی، داده‌های واقعی از API یا CSV محلی بارگذاری شوند.\n")
    
    try:
        # example_1_basic_smc_detection()
        # example_2_retail_trap_detection()
        # df, imb, inv = example_3_liquidity_inversion()
        # df_enhanced = example_4_full_enhancement()
        # example_5_integration_with_state_machine()
        
        print("✓ تمام نمونه‌ها آماده هستند")
        print("\nبرای اجرا:")
        print("  python example_smc_rtm_integration.py")
        
    except FileNotFoundError as e:
        print(f"⚠ فایل داده یافت نشد: {e}")
        print("   لطفاً بعد از آماده‌سازی داده‌ها اجرا کنید")
