"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 4: DISPLACEMENT ENGINE ⚡ (THE CORE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

توضیح فارسی:
Displacement = حرکت قوی بازار
این لایه نشخواهد می‌دهد که:
- آیا کندل‌ها با قدرت حرکت می‌کنند؟
- آیا این حرکت Institutional است؟
- آیا این تا کجا ادامه خواهد یافت؟

تعریف ریاضی:
Impulse Candle (کندل انگیزاننده):
1. Range (High-Low) بزرگ‌تر از میانگین است
2. Body قوی است (نه Doji)
3. Direction واضح است
4. Unidirectional است

مثال:
اگر ATR = 100 pips
- Normal candle: 60 pips
- Impulse candle: 140+ pips با body 80%+
- Non-Impulse: 40 pips یا body 20%

اهمیت:
Sweeps بدون Displacement = فیک است!
اما Displacement بدون sweep = نقصان!

ما باید هر دو را داشته باشیم.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional


class DisplacementEngine:
    """
    تشخیص impulse candles و displacement sequences
    """
    
    def __init__(self):
        pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # IMPULSE CANDLE DETECTION
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_impulse_candle(
        self,
        candle: pd.Series,
        atr: float,
        volatility_regime: str,
        avg_body_ratio: float = 0.6
    ) -> Dict:
        """
        تشخیص Impulse Candle
        
        شرایط:
        1. Range Normalized (بزرگ‌تر از ATR)
        2. Body Ratio (بدنه قوی)
        3. Unidirectionality (جهت واضح)
        4. Volume Confirmation (optional)
        
        Adaptive Thresholds (بر اساس volatility_regime):
        - LOW_VOL: threshold بالاتر (سختگیری بیشتر)
        - NORMAL: threshold میانه
        - HIGH_VOL: threshold پایین‌تر (بخشش بیشتر)
        """
        
        if atr == 0 or np.isnan(atr):
            return None
        
        # Component 1: Range Normalization
        candle_range = candle['high'] - candle['low']
        range_ratio = candle_range / atr
        
        # Adaptive Threshold برای Range
        if volatility_regime == "HIGH_VOL":
            min_range_atr = 1.0
            max_range_atr = 3.5
        elif volatility_regime == "LOW_VOL":
            min_range_atr = 1.5
            max_range_atr = 5.0
        else:  # NORMAL
            min_range_atr = 1.2
            max_range_atr = 4.0
        
        # بررسی اینکه range در محدوده است
        if not (min_range_atr <= range_ratio <= max_range_atr):
            return None
        
        # Component 2: Body Strength
        body = abs(candle['close'] - candle['open'])
        body_ratio = body / candle_range if candle_range > 0 else 0
        
        # Adaptive threshold برای Body
        min_body_threshold = 0.55
        if volatility_regime == "HIGH_VOL":
            min_body_threshold = 0.45
        elif volatility_regime == "LOW_VOL":
            min_body_threshold = 0.65
        
        if body_ratio < min_body_threshold:
            return None  # Doji یا wick بسیار زیاد
        
        # Component 3: Direction Strength
        if candle['close'] > candle['open']:
            direction = "UP"
            upper_wick = candle['high'] - candle['close']
            lower_wick = candle['open'] - candle['low']
            wick_ratio = upper_wick / candle_range
            
            # اگر upper wick خیلی بزرگ، direction ضعیف
            if wick_ratio > 0.35:
                direction_strength = 0.70
            else:
                direction_strength = 0.95
        
        elif candle['close'] < candle['open']:
            direction = "DOWN"
            upper_wick = candle['high'] - candle['open']
            lower_wick = candle['close'] - candle['low']
            wick_ratio = lower_wick / candle_range
            
            if wick_ratio > 0.35:
                direction_strength = 0.70
            else:
                direction_strength = 0.95
        
        else:
            return None  # Doji محض
        
        # Component 4: Efficiency Score
        efficiency = (
            (np.clip(range_ratio / 2, 0, 1) * 0.4) +
            (np.clip(body_ratio, 0, 1) * 0.3) +
            (direction_strength * 0.3)
        )
        
        return {
            'type': f'IMPULSE_{direction}',
            'direction': direction,
            'range_atr': range_ratio,
            'body_ratio': body_ratio,
            'direction_strength': direction_strength,
            'efficiency': efficiency,
            'confidence': int(efficiency * 100),
            'range': candle_range,
            'body': body
        }
    
    # ═══════════════════════════════════════════════════════════════════════
    # IMPULSE SEQUENCE (Consecutive Impulses)
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_impulse_sequences(
        self,
        df: pd.DataFrame,
        atr_col: str = 'atr_14',
        vol_regime_col: str = 'volatility_regime'
    ) -> List[Dict]:
        """
        تشخیص دنباله‌های impulses
        
        مثال:
        [UP, UP, UP] = Bullish Displacement
        [DOWN, DOWN, DOWN] = Bearish Displacement
        
        هر sequence شامل:
        - تعداد candles
        - Total range
        - Average efficiency
        - Trend direction
        """
        
        sequences = []
        current_sequence = []
        last_direction = None
        
        for i in range(len(df)):
            candle = df.iloc[i]
            atr = candle[atr_col]
            vol_regime = candle[vol_regime_col]
            
            impulse = self.detect_impulse_candle(candle, atr, vol_regime)
            
            if impulse:
                direction = impulse['direction']
                
                # اگر جهت تغییر کرد، sequence جدید شروع کن
                if direction != last_direction:
                    
                    # اگر sequence قبلی وجود دارد، save کن
                    if current_sequence:
                        sequences.append(self._build_sequence(current_sequence, df))
                    
                    current_sequence = [{'index': i, **impulse}]
                    last_direction = direction
                
                else:
                    # ادامه دادن sequence
                    current_sequence.append({'index': i, **impulse})
        
        # آخرین sequence
        if current_sequence:
            sequences.append(self._build_sequence(current_sequence, df))
        
        return sequences
    
    def _build_sequence(self, candle_list: List[Dict], df: pd.DataFrame) -> Dict:
        """
        ساخت sequence object
        """
        
        total_range = sum(c['range'] for c in candle_list)
        total_body = sum(c['body'] for c in candle_list)
        avg_efficiency = np.mean([c['efficiency'] for c in candle_list])
        avg_body_ratio = np.mean([c['body_ratio'] for c in candle_list])
        
        direction = candle_list[0]['direction']
        start_idx = candle_list[0]['index']
        end_idx = candle_list[-1]['index']
        
        return {
            'direction': direction,
            'start_index': start_idx,
            'end_index': end_idx,
            'duration_candles': len(candle_list),
            'total_range': total_range,
            'total_body': total_body,
            'avg_efficiency': avg_efficiency,
            'avg_body_ratio': avg_body_ratio,
            'impulses': candle_list,
            'start_price': df.iloc[start_idx]['open'],
            'end_price': df.iloc[end_idx]['close'],
            'displacement': abs(df.iloc[end_idx]['close'] - df.iloc[start_idx]['open']),
            'strength': self._calculate_sequence_strength(candle_list)
        }
    
    def _calculate_sequence_strength(self, candle_list: List[Dict]) -> str:
        """
        تعیین قدرت sequence
        
        WEAK: 1-2 candles
        MEDIUM: 3-5 candles با efficiency خوب
        STRONG: 5+ candles با efficiency عالی
        """
        
        count = len(candle_list)
        avg_eff = np.mean([c['efficiency'] for c in candle_list])
        
        if count >= 5 and avg_eff >= 0.75:
            return "STRONG"
        elif count >= 3 and avg_eff >= 0.65:
            return "MEDIUM"
        else:
            return "WEAK"
    
    # ═══════════════════════════════════════════════════════════════════════
    # DISPLACEMENT SCORE
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_displacement_score(
        self,
        sequence: Dict,
        df: pd.DataFrame,
        atr_col: str = 'atr_14'
    ) -> float:
        """
        Displacement Score = نمره 0-100
        
        فرمول:
        score = (sequence_strength * 0.35) +
                (efficiency * 0.35) +
                (range_normalized * 0.30)
        
        این به ما می‌گوید:
        - 80-100: بسیار قوی، Institutional
        - 60-79: معمولی
        - 40-59: ضعیف
        - <40: تقریباً نویز
        """
        
        if sequence['duration_candles'] == 0:
            return 0
        
        # Component 1: Sequence Strength
        strength_map = {"STRONG": 1.0, "MEDIUM": 0.7, "WEAK": 0.4}
        strength_score = strength_map.get(sequence['strength'], 0.5)
        
        # Component 2: Average Efficiency
        efficiency_score = sequence['avg_efficiency']
        
        # Component 3: Range Normalized
        avg_atr = df.iloc[sequence['start_index']:sequence['end_index']][atr_col].mean()
        normalized_range = sequence['total_range'] / avg_atr if avg_atr > 0 else 0
        range_score = np.clip(normalized_range / 10, 0, 1)  # Normalize to 0-1
        
        # Component 4: Duration (تعداد candles)
        duration_score = np.clip(sequence['duration_candles'] / 10, 0, 1)
        
        # Combine
        final_score = (
            (strength_score * 0.25) +
            (efficiency_score * 0.25) +
            (range_score * 0.25) +
            (duration_score * 0.25)
        )
        
        return int(np.clip(final_score * 100, 0, 100))
    
    # ═══════════════════════════════════════════════════════════════════════
    # INEFFICIENCY (FVG-like Imbalances)
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_inefficiencies(
        self,
        df: pd.DataFrame,
        min_gap_atr: float = 0.5
    ) -> List[Dict]:
        """
        Inefficiency = FVG
        
        تعریف:
        - Bullish FVG: candle1.high < candle3.low
        - Bearish FVG: candle1.low > candle3.high
        
        محاسبه:
        gap_size / ATR >= min_gap_atr
        """
        
        inefficiencies = []
        
        for i in range(2, len(df) - 1):
            c1 = df.iloc[i - 2]
            c2 = df.iloc[i - 1]
            c3 = df.iloc[i]
            atr = df.iloc[i]['atr_14']
            
            # ========== BULLISH FVG ==========
            if c1['high'] < c3['low']:
                gap_size = c3['low'] - c1['high']
                gap_atr = gap_size / atr if atr > 0 else 0
                
                if gap_atr >= min_gap_atr:
                    
                    # بررسی Mitigation (آیا بعداً filled شد؟)
                    mitigated = False
                    mitigation_idx = None
                    for j in range(i + 1, min(len(df), i + 50)):
                        if df.iloc[j]['low'] <= c1['high']:
                            mitigated = True
                            mitigation_idx = j
                            break
                    
                    inefficiencies.append({
                        'type': 'BULLISH_FVG',
                        'index': i,
                        'gap_start': c1['high'],
                        'gap_end': c3['low'],
                        'gap_size': gap_size,
                        'gap_atr': gap_atr,
                        'mitigated': mitigated,
                        'mitigation_index': mitigation_idx,
                        'strength': 'STRONG' if gap_atr >= 1.5 else 'MEDIUM' if gap_atr >= 1.0 else 'WEAK'
                    })
            
            # ========== BEARISH FVG ==========
            if c1['low'] > c3['high']:
                gap_size = c1['low'] - c3['high']
                gap_atr = gap_size / atr if atr > 0 else 0
                
                if gap_atr >= min_gap_atr:
                    
                    mitigated = False
                    mitigation_idx = None
                    for j in range(i + 1, min(len(df), i + 50)):
                        if df.iloc[j]['high'] >= c1['low']:
                            mitigated = True
                            mitigation_idx = j
                            break
                    
                    inefficiencies.append({
                        'type': 'BEARISH_FVG',
                        'index': i,
                        'gap_start': c1['low'],
                        'gap_end': c3['high'],
                        'gap_size': gap_size,
                        'gap_atr': gap_atr,
                        'mitigated': mitigated,
                        'mitigation_index': mitigation_idx,
                        'strength': 'STRONG' if gap_atr >= 1.5 else 'MEDIUM' if gap_atr >= 1.0 else 'WEAK'
                    })
        
        return inefficiencies
    
    # ═══════════════════════════════════════════════════════════════════════
    # MAIN PIPELINE
    # ═══════════════════════════════════════════════════════════════════════
    
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        اعمال تمام محاسبات
        """
        
        # Step 1: Detect Impulse Candles
        df['is_impulse'] = False
        df['impulse_type'] = ''
        df['impulse_efficiency'] = 0.0
        
        sequences = self.detect_impulse_sequences(df)
        
        for seq in sequences:
            for imp in seq['impulses']:
                idx = imp['index']
                df.loc[df.index[idx], 'is_impulse'] = True
                df.loc[df.index[idx], 'impulse_type'] = imp['type']
                df.loc[df.index[idx], 'impulse_efficiency'] = imp['efficiency']
        
        # Step 2: Displacement Score
        df['displacement_score'] = 0
        for seq in sequences:
            score = self.calculate_displacement_score(seq, df)
            for idx in range(seq['start_index'], seq['end_index'] + 1):
                df.loc[df.index[idx], 'displacement_score'] = score
        
        # Step 3: Inefficiencies (FVG)
        inefficiencies = self.detect_inefficiencies(df)
        
        df['is_fvg'] = False
        df['fvg_type'] = ''
        df['fvg_gap_atr'] = 0.0
        
        for ineff in inefficiencies:
            idx = ineff['index']
            df.loc[df.index[idx], 'is_fvg'] = True
            df.loc[df.index[idx], 'fvg_type'] = ineff['type']
            df.loc[df.index[idx], 'fvg_gap_atr'] = ineff['gap_atr']
        
        # Store for next layers
        df.attrs['sequences'] = sequences
        df.attrs['inefficiencies'] = inefficiencies
        
        return df


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from pathlib import Path
    from layer1_market_data_engine import MarketDataEngine
    from layer2_structural_engine import StructuralEngine
    from layer3_liquidity_engine import LiquidityEngine
    
    # Load
    data_path = Path("data/abshodeNaghdi-1.csv")
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    df = df.set_index('timestamp')
    
    print("📊 بارگذاری داده کامل شد")
    
    # Layer 1
    engine1 = MarketDataEngine()
    df = engine1.process(df)
    print("✅ Layer 1")
    
    # Layer 2
    engine2 = StructuralEngine(min_strength=0.5)
    df = engine2.process(df)
    print("✅ Layer 2")
    
    # Layer 3
    engine3 = LiquidityEngine()
    df = engine3.process(df)
    print("✅ Layer 3")
    
    # Layer 4
    engine4 = DisplacementEngine()
    df = engine4.process(df)
    print("✅ Layer 4 (Displacement Engine)\n")
    
    # Results
    impulses = df[df['is_impulse']][['close', 'impulse_type', 'impulse_efficiency', 'displacement_score']].tail(15)
    print("⚡ Recent Impulses:")
    print(impulses)
    
    fvgs = df[df['is_fvg']][['close', 'fvg_type', 'fvg_gap_atr']].tail(10)
    print("\n📊 Recent FVGs:")
    print(fvgs)
