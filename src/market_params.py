# market_params.py — پارامترهای کالیبره‌شده برای سه بازار
# نسخه: ۱.۰ | تاریخ: ۱۴۰۴
# جایگزین تمام پارامترهای پراکنده در سراسر مخزن

MARKET_ABSHODE = {
    "name": "آبشده نقدی",
    "symbol": "AbshodeNaghdi",
    "type": "order_book_driven",
    "venue": "Tehran OTC Physical",
    "currency": "IRT",
    "display_unit": "million_IRT",
    "price_divisor": 1_000_000,
    "timezone": "Asia/Tehran",
    "session_open": "09:00",
    "session_close": "22:00",
    "peak_activity_windows": [
        ("09:00", "10:30"), ("12:30", "14:00"),
        ("16:00", "18:00"), ("19:30", "21:30"),
    ],
    "fake_move_window": ("12:00", "14:30"),
    "structure": {
        "swing_lookback": 5,
        "swing_direction": "left_only",
        "bos_min_displacement_pct": 0.0015,  # ۰.۱۵٪
        "choch_confirmation_candles": 2,
        "structure_break_body_close": True,
    },
    "liquidity": {
        "equal_high_low_threshold_pct": 0.0025,  # ۰.۲۵٪
        "bsl_ssl_lookback_candles": {"1W": 52, "1D": 30, "4H": 60, "1H": 48, "30m": 48, "15m": 48, "5m": 24},
        "liquidity_sweep_threshold_pct": 0.0010,  # ۰.۱۰٪
        "equal_highs_min_touches": 2,
        "equal_lows_min_touches": 2,
    },
    "dealing_range": {
        "lookback_candles_daily": 20,
        "premium_zone_pct": 0.618,
        "discount_zone_pct": 0.382,
        "equilibrium_tolerance_pct": 0.05,
    },
    "volatility": {
        "atr_period": 14,
        "expected_daily_range_pct": (1.5, 3.5),
        "high_volatility_threshold_pct": 3.5,
        "low_volatility_threshold_pct": 0.8,
        "compression_candles_min": 5,
        "compression_range_pct": 0.5,
    },
    "regime": {
        "trending_min_bos_count": 3,
        "ranging_max_range_pct": 2.0,
        "compression_atr_ratio": 0.4,
        "manipulation_max_duration_candles_15m": 8,
    },
    "csv_format": {
        "columns": ["Date", "Time", "Open", "High", "Low", "Close", "Volume"],
        "has_header": False,
        "delimiter": "\t",
        "date_format": "%Y.%m.%d",
        "time_format": "%H:%M",
    },
    "timeframes": {
        "1M": {"role": "macro_cycle", "candles_load": 36},
        "1W": {"role": "structural_bias", "candles_load": 52},
        "1D": {"role": "dealing_range", "candles_load": 30},
        "4H": {"role": "execution_leg", "candles_load": 60},
        "1H": {"role": "tactical_flow", "candles_load": 72},
        "30m": {"role": "auction_sequence", "candles_load": 96},
        "15m": {"role": "session_control", "candles_load": 96},
        "5m": {"role": "dealer_sweep", "candles_load": 72},
        "1m": {"role": "micro_delivery", "candles_load": 120},
    },
}

MARKET_HARAT = {
    "name": "دلار هرات",
    "symbol": "HaratUSD",
    "type": "parallel_fx_market",
    "venue": "Tehran Parallel FX (Harat-Based)",
    "currency_pair": "USD/IRT",
    "display_unit": "IRT_per_USD",
    "price_divisor": 1,
    "timezone": "Asia/Tehran",
    "session_open": "09:00",
    "session_close": "21:00",
    "peak_activity_windows": [
        ("09:30", "11:00"), ("13:00", "14:30"),
        ("16:30", "18:30"), ("19:00", "21:00"),
    ],
    "reference_rate_time": "09:30",
    "structure": {
        "swing_lookback": 5,
        "swing_direction": "left_only",
        "bos_min_displacement_pct": 0.0008,  # ۰.۰۸٪
        "choch_confirmation_candles": 3,
        "structure_break_body_close": True,
        "gap_fill_threshold_pct": 0.0005,  # ۰.۰۵٪
        "iran_news_spike_filter": True,
    },
    "liquidity": {
        "equal_high_low_threshold_pct": 0.0012,  # ۰.۱۲٪
        "bsl_ssl_lookback_candles": {"1W": 26, "1D": 20, "4H": 48, "1H": 48, "30m": 48, "15m": 48},
        "liquidity_sweep_threshold_pct": 0.0006,  # ۰.۰۶٪
        "policy_resistance_zones": True,
        "round_number_magnet_pct": 0.0008,  # ۰.۰۸٪
    },
    "dealing_range": {
        "lookback_candles_daily": 15,
        "premium_zone_pct": 0.618,
        "discount_zone_pct": 0.382,
        "equilibrium_tolerance_pct": 0.03,
    },
    "volatility": {
        "atr_period": 14,
        "expected_daily_range_pct": (0.3, 1.2),
        "high_volatility_threshold_pct": 1.5,
        "low_volatility_threshold_pct": 0.2,
        "policy_event_multiplier": 2.5,
        "compression_candles_min": 8,
        "compression_range_pct": 0.2,
    },
    "cross_market": {
        "xauusd_correlation_pct": 0.65,
        "abshode_transmission_lag_hours": 1.5,
        "global_risk_sensitivity": "high",
    },
    "regime": {
        "trending_min_bos_count": 3,
        "policy_ranging_override": True,
        "manipulation_max_duration_candles_15m": 6,
        "intervention_spike_pct": 0.8,
    },
    "timeframes": {
        "1W": {"role": "macro_policy", "candles_load": 52},
        "1D": {"role": "dealing_range", "candles_load": 30},
        "4H": {"role": "execution_leg", "candles_load": 60},
        "1H": {"role": "tactical_flow", "candles_load": 72},
        "30m": {"role": "auction_sequence", "candles_load": 96},
        "15m": {"role": "session_control", "candles_load": 96},
    },
}

