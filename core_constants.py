# core_constants.py — هستهٔ تغییرناپذیر پروژه
# تغییر این مقادیر نیازمند ثبت دلیل و تأیید است.

IMMUTABLE = {
    "ATR_PERIOD": 14,
    "SWING_WINDOW": 5,
    "MIN_SWING_STRENGTH_BASE": 0.8,        # پایه که با ATR تطبیق می‌شود
    "SWEEP_CLUSTER_GAP_ATR_MULT": 0.2,     # فاصلهٔ مجاز برای خوشه‌بندی سطوح (بر حسب ATR)
    "MAX_CASCADE_DEVIATION_PCT": 20.0,     # حداکثر انحراف مجاز در زنجیره (برای تست)
}