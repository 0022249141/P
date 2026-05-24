# 11_cross_market.py — انتقال بین‌بازاری و هم‌سویی بازارها
# نسخه ۱.۰
import pandas as pd
import numpy as np

def cross_market_analysis(df_xau: pd.DataFrame,
                          df_harat: pd.DataFrame,
                          df_abshode: pd.DataFrame,
                          corr_window: int = 96,   # 24h for 15min data
                          max_lag: int = 12,        # 3h for 15min data
                          return_type: str = 'log') -> pd.DataFrame:
    """
    محاسبه همبستگی غلتان، تأخیر انتقال، و امتیاز هم‌سویی بین سه بازار.
    
    پارامترها:
        df_xau, df_harat, df_abshode : DataFrame با شاخص زمانی (timestamp)
            و ستون 'close'
        corr_window : تعداد کندل برای پنجره همبستگی غلتان
        max_lag : حداکثر تأخیر قابل جستجو (بر حسب کندل)
        return_type : 'log' یا 'simple' برای محاسبه بازده
    
    خروجی:
        DataFrame یکپارچه با شاخص زمانی مشترک و ستون‌های:
        - corr_xau_harat, corr_xau_abs, corr_harat_abs : همبستگی غلتان
        - lag_xau_harat, lag_xau_abs, lag_harat_abs : تأخیر تخمینی (کندل)
        - best_corr_xau_harat, ... : مقدار همبستگی در بهترین lag
        - alignment_score : 0-3
        - regime : 'ALIGNED' یا 'DIVERGING'
    """

    # ۱. بازده‌ها
    def returns(series):
        if return_type == 'log':
            return np.log(series / series.shift(1))
        else:
            return series.pct_change()

    r_xau = returns(df_xau['close'])
    r_harat = returns(df_harat['close'])
    r_abs = returns(df_abshode['close'])

    # ۲. شاخص مشترک
    common_idx = df_xau.index.intersection(df_harat.index).intersection(df_abshode.index)
    if len(common_idx) < corr_window:
        raise ValueError("تعداد نقاط مشترک کافی نیست.")

    r_xau = r_xau.loc[common_idx]
    r_harat = r_harat.loc[common_idx]
    r_abs = r_abs.loc[common_idx]

    # ۳. همبستگی غلتان
    corr_xau_harat = r_xau.rolling(corr_window).corr(r_harat)
    corr_xau_abs   = r_xau.rolling(corr_window).corr(r_abs)
    corr_harat_abs = r_harat.rolling(corr_window).corr(r_abs)

    # ۴. تشخیص تأخیر (cross-correlation) برای هر جفت
    def estimate_lag(s1, s2, max_lag):
        s1 = s1.dropna()
        s2 = s2.dropna()
        common = s1.index.intersection(s2.index)
        s1 = s1.loc[common]
        s2 = s2.loc[common]
        best_lag = 0
        best_corr = -1
        for lag in range(0, max_lag + 1):
            # s2 را lag کندل عقب می‌بریم تا ببینیم s1 با s2 گذشته همبستگی دارد یا خیر
            if lag == 0:
                corr = s1.corr(s2)
            else:
                corr = s1.iloc[lag:].corr(s2.iloc[:-lag])
            if corr > best_corr:
                best_corr = corr
                best_lag = lag
        return best_lag, best_corr

    lag_xh, best_corr_xh = estimate_lag(r_xau, r_harat, max_lag)
    lag_xa, best_corr_xa = estimate_lag(r_xau, r_abs, max_lag)
    lag_ha, best_corr_ha = estimate_lag(r_harat, r_abs, max_lag)

    # ۵. ساخت DataFrame خروجی
    result = pd.DataFrame(index=common_idx)
    result['corr_xau_harat'] = corr_xau_harat
    result['corr_xau_abs']   = corr_xau_abs
    result['corr_harat_abs'] = corr_harat_abs

    # تأخیرها (مقادیر ثابت برای کل بازه، اما می‌توان غلتان هم کرد)
    result['lag_xau_harat'] = lag_xh
    result['lag_xau_abs']   = lag_xa
    result['lag_harat_abs'] = lag_ha
    result['best_corr_xau_harat'] = best_corr_xh
    result['best_corr_xau_abs']   = best_corr_xa
    result['best_corr_harat_abs'] = best_corr_ha

    # ۶. امتیاز هم‌سویی (جهت حرکت هر بازار)
    # تعیین جهت: +1 اگر میانگین بازده اخیر (۵ کندل) مثبت، -1 اگر منفی
    direction = lambda r: np.sign(r.rolling(5).mean())
    dir_xau = direction(r_xau)
    dir_harat = direction(r_harat)
    dir_abs = direction(r_abs)

    # هم‌سویی: هر بازار که با XAUUSD هم‌جهت باشد ۱ امتیاز
    aligned = (dir_xau == dir_harat).astype(int) + (dir_xau == dir_abs).astype(int) + (dir_harat == dir_abs).astype(int)
    # aligned می‌تواند 0,1,2,3 باشد (اما ۲ یعنی دو جفت هم‌جهت هستند)
    # نگاشت به 0-3: اگر هر سه هم‌جهت → 3، دو هم‌جهت → 2، یکی → 1، هیچکدام → 0
    result['alignment_score'] = aligned

    # ۷. رژیم نهایی
    result['regime'] = np.where(result['alignment_score'] < 2, 'DIVERGING', 'ALIGNED')

    return result


# =====================================================================
# مثال استفاده (می‌توانید در run_all_markets.py یا run_full_pipeline.py بگنجانید)
# =====================================================================
if __name__ == "__main__":
    # بارگذاری سه بازار
    df_xau = pd.read_csv('data/XAU_USD-15.csv', parse_dates=['timestamp'], index_col='timestamp')
    df_harat = pd.read_csv('data/haratFardayi-15.csv', parse_dates=['timestamp'], index_col='timestamp')
    df_abshode = pd.read_csv('data/abshodeNaghdi-15.csv', parse_dates=['timestamp'], index_col='timestamp')

    # اجرای تحلیل
    cross = cross_market_analysis(df_xau, df_harat, df_abshode)

    print(cross[['alignment_score', 'regime']].tail())