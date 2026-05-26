# smc_rtm_liquidity_enhancer.py — بهبود SMC/RTM/Liquidity Invertor
"""
تحسین جودی تحلیل با استفاده از:
1. SMC Quant — شناسایی و کمیت‌سازی فعالیت Smart Money
2. RTM Quant — شناسایی و معکوس کردن معاملات Retail
3. Liquidity Invertor — شناسایی و استفاده از مناطق نقدینگی حفاظی
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum

class VolatileRegime(Enum):
    """رژیم‌های نوسان بر اساس ATR و فشردگی"""
    COMPRESSION = "compression"       # ATR < low_threshold
    NORMAL = "normal"                 # ATR میان حدود
    EXPANSION = "expansion"           # ATR > high_threshold
    MANIPULATION = "manipulation"     # نوسان شدید + ریبالانس سریع


class SMCFootprint(Enum):
    """ردپای Smart Money بر اساس رفتار قیمتی"""
    SWEEP = "sweep"                   # نفوذ و برگشت سریع
    MITIGATE = "mitigate"            # مخفی کردن نقطهٔ خروج
    DISPLACE = "displace"             # جابجایی قدرتمند
    FAKE_BREAKOUT = "fake_breakout"  # شکست جعلی
    COMPRESSION_RELEASE = "comp_rel"  # رهایی از فشردگی


@dataclass
class LiquidityZone:
    """منطقهٔ نقدینگی با ویژگی‌های SMC/RTM"""
    price_level: float
    type: str                         # "bullish_pool" | "bearish_pool" | "imbalance"
    strength: float                   # 0-1
    touches: int                      # تعداد دفعاتی که مجدداً آزمایش شده
    creation_time: pd.Timestamp
    last_touch_time: pd.Timestamp
    smb_presence: float              # احتمال حضور Smart Money (0-1)
    retail_trap_risk: float          # احتمال تله‌ی Retail (0-1)


@dataclass
class SMCSignal:
    """سیگنال SMC مع جزئیات تحلیلی"""
    timestamp: pd.Timestamp
    type: SMCFootprint
    market_side: str                 # "long" | "short"
    confidence: float                # 0-1
    entry_level: float
    liquidity_target: float          # هدف نقدینگی
    invalidation_level: float
    retail_trap_potential: float     # احتمال اینکه Retail را گیر بیاندازد
    atm_quality: float              # کیفیت ATM (Asian Trading Mechanics)


class SMCQuantifier:
    """کمیت‌سازی Smart Money رفتار"""
    
    def __init__(self, market_params: Dict):
        self.mp = market_params
        self.atr_period = market_params.get("volatility", {}).get("atr_period", 14)
        self.bos_threshold = market_params.get("structure", {}).get("bos_min_displacement_pct", 0.0025)
        
    def detect_sweep_pattern(self, df: pd.DataFrame, idx: int, lookback: int = 10) -> Tuple[bool, float]:
        """
        تشخیص الگوی Sweep (نفوذ و برگشت سریع)
        
        شرایط:
        - high یا low از سطح قبلی عبور می‌کند
        - close معکوس می‌شود (rejection)
        - حجم تایید می‌کند
        
        Return: (is_sweep, confidence)
        """
        if idx < lookback + 2:
            return False, 0.0
        
        window = df.iloc[idx-lookback:idx]
        current = df.iloc[idx]
        prev = df.iloc[idx-1]
        
        atr = current.get('atr', 0)
        if atr == 0:
            return False, 0.0
        
        # سطح مقاومت/حمایت قبلی
        prev_high = window['high'].max()
        prev_low = window['low'].min()
        
        # شرط ۱: نفوذ
        penetrated_high = current['high'] > prev_high
        penetrated_low = current['low'] < prev_low
        
        if not (penetrated_high or penetrated_low):
            return False, 0.0
        
        # شرط ۲: rejection (wick)
        if penetrated_high:
            upper_wick = current['high'] - current['close']
            rejection_ratio = upper_wick / atr
        else:
            lower_wick = current['open'] - current['low']
            rejection_ratio = lower_wick / atr
        
        if rejection_ratio < 0.5:  # حداقل 0.5 ATR rejection
            return False, 0.0
        
        # شرط ۳: حجم تایید
        avg_vol = window['volume'].mean()
        vol_confirmation = current['volume'] / (avg_vol + 1e-6)
        
        # شرط ۴: بسته شدن خلاف جهت penetration
        if penetrated_high and current['close'] < prev['close']:
            close_confirmation = True
        elif penetrated_low and current['close'] > prev['close']:
            close_confirmation = True
        else:
            close_confirmation = False
        
        if not close_confirmation:
            return False, 0.0
        
        # محاسبهٔ confidence
        conf = (
            min(1.0, rejection_ratio / 2.0) * 0.3 +      # کیفیت rejection
            min(1.0, vol_confirmation / 1.5) * 0.4 +      # تایید حجم
            0.3 * 1.0                                      # بسته شدن معاکس
        )
        
        return True, conf
    
    def detect_mitigate_pattern(self, df: pd.DataFrame, idx: int, lookback: int = 20) -> Tuple[bool, float]:
        """
        تشخیص Mitigation Pattern — جایی که Smart Money بدون Sweep خروج می‌زند
        
        شرایط:
        - نزدیک Peak یا Trough قبلی
        - حجم کم
        - تشکیل دوباره بعد
        """
        if idx < lookback + 1:
            return False, 0.0
        
        window = df.iloc[idx-lookback:idx]
        current = df.iloc[idx]
        
        atr = current.get('atr', 0)
        if atr == 0:
            return False, 0.0
        
        # فاصله تا peak/trough
        window_high = window['high'].max()
        window_low = window['low'].min()
        
        dist_to_high = window_high - current['close']
        dist_to_low = current['close'] - window_low
        
        # حداقل ۰.۲ ATR از peak/trough
        if min(dist_to_high, dist_to_low) > 0.2 * atr:
            return False, 0.0
        
        # حجم کم (retail نمی‌خرد)
        avg_vol = window['volume'].mean()
        if current['volume'] > avg_vol * 0.8:
            return False, 0.0
        
        # body کوچک (uncertainty)
        body = abs(current['close'] - current['open'])
        if body > 0.5 * atr:
            return False, 0.0
        
        confidence = min(1.0, 0.7 - (current['volume'] / avg_vol) * 0.3)
        return True, confidence
    
    def quantify_liquidity_pool(self, df: pd.DataFrame, level: float, tolerance_pct: float = 0.05) -> Dict:
        """
        کمیت‌سازی pool نقدینگی در یک سطح
        
        جزئیات:
        - تعداد touches
        - آخرین touch
        - میانگین حجم در touches
        - احتمال بازگشت
        """
        atr = df['atr'].iloc[-1]
        tolerance = atr * tolerance_pct / 100
        
        touches = df[
            (df['high'] >= level - tolerance) & (df['high'] <= level + tolerance) |
            (df['low'] >= level - tolerance) & (df['low'] <= level + tolerance)
        ]
        
        if len(touches) == 0:
            return {"strength": 0.0, "touches": 0, "last_touch": None}
        
        # قوت = تعداد touches × تازگی آخرین touch
        recency = (len(df) - touches.index[-1]) / len(df)
        strength = min(1.0, (len(touches) / 5) * (1 - recency * 0.3))
        
        return {
            "strength": strength,
            "touches": len(touches),
            "last_touch": df.index[touches.index[-1]],
            "avg_volume_on_touch": touches['volume'].mean(),
            "probability_return": strength * 0.8 + (len(touches) / 10) * 0.2
        }


class RTMQuantifier:
    """کمیت‌سازی Retail Trading رفتار"""
    
    def __init__(self, market_params: Dict):
        self.mp = market_params
    
    def detect_retail_exhaustion(self, df: pd.DataFrame, idx: int, lookback: int = 15) -> Tuple[bool, float]:
        """
        تشخیص اگسشن Retail معاملگران
        
        نشانه‌ها:
        - حجم بالا + بسته شدن ضعیف
        - تشکیل doji/hammer بعد از حرکت شدید
        - reversal candle
        """
        if idx < lookback + 1:
            return False, 0.0
        
        window = df.iloc[idx-lookback:idx]
        current = df.iloc[idx]
        prev = df.iloc[idx-1]
        
        atr = current.get('atr', 0)
        if atr == 0:
            return False, 0.0
        
        # شرط ۱: حجم بالا
        avg_vol = window['volume'].mean()
        high_volume = current['volume'] > avg_vol * 1.5
        
        # شرط ۲: body ضعیف (doji-like)
        body = abs(current['close'] - current['open'])
        weak_body = body < 0.3 * atr
        
        # شرط ۳: wick بزرگ
        upper_wick = current['high'] - max(current['close'], current['open'])
        lower_wick = min(current['close'], current['open']) - current['low']
        large_wick = max(upper_wick, lower_wick) > 0.6 * atr
        
        # شرط ۴: معاکس جهت قبل
        prev_range = prev['high'] - prev['low']
        direction_reversal = (
            (current['close'] < prev['close'] and prev_range > 0.5 * atr) or
            (current['close'] > prev['close'] and prev_range > 0.5 * atr)
        )
        
        is_exhaustion = high_volume and weak_body and large_wick and direction_reversal
        conf = (
            (1.0 if high_volume else 0.0) * 0.25 +
            (1.0 if weak_body else 0.0) * 0.25 +
            (1.0 if large_wick else 0.0) * 0.25 +
            (1.0 if direction_reversal else 0.0) * 0.25
        )
        
        return is_exhaustion, conf
    
    def detect_retail_trap(self, df: pd.DataFrame, idx: int, direction: str = "long") -> Tuple[bool, float]:
        """
        تشخیص تله‌ی Retail
        
        سناریو Long Trap:
        - breakout + close بالا (retail خریدار)
        - candel بعد: open بالا + close پایین (خروج هوشمند)
        
        سناریو Short Trap: معکوس
        """
        if idx < 2:
            return False, 0.0
        
        prev2 = df.iloc[idx-2]
        prev1 = df.iloc[idx-1]
        current = df.iloc[idx]
        
        atr = current.get('atr', 0)
        if atr == 0:
            return False, 0.0
        
        if direction == "long":
            # شرط ۱: breakout + close بالا (جذب retail)
            breakout = prev2['high'] > df.iloc[:idx-2]['high'].max() * 0.99
            high_close = prev1['close'] > prev1['open']
            
            # شرط ۲: rejection (خروج هوشمند)
            rejection = current['close'] < current['open']
            gap_reversal = current['open'] > prev1['close']
            
            trap = breakout and high_close and rejection and gap_reversal
            conf = (1.0 if trap else 0.0) * 0.8 + 0.2 * (1.0 if gap_reversal else 0.0)
        
        else:  # short trap
            breakout = prev2['low'] < df.iloc[:idx-2]['low'].min() * 1.01
            low_close = prev1['close'] < prev1['open']
            rejection = current['close'] > current['open']
            gap_reversal = current['open'] < prev1['close']
            
            trap = breakout and low_close and rejection and gap_reversal
            conf = (1.0 if trap else 0.0) * 0.8 + 0.2 * (1.0 if gap_reversal else 0.0)
        
        return trap, conf


class LiquidityInvertor:
    """شناسایی و معکوس کردن فعالیت نقدینگی"""
    
    def __init__(self, market_params: Dict):
        self.mp = market_params
        self.liquidity_zones: List[LiquidityZone] = []
    
    def identify_imbalance_zones(self, df: pd.DataFrame, min_gap_pct: float = 0.02) -> List[Dict]:
        """
        شناسایی Fair Value Gaps (FVG) / Imbalances
        
        شرایط:
        - Bullish: low[i] > high[i-2] (gap رو بالا)
        - Bearish: high[i] < low[i-2] (gap رو پایین)
        """
        imbalances = []
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else 1.0
        
        for i in range(2, len(df)):
            # bullish imbalance
            if df.iloc[i]['low'] > df.iloc[i-2]['high']:
                gap = df.iloc[i]['low'] - df.iloc[i-2]['high']
                gap_pct = (gap / df.iloc[i-2]['high']) * 100
                
                if gap_pct >= min_gap_pct:
                    imbalances.append({
                        "type": "bullish_imbalance",
                        "top": df.iloc[i-2]['high'],
                        "bottom": df.iloc[i]['low'],
                        "size_pct": gap_pct,
                        "created_at": df.index[i],
                        "filled": False,
                        "fill_time": None
                    })
            
            # bearish imbalance
            elif df.iloc[i]['high'] < df.iloc[i-2]['low']:
                gap = df.iloc[i-2]['low'] - df.iloc[i]['high']
                gap_pct = (gap / df.iloc[i-2]['low']) * 100
                
                if gap_pct >= min_gap_pct:
                    imbalances.append({
                        "type": "bearish_imbalance",
                        "top": df.iloc[i]['high'],
                        "bottom": df.iloc[i-2]['low'],
                        "size_pct": gap_pct,
                        "created_at": df.index[i],
                        "filled": False,
                        "fill_time": None
                    })
        
        return imbalances
    
    def invert_liquidity_flow(self, df: pd.DataFrame, imbalances: List[Dict]) -> Dict:
        """
        معکوس کردن جریان نقدینگی
        
        منطق: اگر Smart Money یک imbalance را ایجاد کرد،
        احتمالاً بعداً آن را fill کند یا از آن استفاده کند
        """
        current_price = df.iloc[-1]['close']
        inverted_levels = []
        
        for imb in imbalances:
            if imb["filled"]:
                continue
            
            level = (imb["top"] + imb["bottom"]) / 2
            distance = abs(level - current_price)
            
            # اگر قیمت نزدیک باشد، احتمال fill بیشتر است
            fill_probability = 1.0 - min(1.0, distance / (imb["top"] - imb["bottom"]))
            
            inverted_levels.append({
                "level": level,
                "type": imb["type"],
                "distance": distance,
                "fill_probability": fill_probability,
                "imbalance_age_bars": len(df) - df[df.index == imb["created_at"]].index.get_loc(imb["created_at"]) if imb["created_at"] in df.index else 0,
                "priority": fill_probability * 0.6 + (imb["size_pct"] / 100) * 0.4
            })
        
        return sorted(inverted_levels, key=lambda x: x["priority"], reverse=True)


def apply_smc_rtm_liquidity_enhancement(df: pd.DataFrame, market_params: Dict) -> pd.DataFrame:
    """
    استفاده جامع از SMC/RTM/Liquidity Invertor
    """
    smc = SMCQuantifier(market_params)
    rtm = RTMQuantifier(market_params)
    lic = LiquidityInvertor(market_params)
    
    df = df.copy()
    df['smc_footprint'] = None
    df['smc_confidence'] = 0.0
    df['retail_trap_risk'] = 0.0
    df['imbalance_proximity'] = 0.0
    
    # تشخیص patterns
    for i in range(2, len(df)):
        # SMC patterns
        is_sweep, sweep_conf = smc.detect_sweep_pattern(df, i)
        if is_sweep:
            df.at[df.index[i], 'smc_footprint'] = 'sweep'
            df.at[df.index[i], 'smc_confidence'] = sweep_conf
        
        is_mitigate, mitigate_conf = smc.detect_mitigate_pattern(df, i)
        if is_mitigate:
            df.at[df.index[i], 'smc_footprint'] = 'mitigate'
            df.at[df.index[i], 'smc_confidence'] = mitigate_conf
        
        # RTM patterns
        is_exhaustion, exh_conf = rtm.detect_retail_exhaustion(df, i)
        if is_exhaustion:
            df.at[df.index[i], 'retail_trap_risk'] = exh_conf
        
        is_trap_long, trap_conf_long = rtm.detect_retail_trap(df, i, direction="long")
        is_trap_short, trap_conf_short = rtm.detect_retail_trap(df, i, direction="short")
        df.at[df.index[i], 'retail_trap_risk'] = max(trap_conf_long, trap_conf_short)
    
    # Liquidity Invertor
    imbalances = lic.identify_imbalance_zones(df)
    inverted = lic.invert_liquidity_flow(df, imbalances)
    
    df['imbalance_levels'] = None
    if inverted:
        top_level = inverted[0]['level']
        df['imbalance_proximity'] = 1.0 - np.minimum(1.0, np.abs(df['close'] - top_level) / (df['atr'] * 2))
    
    return df


if __name__ == "__main__":
    # نمونه استفاده
    print("✅ SMC/RTM/Liquidity Invertor Enhancement Module Ready")
