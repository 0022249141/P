# 06_quality_check.py — نسخهٔ اصلاح‌شده با مسیرهای صحیح
import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    """یافتن ریشهٔ مخزن (محل فایل‌های src/ و data/)"""
    return Path(__file__).parent.parent

def validate_all_pipelines():
    """
    اجرای تمام مراحل pipeline به ترتیب.
    مسیرها نسبت به ریشهٔ مخزن تنظیم شده‌اند.
    """
    root = get_project_root()
    logger.info(f"ریشهٔ مخزن: {root}")

    steps = [
        ("تمیزسازی داده‌ها", root / "01_fix_data.py"),
        ("بازنمونه‌گیری چندتایم‌فریم", root / "02_resample_mtf.py"),
        ("تحلیل ساختار بازار", root / "03_structure.py"),
        ("تحلیل نقدینگی", root / "04_liquidity.py"),
        ("سشن‌بندی", root / "05_sessions.py"),
    ]

    for step_name, script_path in steps:
        if not script_path.exists():
            logger.error(f"فایل {script_path} پیدا نشد — مرحلهٔ «{step_name}» رد شد.")
            continue
        logger.info(f"مرحله: {step_name} — {script_path}")
        try:
            exec(script_path.read_text(encoding='utf-8'))
            logger.info(f"✓ {step_name} با موفقیت انجام شد.")
        except Exception as e:
            logger.error(f"✗ خطا در {step_name}: {e}")
            raise

if __name__ == "__main__":
    validate_all_pipelines()