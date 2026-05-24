"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 2: STRUCTURAL ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

توضیح فارسی:
این لایه ساختار بازار را تشخیص می‌دهد:

1. SWING HIGHS/LOWS = نقاط چرخش (pivot points)
   - نقاطی که قیمت در آن‌ها جهت تغییر می‌دهد
   - اما نه فقط هر نقطه، بلکه نقاط مهم!

2. BOS (Break Of Structure) = شکستن ساختار
   - وقتی قیمت یک Swing High را شکند = BULLISH BOS
   - وقتی قیمت یک Swing Low را شکند = BEARISH BOS
   - این نشانه تغییر trend است

3. CHOCH (Change Of Character) = تغییر کاراکتر
   - این زمانی است که BOS با تغییر trend همراه باشد
   - مثلاً: بازار bearish بود، حالا bullish شد = CHOCH

4. MSS (Market Structure Shift) = شیفت در ساختار بازار
   - ترتیب swings تغییر می‌کند

مهم: این الگوریتم بدون Repaint است!
زیرا ما فقط closed candles را بررسی می‌کنیم.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional


class StructuralEngine:
    """
    تشخیص ساختار بازار
    """
    
    def __init__(self, min_strength: float = 0.6):
        """
        min_strength: حداقل قدرت swing برای شمارش
        (0 = هر نقطه، 1 = فقط نقاط خیلی قوی)
        """
        self.min_strength = min_strength
    
    # ═══════════════════════════════════════════════════════════════════════
    # SWING STRENGTH CALCULATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_swing_strength(
        self,
        left_candles: List,
        pivot_candle: Dict,
        right_candles: List
    ) -> float:
        """
        محاسبه قدرت یک swing
        
        فرمول:
        strength = (height_ratio * 0.4) + (body_ratio * 0.3) + (range_factor * 0.3)
        
        - height_ratio: pivot چقدر بالاتر/پایین‌تر است؟
        - body_ratio: body candleها قوی‌اند؟
        - range_factor: range مقابل میانگین چگونه است؟
        """
        
        # Component 1: Relative Height
        left_highs = [c['high'] for c in left_candles]
        right_highs = [c['high'] for c in right_candles]
        left_lows = [c['low'] for c in left_candles]
        right_lows = [c['low'] for c in right_candles]
        
        # برای Swing High
        if pivot_candle.get('is_high'):
            left_ref = np.mean(left_highs) if left_highs else pivot_candle['high']
            right_ref = np.mean(right_highs) if right_highs else pivot_candle['high']
            ref_level = (left_ref + right_ref) / 2
            
            all_lows = [c['low'] for c in left_candles + right_candles]
            min_level = min(all_lows) if all_lows else pivot_candle['low']
            
            height = pivot_candle['high'] - ref_level
            total_span = pivot_candle['high'] - min_level
            height_ratio = height / total_span if total_span > 0 else 0.5
        
        # برای Swing Low
        else:
            left_ref = np.mean(left_lows) if left_lows else pivot_candle['low']
            right_ref = np.mean(right_lows) if right_lows else pivot_candle['low']
            ref_level = (left_ref + right_ref) / 2
            
            all_highs = [c['high'] for c in left_candles + right_candles]
            max_level = max(all_highs) if all_highs else pivot_candle['high']
            
            depth = ref_level - pivot_candle['low']
            total_span = max_level - pivot_candle['low']
            height_ratio = depth / total_span if total_span > 0 else 0.5
        
        # Component 2: Body Quality
        candle_body = abs(pivot_candle['close'] - pivot_candle['open'])
        candle_range = pivot_candle['high'] - pivot_candle['low']
        body_ratio = candle_body / candle_range if candle_range > 0 else 0
        
        # Component 3: Range Normalization
        all_ranges = [c['high'] - c['low'] for c in left_candles + [pivot_candle] + right_candles]
        avg_range = np.mean(all_ranges)
        range_factor = candle_range / avg_range if avg_range > 0 else 1
        
        strength = (
            (np.clip(height_ratio, 0, 1) * 0.4) +
            (np.clip(body_ratio, 0, 1) * 0.3) +
            (np.clip(range_factor / 2, 0, 1) * 0.3)
        )
        
        return np.clip(strength, 0, 1)
    
    # ═══════════════════════════════════════════════════════════════════════
    # DETECT SWING HIGHS (نقاط اوج)
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_swing_highs(self, df: pd.DataFrame, lookback: int = 5) -> List[Dict]:
        """
        Swing High = نقطه‌ای که:
        1. به‌ترتیب N کندل از چپ و راست بالاتر است
        2. قدرت کافی دارد
        
        lookback: چند کندل از دو طرف؟ (معمول 2-3)
        """
        
        swings = []
        
        for i in range(lookback, len(df) - lookback):
            current = df.iloc[i]
            
            # بررسی چپ
            left_higher = True
            for j in range(i - lookback, i):
                if df.iloc[j]['high'] >= current['high']:
                    left_higher = False
                    break
            
            if not left_higher:
                continue
            
            # بررسی راست
            right_higher = True
            for j in range(i + 1, i + lookback + 1):
                if df.iloc[j]['high'] >= current['high']:
                    right_higher = False
                    break
            
            if not right_higher:
                continue
            
            # محاسبه قدرت
            left_candles = [df.iloc[j].to_dict() for j in range(i - lookback, i)]
            right_candles = [df.iloc[j].to_dict() for j in range(i + 1, i + lookback + 1)]
            current_dict = current.to_dict()
            current_dict['is_high'] = True
            
            strength = self.calculate_swing_strength(left_candles, current_dict, right_candles)
            
            if strength >= self.min_strength:
                swings.append({
                    'index': i,
                    'timestamp': df.index[i],
                    'price': current['high'],
                    'strength': strength,
                    'type': 'HIGH'
                })
        
        return swings
    
    # ═══════════════════════════════════════════════════════════════════════
    # DETECT SWING LOWS (نقاط حداقل)
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_swing_lows(self, df: pd.DataFrame, lookback: int = 5) -> List[Dict]:
        """
        Swing Low = نقطه‌ای که:
        1. به‌ترتیب N کندل از چپ و راست پایین‌تر است
        2. قدرت کافی دارد
        """
        
        swings = []
        
        for i in range(lookback, len(df) - lookback):
            current = df.iloc[i]
            
            # بررسی چپ
            left_lower = True
            for j in range(i - lookback, i):
                if df.iloc[j]['low'] <= current['low']:
                    left_lower = False
                    break
            
            if not left_lower:
                continue
            
            # بررسی راست
            right_lower = True
            for j in range(i + 1, i + lookback + 1):
                if df.iloc[j]['low'] <= current['low']:
                    right_lower = False
                    break
            
            if not right_lower:
                continue
            
            # محاسبه قدرت
            left_candles = [df.iloc[j].to_dict() for j in range(i - lookback, i)]
            right_candles = [df.iloc[j].to_dict() for j in range(i + 1, i + lookback + 1)]
            current_dict = current.to_dict()
            current_dict['is_high'] = False
            
            strength = self.calculate_swing_strength(left_candles, current_dict, right_candles)
            
            if strength >= self.min_strength:
                swings.append({
                    'index': i,
                    'timestamp': df.index[i],
                    'price': current['low'],
                    'strength': strength,
                    'type': 'LOW'
                })
        
        return swings
    
    # ═══════════════════════════════════════════════════════════════════════
    # DETECT BOS & CHOCH
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_bos_choch(
        self,
        df: pd.DataFrame,
        swing_highs: List[Dict],
        swing_lows: List[Dict]
    ) -> Tuple[pd.Series, pd.Series]:
        """
        BOS = Break Of Structure
        CHOCH = Change Of Character
        
        State Machine:
        - اگر بازار bullish است و Swing High شکسته شود = BOS (ادامه bullish)
        - اگر بازار bearish است و Swing Low شکسته شود = BOS (ادامه bearish)
        - اگر BOS با تغییر trend باشد = CHOCH
        """
        
        bos = pd.Series(False, index=df.index)
        choch = pd.Series(False, index=df.index)
        
        # Determine initial trend
        trend = None
        
        for i in range(len(df)):
            current_price = df.iloc[i]['close']
            
            # بررسی Swing Highs برای BULLISH BOS
            for sh in swing_highs:
                if i > sh['index']:
                    # آیا Swing High شکسته شد؟
                    if df.iloc[i]['high'] > sh['price']:
                        
                        # اگر trend قبل‌تر bearish بود
                        if trend == "BEARISH":
                            choch.iloc[i] = True  # تغییر کاراکتر
                        
                        bos.iloc[i] = True
                        trend = "BULLISH"
                        break
            
            # بررسی Swing Lows برای BEARISH BOS
            for sl in swing_lows:
                if i > sl['index']:
                    # آیا Swing Low شکسته شد؟
                    if df.iloc[i]['low'] < sl['price']:
                        
                        # اگر trend قبل‌تر bullish بود
                        if trend == "BULLISH":
                            choch.iloc[i] = True
                        
                        bos.iloc[i] = True
                        trend = "BEARISH"
                        break
        
        return bos, choch
    
    # ═══════════════════════════════════════════════════════════════════════
    # MARKET STRUCTURE STATE
    # ═══════════════════════════════════════════════════════════════════════
    
    def determine_market_structure(
        self,
        swing_highs: List[Dict],
        swing_lows: List[Dict]
    ) -> str:
        """
        تعیین وضعیت ساختار بازار:
        - UPTREND: Higher Highs و Higher Lows
        - DOWNTREND: Lower Highs و Lower Lows
        - RANGING: نوسان‌های افقی
        """
        
        if not swing_highs or not swing_lows:
            return "UNKNOWN"
        
        # آخرین دو swing high
        recent_highs = sorted(swing_highs, key=lambda x: x['index'])[-2:]
        recent_lows = sorted(swing_lows, key=lambda x: x['index'])[-2:]
        
        if len(recent_highs) >= 2:
            higher_high = recent_highs[-1]['price'] > recent_highs[-2]['price']
        else:
            higher_high = None
        
        if len(recent_lows) >= 2:
            higher_low = recent_lows[-1]['price'] > recent_lows[-2]['price']
        else:
            higher_low = None
        
        if higher_high and higher_low:
            return "UPTREND"
        elif not higher_high and not higher_low:
            return "DOWNTREND"
        else:
            return "RANGING"
    
    # ═══════════════════════════════════════════════════════════════════════
    # MAIN PIPELINE
    # ═══════════════════════════════════════════════════════════════════════
    
    def process(self, df: pd.DataFrame, lookback: int = 2) -> pd.DataFrame:
        """
        اعمال تمام محاسبات
        """
        
        # Step 1: Detect Swings
        swing_highs = self.detect_swing_highs(df, lookback=lookback)
        swing_lows = self.detect_swing_lows(df, lookback=lookback)
        
        # Step 2: Create columns
        df['swing_high'] = False
        df['swing_low'] = False
        df['swing_high_price'] = np.nan
        df['swing_low_price'] = np.nan
        
        for sh in swing_highs:
            df.loc[df.index[sh['index']], 'swing_high'] = True
            df.loc[df.index[sh['index']], 'swing_high_price'] = sh['price']
        
        for sl in swing_lows:
            df.loc[df.index[sl['index']], 'swing_low'] = True
            df.loc[df.index[sl['index']], 'swing_low_price'] = sl['price']
        
        # Step 3: Detect BOS & CHOCH
        bos, choch = self.detect_bos_choch(df, swing_highs, swing_lows)
        df['bos'] = bos
        df['choch'] = choch
        
        # Step 4: Market Structure
        structure = self.determine_market_structure(swing_highs, swing_lows)
        df['market_structure'] = structure
        
        # Step 5: Store swing data for next layers
        df.attrs['swing_highs'] = swing_highs
        df.attrs['swing_lows'] = swing_lows
        
        return df


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from pathlib import Path
    from layer1_market_data_engine import MarketDataEngine
    
    # بارگذاری و Layer 1
    data_path = Path("data/abshodeNaghdi-1.csv")
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    df = df.set_index('timestamp')
    
    print("📊 بارگذاری داده کامل شد")
    
    # Layer 1
    engine1 = MarketDataEngine()
    df = engine1.process(df)
    print("✅ Layer 1 اعمال شد")
    
    # Layer 2
    engine2 = StructuralEngine(min_strength=0.5)
    df = engine2.process(df)
    print("✅ Layer 2 اعمال شد\n")
    
    # نمایش نتایج
    swing_info = df[df['swing_high'] | df['swing_low']][['close', 'swing_high', 'swing_low']].tail(20)
    print("Swing Points:")
    print(swing_info)
    
    bos_info = df[df['bos']][['close', 'bos', 'choch']].tail(10)
    print("\nBOS/CHOCH:")
    print(bos_info)
