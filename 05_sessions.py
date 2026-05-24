# 05_sessions.py — سشن‌بندی صحیح بازار تهران
import pandas as pd
from datetime import time

def detect_session(row, market_name: str = "AbshodeNaghdi"):
    """
    تشخیص سشن معاملاتی برای بازارهای تهران.
    London/NY فقط برای XAUUSD معنا دارد.
    """
    if market_name in ["AbshodeNaghdi", "HaratUSD"]:
        # سشن‌های واقعی بازار تهران
        t = row['timestamp'].time()
        if time(9, 0) <= t < time(10, 30):
            return "TEHRAN_OPEN"
        elif time(10, 30) <= t < time(12, 30):
            return "TEHRAN_MID_MORNING"
        elif time(12, 30) <= t < time(14, 0):
            return "TEHRAN_LUNCH_TRANSITION"
        elif time(14, 0) <= t < time(16, 0):
            return "TEHRAN_AFTERNOON"
        elif time(16, 0) <= t < time(18, 0):
            return "TEHRAN_EVENING"
        elif time(18, 0) <= t < time(19, 30):
            return "TEHRAN_BREAK"
        elif time(19, 30) <= t < time(21, 30):
            return "TEHRAN_NIGHT"
        elif time(21, 30) <= t < time(22, 0):
            return "TEHRAN_CLOSE"
        else:
            return "CLOSED"
    else:
        # سشن‌های جهانی برای XAUUSD
        t = row['timestamp'].time()
        if time(0, 0) <= t < time(9, 0):
            return "ASIAN"
        elif time(9, 0) <= t < time(17, 0):
            return "LONDON"
        elif time(17, 0) <= t < time(23, 59):
            return "NEW_YORK"
        else:
            return "ASIAN"