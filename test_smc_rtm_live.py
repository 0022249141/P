#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_smc_rtm_live.py — تست عملی SMC/RTM/Liquidity بر روی داده‌های واقعی
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

# Import enhancement module
from src.smc_rtm_liquidity_enhancer import (
    SMCQuantifier, RTMQuantifier, LiquidityInvertor,
    apply_smc_rtm_liquidity_enhancement
)

# Import market params
from src.market_params import MARKET_XAUUSD, MARKET_HARAT, MARKET_ABSHODE

def test_single_market(market_name, csv_file, market_params):
    """تست یک بازار با داده‌های 15 دقیقه‌ای"""
    print(f"\n{'='*70}")
    print(f"🔬 Testing {market_name.upper()}")
    print(f"{'='*70}")
    
    try:
        # بارگذاری داده (فرمت: Date,Time,Open,High,Low,Close,Volume)
        df = pd.read_csv(csv_file, header=None, 
                        names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
        
        # ترکیب تاریخ و ساعت
        df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str),
                                        format='%Y.%m.%d %H:%M')
        df = df.drop(columns=['date', 'time'])
        df = df.set_index('timestamp')
        
        print(f"✓ Loaded {len(df)} candles from {csv_file.name}")
        
        # نیاز به اطمینان از ستون‌های مورد نیاز
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            print(f"⚠ Missing columns. Available: {df.columns.tolist()}")
            return None
        
        # محاسبهٔ ATR (اگر موجود نیست)
        if 'atr' not in df.columns:
            atr_period = 14
            hl_diff = df['high'] - df['low']
            hc_diff = abs(df['high'] - df['close'].shift())
            lc_diff = abs(df['low'] - df['close'].shift())
            tr = pd.concat([hl_diff, hc_diff, lc_diff], axis=1).max(axis=1)
            df['atr'] = tr.rolling(atr_period).mean()
        
        df_enhanced = apply_smc_rtm_liquidity_enhancement(df, market_params)
        print(f"✓ Enhancement applied successfully")
        
        # تحلیل نتایج
        sweep_count = (df_enhanced['smc_footprint'] == 'sweep').sum()
        mitigate_count = (df_enhanced['smc_footprint'] == 'mitigate').sum()
        avg_conf = df_enhanced['smc_confidence'].mean()
        avg_retail_risk = df_enhanced['retail_trap_risk'].mean()
        
        print(f"\n📊 SMC Analysis Results:")
        print(f"   Sweeps detected:     {sweep_count:4d} ({sweep_count/len(df_enhanced)*100:5.2f}%)")
        print(f"   Mitigates detected:  {mitigate_count:4d} ({mitigate_count/len(df_enhanced)*100:5.2f}%)")
        print(f"   Avg SMC Confidence:  {avg_conf:6.2%}")
        print(f"   Avg Retail Risk:     {avg_retail_risk:6.2%}")
        
        # نمونه‌های های با سیگنال
        signals = df_enhanced[df_enhanced['smc_footprint'].notna()]
        if len(signals) > 0:
            print(f"\n🎯 Recent Signals (last 5):")
            for idx, (_, row) in enumerate(signals.tail(5).iterrows()):
                print(f"   {idx+1}. {row['smc_footprint']:12} | Conf: {row['smc_confidence']:5.1%} | "
                      f"Retail Risk: {row['retail_trap_risk']:5.1%}")
        
        # Liquidity zones
        imbalances = LiquidityInvertor(market_params).identify_imbalance_zones(df)
        print(f"\n💧 Liquidity Zones:")
        print(f"   Imbalances found:    {len(imbalances):4d}")
        if imbalances:
            for imb in imbalances[-3:]:
                print(f"   - {imb['type']:20} | Size: {imb['size_pct']:6.3f}% | "
                      f"Created: {imb['created_at']}")
        
        # Current market state
        current = df_enhanced.iloc[-1]
        print(f"\n📈 Current Market State:")
        print(f"   Price:               {current['close']:10.2f}")
        print(f"   ATR14:               {current.get('atr', 0):10.2f}")
        print(f"   Volume (last):       {current['volume']:10.0f}")
        print(f"   SMC Footprint:       {str(current['smc_footprint']):20}")
        print(f"   SMC Confidence:      {current['smc_confidence']:6.1%}")
        print(f"   Retail Trap Risk:    {current['retail_trap_risk']:6.1%}")
        
        return df_enhanced
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def generate_comparison_report(results_dict):
    """تولید گزارش مقایسه‌ای سه بازار"""
    print(f"\n{'='*70}")
    print(f"📋 COMPARATIVE ANALYSIS — سه بازار")
    print(f"{'='*70}")
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "markets": {}
    }
    
    for market_name, df_enhanced in results_dict.items():
        if df_enhanced is None:
            continue
        
        signals = df_enhanced[df_enhanced['smc_footprint'].notna()]
        
        market_data = {
            "total_candles": len(df_enhanced),
            "sweep_signals": (df_enhanced['smc_footprint'] == 'sweep').sum(),
            "mitigate_signals": (df_enhanced['smc_footprint'] == 'mitigate').sum(),
            "avg_confidence": float(df_enhanced['smc_confidence'].mean()),
            "avg_retail_risk": float(df_enhanced['retail_trap_risk'].mean()),
            "signal_quality": float(signals['smc_confidence'].mean()) if len(signals) > 0 else 0.0,
            "current_price": float(df_enhanced.iloc[-1]['close']),
            "current_atr": float(df_enhanced.iloc[-1].get('atr', 0)),
        }
        
        report["markets"][market_name] = market_data
    
    # Print comparison table
    print(f"\n{'Market':<20} {'Sweeps':>8} {'Mitigates':>10} {'Avg Conf':>10} {'Retail Risk':>12} {'Signal Q.':>10}")
    print("-" * 80)
    
    for market_name, data in report["markets"].items():
        print(f"{market_name:<20} {data['sweep_signals']:>8} {data['mitigate_signals']:>10} "
              f"{data['avg_confidence']:>9.1%} {data['avg_retail_risk']:>11.1%} {data['signal_quality']:>9.1%}")
    
    # Save report
    report_path = Path("data") / "smc_rtm_test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✓ Report saved to: {report_path}")
    
    return report


