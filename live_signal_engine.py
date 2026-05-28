# -*- coding: utf-8 -*-
"""
live_signal_engine.py — موتور تولید سیگنال‌های زنده
تکامل یافته با SMC/RTM/Liquidity/Regime
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from market_params import get_market_params, VALID_REGIMES

class LiveSignalEngine:
    """موتور تولید سیگنال‌های زنده برای تمام بازارها"""
    
    def __init__(self, market_name: str):
        self.market_name = market_name
        self.params = get_market_params(market_name)
        self.df = None
        self.signals = []
        
    def load_data(self, csv_path: str) -> None:
        """بارگذاری داده‌های OHLCV"""
        self.df = pd.read_csv(csv_path)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        self.df = self.df.sort_values('timestamp').reset_index(drop=True)
        
    def add_atr(self, period: int = 14) -> None:
        """افزودن ATR"""
        if self.df is None:
            return
        
        high, low, close = self.df['high'], self.df['low'], self.df['close']
        tr = np.maximum(
            high - low,
            np.abs(high - close.shift(1)),
            np.abs(low - close.shift(1))
        )
        self.df['ATR'] = tr.ewm(span=period, adjust=False).mean()
        
    def add_regime(self) -> None:
        """تشخیص رژیم بازار"""
        if self.df is None or 'ATR' not in self.df.columns:
            return
        
        self.df['regime'] = 'Unknown'
        atr_ma = self.df['ATR'].rolling(20, min_periods=1).mean()
        
        # Compression
        self.df.loc[self.df['ATR'] < self.params['compression_atr_ratio'] * atr_ma, 'regime'] = 'Compressing'
        
        # Ranging
        lookback = self.params['ranging_lookback']
        for i in range(lookback, len(self.df)):
            window = self.df.iloc[i-lookback:i+1]
            range_pct = (window['high'].max() - window['low'].min()) / window['close'].mean() * 100
            if range_pct < self.params['ranging_max_range_pct']:
                self.df.loc[i, 'regime'] = 'Ranging'
        
        # Trending
        for i in range(lookback, len(self.df)):
            window = self.df.iloc[i-lookback:i+1]
            close = window['close']
            if close.iloc[-1] > close.iloc[0] * 1.02:
                self.df.loc[i, 'regime'] = 'Trending'
            elif close.iloc[-1] < close.iloc[0] * 0.98:
                self.df.loc[i, 'regime'] = 'Trending'
    
    def detect_sweeps(self) -> None:
        """تشخیص Sweep Patterns"""
        if self.df is None or 'ATR' not in self.df.columns:
            return
        
        self.df['sweep_score'] = 0.0
        self.df['sweep_type'] = 'none'
        
        lookback = 20
        threshold = self.params['sweep_threshold_atr']
        
        for i in range(1, len(self.df)):
            if i < lookback:
                continue
            
            window = self.df.iloc[i-lookback:i+1]
            last_high = window['high'].iloc[:-1].max()
            last_low = window['low'].iloc[:-1].min()
            atr = self.df['ATR'].iloc[i]
            
            # Bearish Sweep
            if self.df['high'].iloc[i] > last_high and self.df['close'].iloc[i] < last_high:
                penetration = (self.df['high'].iloc[i] - last_high) / atr
                wick = (self.df['high'].iloc[i] - self.df['close'].iloc[i]) / (self.df['high'].iloc[i] - self.df['low'].iloc[i] + 1e-10)
                score = min((penetration * 0.5 + wick * 0.5) / threshold, 1.0)
                self.df.loc[i, 'sweep_score'] = score
                self.df.loc[i, 'sweep_type'] = 'bearish'
            
            # Bullish Sweep
            elif self.df['low'].iloc[i] < last_low and self.df['close'].iloc[i] > last_low:
                penetration = (last_low - self.df['low'].iloc[i]) / atr
                wick = (self.df['close'].iloc[i] - self.df['low'].iloc[i]) / (self.df['high'].iloc[i] - self.df['low'].iloc[i] + 1e-10)
                score = min((penetration * 0.5 + wick * 0.5) / threshold, 1.0)
                self.df.loc[i, 'sweep_score'] = score
                self.df.loc[i, 'sweep_type'] = 'bullish'
    
    def generate_signals(self) -> pd.DataFrame:
        """تولید سیگنال‌های نهایی"""
        if self.df is None:
            return pd.DataFrame()
        
        signals = []
        
        for i in range(1, len(self.df)):
            row = self.df.iloc[i]
            
            if pd.isna(row['sweep_score']) or row['sweep_score'] == 0:
                continue
            
            regime = row.get('regime', 'Unknown')
            if regime not in VALID_REGIMES:
                continue
            
            # Long Signal
            if row['sweep_type'] == 'bullish' and row['sweep_score'] >= 0.65:
                entry_price = row['close']
                sl_price = row['low'] - self.params['atr_sl_mult'] * row['ATR']
                tp_price = entry_price + (entry_price - sl_price) * self.params['rr_ratio']
                
                signals.append({
                    'timestamp': row['timestamp'],
                    'market': self.market_name,
                    'direction': 'LONG',
                    'entry_price': entry_price,
                    'sl_price': sl_price,
                    'tp_price': tp_price,
                    'sweep_confidence': row['sweep_score'],
                    'regime': regime,
                    'atr': row['ATR'],
                })
            
            # Short Signal
            elif row['sweep_type'] == 'bearish' and row['sweep_score'] >= 0.65:
                entry_price = row['close']
                sl_price = row['high'] + self.params['atr_sl_mult'] * row['ATR']
                tp_price = entry_price - (sl_price - entry_price) * self.params['rr_ratio']
                
                signals.append({
                    'timestamp': row['timestamp'],
                    'market': self.market_name,
                    'direction': 'SHORT',
                    'entry_price': entry_price,
                    'sl_price': sl_price,
                    'tp_price': tp_price,
                    'sweep_confidence': row['sweep_score'],
                    'regime': regime,
                    'atr': row['ATR'],
                })
        
        return pd.DataFrame(signals)
    
    def analyze(self, csv_path: str) -> pd.DataFrame:
        """تحلیل کامل و تولید سیگنال‌ها"""
        self.load_data(csv_path)
        self.add_atr()
        self.add_regime()
        self.detect_sweeps()
        return self.generate_signals()
