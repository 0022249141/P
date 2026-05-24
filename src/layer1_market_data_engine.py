"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 1: MARKET DATA ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

توضیح فارسی:
این لایه تمام داده‌های بازار را نرمال‌سازی می‌کند تا یک بستر یکسان برای 
تحلیل داشته باشیم. هر بازار و هر timeframe متفاوت است، اما ما باید 
آن‌ها را به یک scale یکسان تبدیل کنیم.

مثال:
- اگر EURUSD کندل اول 1.0850 باشد
- و XAU/USD کندل اول 2050 باشد
- ما نمی‌تونیم از 0.05 به عنوان threshold برای هر دو استفاده کنیم
- باید از ATR استفاده کنیم (Adaptive Threshold Range)

اصول:
1. ATR (Average True Range) = volatility سنج
2. Normalization = تقسیم بر ATR
3. Percentile = نسبتی از تاریخچه
4. Z-Score = چند استاندارد deviation فاصله است
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional


class MarketDataEngine:
    """
    بستر داده‌های بازار - نرمال‌سازی شده
    """
    
    def __init__(self, lookback: int = 50):
        """
        lookback: چند کندل قبلی را برای محاسبه statistics استفاده کنیم؟
        """
        self.lookback = lookback
    
    # ═══════════════════════════════════════════════════════════════════════
    # TRUE RANGE (بدون Lag، بدون Repaint)
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_true_range(self, df: pd.DataFrame) -> pd.Series:
        """
        True Range (TR) = بالاترین فاصله بین سه مقدار:
        
        1. high - low (محدوده کندل فعلی)
        2. |high - close_prev| (gap از بسته قبلی)
        3. |low - close_prev| (gap از بسته قبلی)
        
        فرمول ریاضی:
        TR = max(H - L, |H - C_prev|, |L - C_prev|)
        
        چرا؟ زیرا بازار ممکن است gap بخورد!
        """
        high_low = df['high'] - df['low']
        high_close_prev = abs(df['high'] - df['close'].shift(1))
        low_close_prev = abs(df['low'] - df['close'].shift(1))
        
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        return tr
    
    # ═══════════════════════════════════════════════════════════════════════
    # ATR (Average True Range) - Adaptive Volatility
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        ATR = میانگین TR در آخر N کندل
        
        ATR(14) معمول است (14 کندل)
        اما در بازارهای volatile تر، می‌تواند بالاتر باشد
        
        فرمول:
        ATR = SMA(TR, 14)
        """
        tr = self.calculate_true_range(df)
        atr = tr.rolling(window=period).mean()
        return atr
    
    # ═══════════════════════════════════════════════════════════════════════
    # VOLATILITY REGIME (Low/Normal/High)
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_volatility_regime(self, df: pd.DataFrame, atr_col: str = 'atr_14') -> pd.Series:
        """
        Volatility Regime = وضعیت volatility بازار
        
        - LOW_VOL: قیمت ساکن است، تحرک کم
        - NORMAL: وضعیت عادی
        - HIGH_VOL: بازار قلق‌وار است، نوسان‌ها شدید
        
        این برای threshold‌ها مهم است:
        - در HIGH_VOL، threshold را بزرگتر می‌کنیم
        - در LOW_VOL، threshold را کوچک‌تر می‌کنیم
        
        روش:
        1. ATR آخر 50 کندل را بگیر
        2. 20th و 80th percentile بگیر
        3. ATR کنونی را مقایسه کن
        """
        atr_history = df[atr_col].rolling(window=self.lookback).std()
        
        p20 = atr_history.rolling(window=self.lookback).quantile(0.20)
        p80 = atr_history.rolling(window=self.lookback).quantile(0.80)
        
        regime = pd.Series("NORMAL", index=df.index)
        regime[df[atr_col] < p20] = "LOW_VOL"
        regime[df[atr_col] > p80] = "HIGH_VOL"
        
        return regime
    
    # ═══════════════════════════════════════════════════════════════════════
    # NORMALIZED RANGE (نرمال‌شده بر اساس ATR)
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_normalized_range(self, df: pd.DataFrame, atr_col: str = 'atr_14') -> pd.Series:
        """
        Normalized Range = (High - Low) / ATR
        
        این یک عدد بدون واحد است.
        
        مثال:
        - اگر EURUSD: range = 0.0050، ATR = 0.0080
          normalized = 0.0050 / 0.0080 = 0.625
        
        - اگر XAU/USD: range = 25، ATR = 40
          normalized = 25 / 40 = 0.625
        
        حالا هر دو یک معنی دارند!
        """
        price_range = df['high'] - df['low']
        normalized = price_range / df[atr_col].replace(0, np.nan)
        return normalized.fillna(0)
    
    # ═══════════════════════════════════════════════════════════════════════
    # BODY RATIO (نسبت بدنه به کل range)
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_body_ratio(self, df: pd.DataFrame) -> pd.Series:
        """
        Body Ratio = |Close - Open| / (High - Low)
        
        این نشان می‌دهد کندل چقدر قوی است:
        
        - 0.9 = کندل تقریباً pure است (بسیار قوی)
        - 0.5 = نیمی مقاومت، نیمی wick (متوسط)
        - 0.1 = خیلی دور، زیاد wick (ضعیف، doji)
        """
        body = abs(df['close'] - df['open'])
        range_val = df['high'] - df['low']
        
        body_ratio = body / range_val.replace(0, np.nan)
        return body_ratio.fillna(0)
    
    # ═══════════════════════════════════════════════════════════════════════
    # VOLUME ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_volume_ratio(self, df: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """
        Volume Ratio = کندل فعلی / میانگین volume آخر N کندل
        
        - 1.0 = volume عادی
        - 1.5 = 50% بیشتر از متوسط (قوی!)
        - 0.5 = 50% کمتر از متوسط (ضعیف)
        """
        avg_volume = df['volume'].rolling(window=lookback).mean()
        volume_ratio = df['volume'] / avg_volume.replace(0, np.nan)
        return volume_ratio.fillna(1.0)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Z-SCORE (چند std dev فاصله است؟)
    # ═══════════════════════════════════════════════════════════════════════
    
    def calculate_zscore(self, series: pd.Series, lookback: int = 20) -> pd.Series:
        """
        Z-Score = (Value - Mean) / Std Dev
        
        این یک statistical measure است:
        - Z-Score = 0 = میانگین
        - Z-Score = 2 = 2 استاندارد deviation بالاتر
        - Z-Score = -2 = 2 استاندارد deviation پایین‌تر
        
        برای تشخیص anomalies مفید است!
        """
        mean = series.rolling(window=lookback).mean()
        std = series.rolling(window=lookback).std()
        
        zscore = (series - mean) / std.replace(0, np.nan)
        return zscore.fillna(0)
    
    # ═══════════════════════════════════════════════════════════════════════
    # SESSION DETECTION (London/NY/Tokyo/etc)
    # ═══════════════════════════════════════════════════════════════════════
    
    def detect_session(self, timestamp: pd.Timestamp) -> str:
        """
        تشخیص session بر اساس ساعت (UTC)
        
        - Tokyo: 00:00 - 09:00 UTC
        - London: 08:00 - 17:00 UTC
        - NewYork: 13:00 - 22:00 UTC
        """
        hour = timestamp.hour
        
        if 0 <= hour < 9:
            return "TOKYO"
        elif 8 <= hour < 17:
            return "LONDON"
        elif 13 <= hour < 22:
            return "NEWYORK"
        else:
            return "OVERLAP"
    
    # ═══════════════════════════════════════════════════════════════════════
    # MAIN PIPELINE
    # ═══════════════════════════════════════════════════════════════════════
    
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        تمام محاسبات را اعمال کن
        """
        # Step 1: True Range
        df['true_range'] = self.calculate_true_range(df)
        
        # Step 2: ATR
        df['atr_14'] = self.calculate_atr(df, period=14)
        df['atr_14'] = df['atr_14'].fillna(method='bfill')
        
        # Step 3: Volatility Regime
        df['volatility_regime'] = self.calculate_volatility_regime(df)
        
        # Step 4: Normalized Range
        df['normalized_range'] = self.calculate_normalized_range(df)
        
        # Step 5: Body Ratio
        df['body_ratio'] = self.calculate_body_ratio(df)
        
        # Step 6: Volume Ratio
        if 'volume' in df.columns:
            df['volume_ratio'] = self.calculate_volume_ratio(df)
        else:
            df['volume_ratio'] = 1.0
        
        # Step 7: Z-Scores
        df['range_zscore'] = self.calculate_zscore(df['high'] - df['low'])
        df['volume_zscore'] = self.calculate_zscore(df['volume']) if 'volume' in df.columns else 0
        
        # Step 8: Session
        df['session'] = df.index.map(lambda x: self.detect_session(x))
        
        return df


# ═══════════════════════════════════════════════════════════════════════════
# TEST & USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # بارگذاری داده
    data_path = Path("data/abshodeNaghdi-1.csv")
    
    if not data_path.exists():
        print(f"❌ فایل {data_path} پیدا نشد")
        sys.exit(1)
    
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    df = df.set_index('timestamp')
    
    print("📊 بارگذاری داده کامل شد")
    print(f"تعداد کندل: {len(df)}")
    print(f"ستون‌ها: {list(df.columns)}\n")
    
    # اعمال Layer 1
    engine = MarketDataEngine(lookback=50)
    df = engine.process(df)
    
    print("✅ Layer 1 (Market Data Engine) اعمال شد\n")
    
    # نمایش نتایج
    print(df[['close', 'atr_14', 'volatility_regime', 'normalized_range', 'body_ratio']].tail(10))
    
    # ذخیره کردن
    output_path = Path("data/layer1_processed/abshodeNaghdi-1.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path)
    
    print(f"\n✅ نتیجه در {output_path} ذخیره شد")