def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║        SMC/RTM/Liquidity Live Test on Real Market Data         ║
    ║                                                                ║
    ║  تست زنده بر روی داده‌های واقعی بازار                    ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    data_dir = Path("data")
    results = {}
    
    # Test XAUUSD (15m)
    print("\n🔷 Market 1: XAUUSD (Gold/USD)")
    xau_file = data_dir / "XAU_USD-15.csv"
    if xau_file.exists():
        results["XAUUSD"] = test_single_market("XAUUSD", xau_file, MARKET_XAUUSD)
    else:
        print(f"⚠ File not found: {xau_file}")
    
    # Test HaratUSD (15m)
    print("\n🔶 Market 2: HaratUSD (Iran FX)")
    harat_file = data_dir / "haratFardayi-15.csv"
    if harat_file.exists():
        results["HaratUSD"] = test_single_market("HaratUSD", harat_file, MARKET_HARAT)
    else:
        print(f"⚠ File not found: {harat_file}")
    
    # Test AbshodeNaghdi (15m)
    print("\n🔳 Market 3: AbshodeNaghdi (Iran Gold)")
    abshode_file = data_dir / "abshodeNaghdi-15.csv"
    if abshode_file.exists():
        results["AbshodeNaghdi"] = test_single_market("AbshodeNaghdi", abshode_file, MARKET_ABSHODE)
    else:
        print(f"⚠ File not found: {abshode_file}")
    
    # Generate comparison report
    if results:
        report = generate_comparison_report(results)
        
        print(f"\n{'='*70}")
        print(f"✅ TEST COMPLETE")
        print(f"{'='*70}")
        print(f"Results saved to: data/smc_rtm_test_report.json")
        
        # Summary statistics
        total_sweeps = sum(1 for r in results.values() if r is not None 
                          for _ in [r[r['smc_footprint'] == 'sweep']])
        print(f"\nTotal sweeps across all markets: {total_sweeps}")
    else:
        print("\n❌ No data files found or processed successfully")


if __name__ == "__main__":
    main()