MARKET_XAUUSD = {
    "name": "انس جهانی طلا",
    "symbol": "XAUUSD",
    "type": "cme_futures_spot",
    "venue": "Global (COMEX/LBMA/OTC)",
    "currency": "USD",
    "display_unit": "USD_per_troy_oz",
    "price_divisor": 1,
    "timezone": "UTC",
    "tehran_offset_hours": 3.5,
    "sessions": {
        "sydney": {"open": "00:00", "close": "09:00", "tehran": ("03:30", "12:30")},
        "tokyo": {"open": "01:00", "close": "10:00", "tehran": ("04:30", "13:30")},
        "london": {"open": "08:00", "close": "17:00", "tehran": ("11:30", "20:30")},
        "new_york": {"open": "13:00", "close": "22:00", "tehran": ("16:30", "01:30")},
    },
    "kill_zones": {
        "london_open": {"utc": ("08:00", "09:30"), "tehran": ("11:30", "13:00")},
        "new_york_open": {"utc": ("13:00", "14:30"), "tehran": ("16:30", "18:00")},
        "london_close": {"utc": ("16:00", "17:00"), "tehran": ("19:30", "20:30")},
        "asian_range": {"utc": ("20:00", "00:00"), "tehran": ("23:30", "03:30")},
    },
    "high_impact_news": {
        "nfp_day": "first_friday_month",
        "fomc": "8_times_year",
        "cpi": "monthly",
        "dxy_inverse_correlation": -0.82,
    },
    "structure": {
        "swing_lookback": 5,
        "swing_direction": "left_only",
        "bos_min_displacement_pct": 0.0025,  # ۰.۲۵٪
        "choch_confirmation_candles": 2,
        "structure_break_body_close": True,
        "pd_array_fib_levels": [0.236, 0.382, 0.5, 0.618, 0.705, 0.786],
    },
    "liquidity": {
        "equal_high_low_threshold_pct": 0.0005,  # ۰.۰۵٪
        "bsl_ssl_lookback_candles": {
            "1M": 24, "1W": 52, "1D": 30, "4H": 60,
            "1H": 72, "30m": 96, "15m": 96, "5m": 72, "1m": 120,
        },
        "liquidity_sweep_threshold_pct": 0.0003,  # ۰.۰۳٪
        "smart_money_footprint_fvg_min_pct": 0.0015,  # ۰.۱۵٪
        "order_block_body_min_pct": 0.0020,  # ۰.۲۰٪
    },
    "dealing_range": {
        "lookback_candles_daily": 20,
        "premium_zone_pct": 0.618,
        "discount_zone_pct": 0.382,
        "equilibrium_tolerance_pct": 0.03,
        "weekly_high_low_protected": True,
    },
    "volatility": {
        "atr_period": 14,
        "expected_daily_range_usd": (15, 35),
        "expected_daily_range_pct": (0.6, 1.5),
        "high_volatility_threshold_pct": 2.0,
        "low_volatility_threshold_pct": 0.3,
        "compression_candles_min": 6,
        "compression_range_pct": 0.25,
        "news_spike_exclusion_minutes": 15,
    },
    "iran_transmission": {
        "abshode_correlation_pct": 0.78,
        "harat_correlation_pct": 0.65,
        "transmission_lag_hours_abshode": 2.0,
        "transmission_lag_hours_harat": 1.5,
        "iran_premium_over_spot_pct": (5, 15),
        "transmission_filter": "london_new_york_overlap",
    },
    "regime": {
        "trending_min_bos_count": 3,
        "manipulation_max_duration_candles_15m": 8,
        "asian_range_extension_threshold_pct": 0.15,
        "ict_power_of_3_enabled": True,
    },
    "timeframes": {
        "1M": {"role": "macro_context", "candles_load": 36},
        "1W": {"role": "structural_bias", "candles_load": 52},
        "1D": {"role": "dealing_range", "candles_load": 30},
        "4H": {"role": "execution_leg", "candles_load": 60},
        "1H": {"role": "tactical_flow", "candles_load": 72},
        "30m": {"role": "auction_sequence", "candles_load": 96},
        "15m": {"role": "session_control", "candles_load": 96},
        "5m": {"role": "dealer_sweep", "candles_load": 72},
        "1m": {"role": "micro_delivery", "candles_load": 120},
    },
}

