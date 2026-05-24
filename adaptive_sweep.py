import pandas as pd
import numpy as np
from typing import Tuple, Optional

class AdaptiveSweepDetector:
    """
    سوئیپ دتکتور تطبیقی بدون آستانه ثابت.
    """
    def __init__(
        self,
        penetration_max_atr: float = 0.5,
        rejection_wick_min_ratio: float = 0.6,
        close_relocation_atr: float = 0.2,
        volume_percentile: float = 80,
        min_swing_strength: int = 1,
        cluster_distance_atr: float = 0.5
    ):
        self.penetration_max_atr = penetration_max_atr
        self.rejection_wick_min_ratio = rejection_wick_min_ratio
        self.close_relocation_atr = close_relocation_atr
        self.volume_percentile = volume_percentile
        self.min_swing_strength = min_swing_strength
        self.cluster_distance_atr = cluster_distance_atr
        self.liquidity_levels_high = None
        self.liquidity_levels_low = None

    def _identify_liquidity_levels(self, df: pd.DataFrame):
        """سطوح نقدینگی مبتنی بر swing_high/swing_low و خوشه‌بندی."""
        highs = df[df['swing_high'] > 0][['datetime', 'high', 'swing_high', 'atr']].copy()
        lows = df[df['swing_low'] > 0][['datetime', 'low', 'swing_low', 'atr']].copy()

        # خوشه‌بندی ساده: اگر دو سطح فاصله‌شان کمتر از cluster_distance_atr * ATR باشد، یکی شوند
        clusters_high = []
        if not highs.empty:
            highs = highs.sort_values('high')
            current_cluster = [highs.iloc[0]]
            for i in range(1, len(highs)):
                row = highs.iloc[i]
                if row['high'] - current_cluster[-1]['high'] <= self.cluster_distance_atr * row['atr']:
                    current_cluster.append(row)
                else:
                    clusters_high.append(current_cluster)
                    current_cluster = [row]
            clusters_high.append(current_cluster)
            # هر خوشه → میانگین high و وزن بر اساس تعداد نقاط
            self.liquidity_levels_high = pd.DataFrame([
                {'level': np.mean([r['high'] for r in cl]),
                 'weight': len(cl),
                 'atr': np.mean([r['atr'] for r in cl])}
                for cl in clusters_high if len(cl) >= self.min_swing_strength
            ])
        else:
            self.liquidity_levels_high = pd.DataFrame()

        clusters_low = []
        if not lows.empty:
            lows = lows.sort_values('low')
            current_cluster = [lows.iloc[0]]
            for i in range(1, len(lows)):
                row = lows.iloc[i]
                if row['low'] - current_cluster[-1]['low'] <= self.cluster_distance_atr * row['atr']:
                    current_cluster.append(row)
                else:
                    clusters_low.append(current_cluster)
                    current_cluster = [row]
            clusters_low.append(current_cluster)
            self.liquidity_levels_low = pd.DataFrame([
                {'level': np.mean([r['low'] for r in cl]),
                 'weight': len(cl),
                 'atr': np.mean([r['atr'] for r in cl])}
                for cl in clusters_low if len(cl) >= self.min_swing_strength
            ])
        else:
            self.liquidity_levels_low = pd.DataFrame()

    def _rolling_volume_percentile(self, volumes: pd.Series, window: int = 50) -> pd.Series:
        return volumes.rolling(window=window, min_periods=1).apply(
            lambda x: np.percentile(x, self.volume_percentile), raw=False
        )

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """اعمال تشخیص جاروب و برگرداندن sweep_score و sweep_type."""
        df = df.copy()
        # اطمینان از وجود ATR
        if 'atr' not in df.columns:
            raise ValueError("ستون atr در دیتافریم وجود ندارد. ابتدا Stage1 را اجرا کنید.")

        self._identify_liquidity_levels(df)

        df['sweep_score'] = 0.0
        df['sweep_type'] = 'none'

        if self.liquidity_levels_high.empty and self.liquidity_levels_low.empty:
            print("هیچ سطح نقدینگی‌ای یافت نشد.")
            return df

        # محاسبه volume threshold تطبیقی
        vol_percentile_series = self._rolling_volume_percentile(df['volume'], window=50)

        for idx, row in df.iterrows():
            atr = row['atr']
            if atr == 0:
                continue

            # --- بررسی Sweep نزولی (خرید) ---
            # کندل high از سطح نقدینگی low عبور کرده و close پایین برگشته
            sweep_score = 0.0
            sweep_type = 'none'

            if not self.liquidity_levels_low.empty:
                for _, level_row in self.liquidity_levels_low.iterrows():
                    level = level_row['level']
                    # شرط نفوذ
                    if row['low'] < level < row['high']:
                        depth = (row['high'] - level) / atr
                        if depth > self.penetration_max_atr:
                            continue  # عمق زیاد → احتمال شکست
                        # نسبت سایه برگشتی (سایه پایینی)
                        lower_wick = row['close'] - row['low'] if row['close'] > row['low'] else row['close'] - row['low']
                        rejection_ratio = lower_wick / (row['high'] - row['low']) if row['high'] > row['low'] else 0
                        if rejection_ratio < self.rejection_wick_min_ratio:
                            continue
                        # بسته شدن نزدیک سطح
                        if abs(row['close'] - level) > self.close_relocation_atr * atr:
                            continue
                        # حجم بالاتر از حد آستانه
                        if row['volume'] < vol_percentile_series.loc[idx]:
                            continue
                        # امتیازدهی
                        score = min(1.0, rejection_ratio) * 0.4
                        score += min(1.0, depth / self.penetration_max_atr) * 0.3
                        score += min(1.0, row['volume'] / (vol_percentile_series.loc[idx] + 0.01)) * 0.3
                        if score > sweep_score:
                            sweep_score = score
                            sweep_type = 'bullish'  # نشانه خرید (sweep نقدینگی فروش)

            # --- بررسی Sweep صعودی (فروش) ---
            if not self.liquidity_levels_high.empty:
                for _, level_row in self.liquidity_levels_high.iterrows():
                    level = level_row['level']
                    if row['low'] < level < row['high']:
                        depth = (level - row['low']) / atr
                        if depth > self.penetration_max_atr:
                            continue
                        upper_wick = row['high'] - row['close'] if row['close'] < row['high'] else 0
                        rejection_ratio = upper_wick / (row['high'] - row['low']) if row['high'] > row['low'] else 0
                        if rejection_ratio < self.rejection_wick_min_ratio:
                            continue
                        if abs(row['close'] - level) > self.close_relocation_atr * atr:
                            continue
                        if row['volume'] < vol_percentile_series.loc[idx]:
                            continue
                        score = min(1.0, rejection_ratio) * 0.4
                        score += min(1.0, depth / self.penetration_max_atr) * 0.3
                        score += min(1.0, row['volume'] / (vol_percentile_series.loc[idx] + 0.01)) * 0.3
                        if score > sweep_score:
                            sweep_score = score
                            sweep_type = 'bearish'  # نشانه فروش (sweep نقدینگی خرید)

            df.at[idx, 'sweep_score'] = round(sweep_score, 4)
            df.at[idx, 'sweep_type'] = sweep_type

        return df


def main():
    # برای تست، فایل Stage2 طلا ۱۵ دقیقه را بخوان
    input_path = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\struct_processed_XAU_USD-15.csv"
    output_path = r"C:\Users\pouria.sl\Desktop\GitHub.Desktop.3.5.5.x64\processed_stage2\sweep_XAU_USD-15.csv"

    df = pd.read_csv(input_path)
    detector = AdaptiveSweepDetector()
    result_df = detector.detect(df)

    # ذخیره
    result_df.to_csv(output_path, index=False)
    print(f"تعداد سیگنال‌های سوئیپ (bullish): {len(result_df[result_df['sweep_type']=='bullish'])}")
    print(f"تعداد سیگنال‌های سوئیپ (bearish): {len(result_df[result_df['sweep_type']=='bearish'])}")
    print(f"فایل خروجی ذخیره شد: {output_path}")

if __name__ == "__main__":
    main()
