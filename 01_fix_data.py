# 01_fix_data.py — نسخهٔ هوشمند تبدیل فایل‌های خام به تمیز
import pandas as pd
from pathlib import Path

def smart_read(filepath):
    """تلاش برای خواندن فایل با فرمت‌های مختلف و برگرداندن DataFrame"""
    # حالت ۱: فایل تمیز با هدر (کاما جداکننده)
    try:
        df = pd.read_csv(filepath)
        if 'timestamp' in df.columns:
            return df, True
    except:
        pass

    # حالت ۲: فایل خام (تب جداکننده، بدون هدر)
    try:
        df = pd.read_csv(filepath, sep='\t', header=None,
                         names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str),
                                             format='%Y.%m.%d %H:%M')
            df.drop(columns=['date', 'time'], inplace=True)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)
            return df, False
    except:
        pass

    # حالت ۳: فایل خام با کاما جداکننده (بدون هدر)
    try:
        df = pd.read_csv(filepath, sep=',', header=None,
                         names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str),
                                             format='%Y.%m.%d %H:%M')
            df.drop(columns=['date', 'time'], inplace=True)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)
            return df, False
    except:
        pass

    return None, False

def process_all():
    data_dir = Path("data")
    for file in data_dir.glob("*.csv"):
        print(f"پردازش {file.name}...")
        df, is_clean = smart_read(file)
        if df is None or len(df) == 0:
            print(f"  ⚠️ نمی‌توان فایل را خواند. حذف نمی‌شود.")
            continue
        if is_clean:
            print(f"  ✅ قبلاً تمیز است ({len(df)} ردیف).")
        else:
            df.to_csv(file, index=False)
            print(f"  ✅ تبدیل شد و بازنویسی گردید ({len(df)} ردیف).")

if __name__ == "__main__":
    process_all()