CROSS_MARKET_MATRIX = {
    "transmission_chain": ["XAUUSD", "HaratUSD", "AbshodeNaghdi"],
    "correlation_matrix": {
        ("XAUUSD", "AbshodeNaghdi"): 0.78,
        ("XAUUSD", "HaratUSD"): 0.65,
        ("HaratUSD", "AbshodeNaghdi"): 0.85,
    },
    "transmission_lag": {
        ("XAUUSD", "HaratUSD"): 1.5,
        ("XAUUSD", "AbshodeNaghdi"): 2.0,
        ("HaratUSD", "AbshodeNaghdi"): 0.5,
    },
    "rules": {
        "xauusd_up_harat_up_abshode_up": "scenario_bullish_aligned",
        "xauusd_up_harat_flat_abshode_lag": "abshode_catching_up",
        "xauusd_down_harat_up_abshode_conflict": "policy_override_likely",
        "all_diverging": "high_uncertainty_no_trade",
    },
    "confirmation_score": {
        "all_aligned": 3,
        "two_aligned": 2,
        "diverging": 1,
        "threshold_for_analysis": 2,
    },
}

# نگاشت نام کوتاه به دیکشنری کامل
MARKETS = {
    "abshodeh": MARKET_ABSHODE,
    "harat": MARKET_HARAT,
    "xauusd": MARKET_XAUUSD,
}

# ثابت‌های سراسری
VALID_REGIMES = ["LOW_VOL", "NORMAL", "HIGH_VOL", "MANIPULATION"]
DEFAULT_SEED = 42
DEFAULT_SIMULATIONS = 1000
DEFAULT_MAX_HOLDING_CANDLES = 96
DEFAULT_MIN_EV = 0.05
MIN_CROSS_MARKET_SCORE = CROSS_MARKET_MATRIX["confirmation_score"]["threshold_for_analysis"]

# آستانه‌های کالیبره‌شده برای 04_liquidity.py
LIQUIDITY_THRESHOLDS = {
    "AbshodeNaghdi": 0.0025,  # ۰.۲۵٪
    "HaratUSD": 0.0012,       # ۰.۱۲٪
    "XAUUSD": 0.0005,         # ۰.۰۵٪
}

# آستانه‌های BOS برای 03_structure.py
BOS_MIN_DISPLACEMENT = {
    "AbshodeNaghdi": 0.0015,  # ۰.۱۵٪
    "HaratUSD": 0.0008,       # ۰.۰۸٪
    "XAUUSD": 0.0025,         # ۰.۲۵٪
}

# تنظیمات تایم‌فریم و سشن برای 02_resample_mtf.py
TIMEFRAMES_BY_MARKET = {
    "AbshodeNaghdi": {
        "rules": {"1T": "1min", "5T": "5min", "15T": "15min", "30T": "30min",
                   "1h": "1H", "4h": "4H", "1D": "1D", "1W": "W", "1M": "MS"},
        "session_filter": {"start": "09:00", "end": "22:00", "tz": "Asia/Tehran"},
    },
    "HaratUSD": {
        "rules": {"15T": "15min", "30T": "30min", "1h": "1H", "4h": "4H",
                   "1D": "1D", "1W": "W"},
        "session_filter": {"start": "09:00", "end": "21:00", "tz": "Asia/Tehran"},
    },
    "XAUUSD": {
        "rules": {"1T": "1min", "5T": "5min", "15T": "15min", "30T": "30min",
                   "1h": "1H", "4h": "4H", "1D": "1D", "1W": "W", "1M": "MS"},
        "session_filter": None,  # ۲۴ ساعته
    },
}