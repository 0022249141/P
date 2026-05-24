# config.py — مرکز یکپارچه پارامترهای پروژه
from market_params import (
    MARKET_ABSHODE, MARKET_HARAT, MARKET_XAUUSD,
    LIQUIDITY_THRESHOLDS, BOS_MIN_DISPLACEMENT,
    VALID_REGIMES, DEFAULT_SEED, DEFAULT_SIMULATIONS,
    DEFAULT_MAX_HOLDING_CANDLES, DEFAULT_MIN_EV,
    MIN_CROSS_MARKET_SCORE, TIMEFRAMES_BY_MARKET,
)

MARKET_ALIASES = {
    "abshodeh": "AbshodeNaghdi",
    "harat": "HaratUSD",
    "xauusd": "XAUUSD",
    "abshodeNaghdi": "AbshodeNaghdi",
    "haratFardayi": "HaratUSD",
    "XAU_USD": "XAUUSD",
}

BACKTEST_DEFAULTS = {
    "max_holding_candles": DEFAULT_MAX_HOLDING_CANDLES,
    "min_ev": DEFAULT_MIN_EV,
    "seed": DEFAULT_SEED,
    "simulations": DEFAULT_SIMULATIONS,
}

def get_market_config(name: str):
    key = MARKET_ALIASES.get(name, name)
    if key in {"AbshodeNaghdi", "abshodeh"}:
        return MARKET_ABSHODE
    elif key in {"HaratUSD", "harat"}:
        return MARKET_HARAT
    else:
        return MARKET_XAUUSD