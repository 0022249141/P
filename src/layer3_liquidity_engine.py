"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 3: LIQUIDITY ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

توضیح فارسی:
این لایه جایی‌ها را پیدا می‌کند که بازار liquidity جمع می‌کند!

1. EQUAL HIGHS/LOWS = درجات یکسان
   - قیمت دو بار یا بیش‌تر به یک level رفت
   - این جایی است که خریداران/فروشندگان orders می‌گذارند

2. SWEEP = قیمت این levels را می‌خورد
   - مثل "Liquidity Grab"
   - Institutions بازار را sweep می‌کنند تا liquidity جمع کنند

3. RESTING LIQUIDITY = درجات که아هنوز sweep نشده
   - خطرناک! Institutions می‌توانند آن را بخورند

4. INDUCEMENT = قیمت آن level را اندکی بالاتر/پایین‌تر برد
   - معمولاً پیش از reversal
   - مثل "tease"

مهم: تمام محاسبات NORMALIZED هستند!
از ATR استفاده می‌کنیم، نه fixed thresholds.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional


class LiquidityEngine:
    """
    تشخیص liquidity zones و sweeps
    """
    
    def __init__(self, tolerance_atr: float = 0.15):
        """
        tolerance_atr: چقدر tolerance برای equal highs/lows؟
        مثال: 0.15 = 15% ATR
        """
        self.tolerance_atr = tolerance_atr
    
    # ═══════════════════════════════════════════════════════════════════════
    # EQUAL HIGHS/LOWS (Normalized)
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_equal_levels(
        self,
        df: pd.DataFrame,
        lookback: int = 20,
        atr_col: str = 'atr_14'
    ) -> Tuple[pd.Series, pd.Series]:
        """
        تشخیص درجات یکسان (normalized)
        
        روش:
        1. برای هر کندل، ببین چند بار این level قبل‌تر دیده شده
        2. اگر بیش‌تر از دو بار، equal level است
        
        Tolerance = tolerance_atr * ATR
        """
        
        equal_highs = pd.Series(0, index=df.index)
        equal_lows = pd.Series(0, index=df.index)
        
        for i in range(lookback, len(df)):
            current_high = df.iloc[i]['high']
            current_low = df.iloc[i]['low']
            tolerance = self.tolerance_atr * df.iloc[i][atr_col]
            
            # بررسی highs
            count_highs = 0
            for j in range(i - lookback, i):
                past_high = df.iloc[j]['high']
                if abs(current_high - past_high) <= tolerance:
                    count_highs += 1
            
            if count_highs >= 2:
                equal_highs.iloc[i] = count_highs
            
            # بررسی lows
            count_lows = 0
            for j in range(i - lookback, i):
                past_low = df.iloc[j]['low']
                if abs(current_low - past_low) <= tolerance:
                    count_lows += 1
            
            if count_lows >= 2:
                equal_lows.iloc[i] = count_lows
        
        return equal_highs, equal_lows
    
    # ═══════════════════════════════════════════════════════════════════════
    # SWEEP DETECTION
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_sweeps(
        self,
        df: pd.DataFrame,
        swing_highs: List[Dict],
        swing_lows: List[Dict],
        atr_col: str = 'atr_14',
        lookback_sweep: int = 5
    ) -> List[Dict]:
        """
        Sweep = قیمت یک swing level را touch کند و reverse شود
        
        شرایط:
        1. قیمت swing level را برسد (یا بگذرد)
        2. در بعدی، reverse شود
        3. تایید شود (volume، body، etc)
        """
        
        sweeps = []
        
        for i in range(1, len(df) - 1):
            current = df.iloc[i]
            next_candle = df.iloc[i + 1]
            
            # ========== BULLISH SWEEP ==========
            for sl in swing_lows:
                if i <= sl['index']:
                    continue
                
                # آیا low این کندل، swing low را touch کرد؟
                if current['low'] <= sl['price']:
                    
                    # آیا بعدی reverse شد؟
                    if next_candle['close'] > current['close']:
                        
                        # محاسبه metrics
                        depth_pips = sl['price'] - current['low']
                        depth_atr = depth_pips / current[atr_col]
                        
                        # Volume anomaly؟
                        avg_vol = df.iloc[max(0, i - 20):i]['volume'].mean()
                        volume_ratio = current['volume'] / avg_vol if avg_vol > 0 else 1
                        
                        # Mitigation score
                        mitigation_score = self._calculate_mitigation_score(
                            current, sl['price'], atr_col
                        )
                        
                        sweeps.append({
                            'type': 'BULLISH_SWEEP',
                            'index': i,
                            'timestamp': df.index[i],
                            'target_level': sl['price'],
                            'depth_pips': depth_pips,
                            'depth_atr': depth_atr,
                            'volume_ratio': volume_ratio,
                            'mitigation_score': mitigation_score,
                            'swing_ref_index': sl['index'],
                            'confirmation_index': i + 1,
                            'confidence': self._calculate_sweep_confidence(
                                depth_atr, volume_ratio, mitigation_score
                            )
                        })
            
            # ========== BEARISH SWEEP ==========
            for sh in swing_highs:
                if i <= sh['index']:
                    continue
                
                # آیا high این کندل، swing high را touch کرد؟
                if current['high'] >= sh['price']:
                    
                    # آیا بعدی reverse شد؟
                    if next_candle['close'] < current['close']:
                        
                        depth_pips = current['high'] - sh['price']
                        depth_atr = depth_pips / current[atr_col]
                        
                        avg_vol = df.iloc[max(0, i - 20):i]['volume'].mean()
                        volume_ratio = current['volume'] / avg_vol if avg_vol > 0 else 1
                        
                        mitigation_score = self._calculate_mitigation_score(
                            current, sh['price'], atr_col
                        )
                        
                        sweeps.append({
                            'type': 'BEARISH_SWEEP',
                            'index': i,
                            'timestamp': df.index[i],
                            'target_level': sh['price'],
                            'depth_pips': depth_pips,
                            'depth_atr': depth_atr,
                            'volume_ratio': volume_ratio,
                            'mitigation_score': mitigation_score,
                            'swing_ref_index': sh['index'],
                            'confirmation_index': i + 1,
                            'confidence': self._calculate_sweep_confidence(
                                depth_atr, volume_ratio, mitigation_score
                            )
                        })
        
        return sweeps
    
    # ═══════════════════════════════════════════════════════════════════════
    # MITIGATION SCORE
    # ═══════════════════════════════════════════════════════════════════════
    
    def _calculate_mitigation_score(
        self,
        candle: pd.Series,
        target_level: float,
        atr_col: str
    ) -> float:
        """
        Mitigation score = چقدر قوی است sweep؟
        
        مثل: آیا close به target رسید؟ یا فقط wicked؟
        """
        
        if candle['high'] >= target_level and candle['close'] > target_level:
            return 0.95  # Strong - close بالاتر از target
        elif candle['high'] >= target_level:
            return 0.70  # Medium - فقط wick
        else:
            return 0.40  # Weak - فقط به آن نزدیک شد
    
    def _calculate_sweep_confidence(
        self,
        depth_atr: float,
        volume_ratio: float,
        mitigation_score: float
    ) -> float:
        """
        Confidence score (0-100) برای sweep
        
        فرمول:
        confidence = (depth_atr * 0.3) + (volume * 0.4) + (mitigation * 0.3)
        """
        
        # Depth: اگر خیلی عمیق، کمتر معتبر
        depth_score = 100 * np.exp(-0.5 * max(0, depth_atr - 1))
        if depth_atr > 5:
            depth_score = 20
        
        # Volume: اگر volume زیاد، معتبرتر
        volume_score = min(100, (volume_ratio - 0.5) * 50)
        
        # Mitigation: مستقیم
        mitigation_score_val = mitigation_score * 100
        
        confidence = (
            (depth_score * 0.3) +
            (volume_score * 0.4) +
            (mitigation_score_val * 0.3)
        )
        
        return int(np.clip(confidence, 0, 100))
    
    # ═══════════════════════════════════════════════════════════════════════
    # RESTING LIQUIDITY
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_resting_liquidity(
        self,
        swing_highs: List[Dict],
        swing_lows: List[Dict],
        sweeps: List[Dict]
    ) -> List[Dict]:
        """
        Resting Liquidity = درجاتی که아هنوز sweep نشده
        
        این درجات ریسک‌دار هستند! (خطر ک consumption)
        """
        
        resting = []
        swept_levels = [s['target_level'] for s in sweeps]
        
        # Check Swing Highs
        for sh in swing_highs:
            is_swept = any(
                abs(sh['price'] - swept) < 0.001
                for swept in swept_levels
            )
            
            if not is_swept:
                resting.append({
                    'type': 'RESTING_HIGH',
                    'price': sh['price'],
                    'swing_ref': sh,
                    'risk_level': 'MEDIUM'
                })
        
        # Check Swing Lows
        for sl in swing_lows:
            is_swept = any(
                abs(sl['price'] - swept) < 0.001
                for swept in swept_levels
            )
            
            if not is_swept:
                resting.append({
                    'type': 'RESTING_LOW',
                    'price': sl['price'],
                    'swing_ref': sl,
                    'risk_level': 'MEDIUM'
                })
        
        return resting
    
    # ═══════════════════════════════════════════════════════════════════════
    # MAIN PIPELINE
    # ═══════════════════════════════════════════════════════════════════════
    
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        اعمال تمام محاسبات
        """
        
        # Retrieve swing data from Layer 2
        swing_highs = df.attrs.get('swing_highs', [])
        swing_lows = df.attrs.get('swing_lows', [])
        
        # Step 1: Equal Highs/Lows
        df['equal_highs_count'], df['equal_lows_count'] = self.detect_equal_levels(df)
        
        # Step 2: Sweeps
        sweeps = self.detect_sweeps(df, swing_highs, swing_lows)
        
        # Add sweep data to dataframe
        df['is_sweep'] = False
        df['sweep_type'] = ''
        df['sweep_confidence'] = 0
        
        for sweep in sweeps:
            df.loc[df.index[sweep['index']], 'is_sweep'] = True
            df.loc[df.index[sweep['index']], 'sweep_type'] = sweep['type']
            df.loc[df.index[sweep['index']], 'sweep_confidence'] = sweep['confidence']
        
        # Step 3: Resting Liquidity
        resting = self.detect_resting_liquidity(swing_highs, swing_lows, sweeps)
        
        # Store for next layers
        df.attrs['sweeps'] = sweeps
        df.attrs['resting_liquidity'] = resting
        
        return df


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from pathlib import Path
    from layer1_market_data_engine import MarketDataEngine
    from layer2_structural_engine import StructuralEngine
    
    # Load data
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
    print("✅ Layer 2 اعمال شد")
    
    # Layer 3
    engine3 = LiquidityEngine()
    df = engine3.process(df)
    print("✅ Layer 3 اعمال شد\n")
    
    # Display results
    sweep_data = df[df['is_sweep']][['close', 'sweep_type', 'sweep_confidence']].tail(10)
    print("🔍 Recent Sweeps:")
    print(sweep_data)
    
    equal_levels = df[df['equal_highs_count'] > 0][['close', 'equal_highs_count']].tail(10)
    print("\n📍 Equal Highs:")
    print(equal_levels)
