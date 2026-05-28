# -*- coding: utf-8 -*-
"""
market_params.py — مرکز پارامترهای تمام بازارها
استاندارد برای SMC/RTM/Liquidity/Regime
"""

# ╔════════════════════════════════════════════════════════════════╗
# ║ 1. XAUUSD (طلا - بازار جهانی)                                 ║
# ╚════════════════════════════════════════════════════════════════╝

MARKET_XAUUSD = {
    "name": "XAUUSD",
    "display_name": "🟡 طلا (XAUUSD)",
    "currency": "USD",
    "tick_size": 0.01,
    "contract_size": 1.0,
    
    # ATR & Volatility
    "atr_period": 14,
    "atr_threshold_low": 2.0,
    "atr_threshold_high": 8.0,
    "compression_atr_ratio": 0.4,
    
    # SMC Pattern
    "sweep_threshold_atr": 0.5,
    "penetration_min": 0.3,
    "rejection_wick_min": 0.5,
    "volume_multiplier": 1.2,
    
    # Liquidity
    "liquidity_pool_touches": 2,
    "liquidity_decay_bars": 100,
    "fvg_min_gap_pct": 0.08,
    
    # Order Blocks
    "ob_min_body_pct": 0.0020,
    "ob_lookback": 50,
    
    # Regime
    "trending_min_bos": 3,
    "ranging_max_range_pct": 2.0,
    "ranging_lookback": 20,
    "manipulation_max_candles": 8,
    
    # Retail Trap
    "retail_trap_window": 3,
    "doji_body_max_pct": 0.001,
    "exhaustion_volume_mult": 1.5,
    
    # Trade
    "risk_percent": 1.0,
    "account_balance": 10000,
    "atr_sl_mult": 1.5,
    "rr_ratio": 1.5,
    "max_holding_candles": 96,
    "min_ev": 0.05,
}

# ╔════════════════════════════════════════════════════════════════╗
# ║ 2. HaratUSD (هرات - بازار انجمن ایران)                        ║
# ╚════════════════════════════════════════════════════════════════╝

MARKET_HARAT = {
    "name": "HaratUSD",
    "display_name": "💳 هرات (USD)",
    "currency": "IRR",
    "tick_size": 1.0,
    "contract_size": 1.0,
    
    # ATR & Volatility
    "atr_period": 14,
    "atr_threshold_low": 50.0,
    "atr_threshold_high": 300.0,
    "compression_atr_ratio": 0.4,
    
    # SMC Pattern
    "sweep_threshold_atr": 0.3,  # حساس‌تر
    "penetration_min": 0.25,
    "rejection_wick_min": 0.4,
    "volume_multiplier": 1.3,
    
    # Liquidity
    "liquidity_pool_touches": 3,  # بیشتر
    "liquidity_decay_bars": 80,
    "fvg_min_gap_pct": 0.10,
    
    # Order Blocks
    "ob_min_body_pct": 0.0015,
    "ob_lookback": 40,
    
    # Regime
    "trending_min_bos": 2,  # کمتر
    "ranging_max_range_pct": 3.0,
    "ranging_lookback": 15,
    "manipulation_max_candles": 6,  # کمتر
    
    # Retail Trap
    "retail_trap_window": 3,
    "doji_body_max_pct": 0.001,
    "exhaustion_volume_mult": 1.6,
    
    # Trade
    "risk_percent": 1.0,
    "account_balance": 10000,
    "atr_sl_mult": 1.5,
    "rr_ratio": 1.5,
    "max_holding_candles": 72,
    "min_ev": 0.05,
}

# ╔════════════════════════════════════════════════════════════════╗
# ║ 3. AbshodeNaghdi (ابشو نقدی - بازار فوری ایران)               ║
# ╚════════════════════════════════════════════════════════════════╝

MARKET_ABSHODE = {
    "name": "AbshodeNaghdi",
    "display_name": "🔸 ابشو نقدی",
    "currency": "IRR",
    "tick_size": 100.0,
    "contract_size": 1.0,
    
    # ATR & Volatility
    "atr_period": 14,
    "atr_threshold_low": 40.0,
    "atr_threshold_high": 250.0,
    "compression_atr_ratio": 0.35,
    
    # SMC Pattern
    "sweep_threshold_atr": 0.4,
    "penetration_min": 0.3,
    "rejection_wick_min": 0.5,
    "volume_multiplier": 1.25,
    
    # Liquidity
    "liquidity_pool_touches": 2,
    "liquidity_decay_bars": 90,
    "fvg_min_gap_pct": 0.09,
    
    # Order Blocks
    "ob_min_body_pct": 0.0020,
    "ob_lookback": 45,
    
    # Regime
    "trending_min_bos": 3,
    "ranging_max_range_pct": 2.5,
    "ranging_lookback": 18,
    "manipulation_max_candles": 7,
    
    # Retail Trap
    "retail_trap_window": 3,
    "doji_body_max_pct": 0.0008,
    "exhaustion_volume_mult": 1.5,
    
    # Trade
    "risk_percent": 1.0,
    "account_balance": 10000,
    "atr_sl_mult": 1.5,
    "rr_ratio": 1.5,
    "max_holding_candles": 80,
    "min_ev": 0.05,
}

# ═══════════════════════════════════════════════════════════════

VALID_REGIMES = ["Compressing", "Ranging", "Trending", "Manipulation"]
VALID_DIRECTIONS = ["LONG", "SHORT", "NEUTRAL"]

TIMEFRAMES_BY_MARKET = {
    "XAUUSD": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
    "HaratUSD": ["M5", "M15", "M30", "H1", "H4", "D1"],
    "AbshodeNaghdi": ["M5", "M15", "M30", "H1", "H4"],
}

DEFAULT_SEED = 42
DEFAULT_SIMULATIONS = 1000
DEFAULT_MAX_HOLDING_CANDLES = 96
DEFAULT_MIN_EV = 0.05

MIN_CROSS_MARKET_SCORE = 0.65

TRADING_SESSIONS = {
    "HaratUSD": {
        "morning": ("08:30", "12:30"),
        "afternoon": ("14:00", "17:30"),
    },
    "AbshodeNaghdi": {
        "morning": ("08:30", "12:30"),
        "afternoon": ("14:00", "17:30"),
    },
}

BOS_MIN_DISPLACEMENT = {
    "XAUUSD": 0.5,
    "HaratUSD": 0.3,
    "AbshodeNaghdi": 0.4,
}

LIQUIDITY_THRESHOLDS = {
    "XAUUSD": {"high": 8.0, "medium": 3.0, "low": 0.5},
    "HaratUSD": {"high": 300.0, "medium": 100.0, "low": 20.0},
    "AbshodeNaghdi": {"high": 250.0, "medium": 80.0, "low": 15.0},
}

def get_market_params(market_name: str) -> dict:
    """بازیابی پارامترهای یک بازار بر ا��اس نام"""
    market_name = market_name.upper().strip()
    
    if market_name in ["XAUUSD", "XAU", "GOLD"]:
        return MARKET_XAUUSD
    elif market_name in ["HARATUSD", "HARAT", "HARAT_USD"]:
        return MARKET_HARAT
    elif market_name in ["ABSHODENAHDI", "ABSHODE", "ABSHODEH", "ABSHO"]:
        return MARKET_ABSHODE
    else:
        return MARKET_XAUUSD

def get_all_markets() -> list:
    """لیست تمام بازارهای در دسترس"""
    return [MARKET_XAUUSD, MARKET_HARAT, MARKET_ABSHODE]
