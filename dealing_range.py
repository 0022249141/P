# 09_dealing_range.py — محاسبه محدوده معاملاتی (Dealing Range)
import pandas as pd
import numpy as np

def _get_default_lookback(market_name: str) -> int:
    try:
        from src.market_params import MARKETS
        alias = {"XAUUSD":"xauusd","AbshodeNaghdi":"abshodeh","HaratUSD":"harat"}
        key = alias.get(market_name, market_name)
        return MARKETS.get(key, MARKETS["xauusd"])["dealing_range"]["lookback_candles_daily"]
    except:
        return {"AbshodeNaghdi":20,"HaratUSD":15,"XAUUSD":20}.get(market_name,20)

def detect_dealing_range(df: pd.DataFrame, market_name: str = "XAUUSD", lookback: int = None) -> pd.DataFrame:
    df = df.copy()
    if lookback is None:
        lookback = _get_default_lookback(market_name)

    df['dr_high'] = df['high'].rolling(window=lookback, min_periods=1).max()
    df['dr_low']  = df['low'].rolling(window=lookback, min_periods=1).min()
    df['dr_midpoint'] = (df['dr_high'] + df['dr_low']) / 2
    dr_range = df['dr_high'] - df['dr_low']
    df['dr_premium']  = df['dr_low'] + 0.618 * dr_range
    df['dr_discount'] = df['dr_low'] + 0.382 * dr_range
    df['position_pct'] = (df['close'] - df['dr_low']) / dr_range * 100
    df['position_pct'] = df['position_pct'].clip(0, 100)
    df['in_premium']  = df['close'] > df['dr_premium']
    df['in_discount'] = df['close'] < df['dr_discount']
    return df