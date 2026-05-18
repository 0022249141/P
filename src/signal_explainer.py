import pandas as pd

class SignalExplainer:
    def __init__(self, scoring_engine, mtf_analyzer):
        self.scorer = scoring_engine
        self.mtf = mtf_analyzer

    def explain_signal(self, idx):
        """
        Returns a string in Persian explaining the logic behind a signal at idx.
        """
        df = self.scorer.liq.mkt.df
        timestamp = df['timestamp'].iloc[idx]
        close = df['close'].iloc[idx]
        sweep = self.scorer.liq.get_sweep(idx)
        disp = self.scorer.disp.get_score(idx)
        fvg = self.scorer.zone.get_fvg_score(idx)
        ob = self.scorer.zone.get_ob_score(idx)
        setup = self.scorer.get_setup_score(idx)
        htf_bias = self.scorer.htf_bias
        regime = self.scorer.liq.mkt.get_regime(idx)

        lines = []
        lines.append(f"📅 زمان: {timestamp}")
        lines.append(f"💰 قیمت: {close:.2f}")
        lines.append(f"📊 امتیاز ستاپ: {setup:.1f}/100")
        lines.append(f"🌊 سوگیری تایم‌فریم بالا: {'صعودی' if htf_bias > 0.6 else 'نزولی' if htf_bias < -0.6 else 'خنثی'} (امتیاز: {htf_bias:.2f})")
        lines.append(f"🔘 رژیم نوسان: {regime}")

        # تحلیل Sweep
        if sweep > 0.7:
            lines.append(f"✅ جاروب نقدینگی قوی (Sweep Score={sweep:.2f}): نشان‌دهندهٔ جمع‌آوری نقدینگی توسط بازارساز قبل از حرکت اصلی.")
        elif sweep > 0.3:
            lines.append(f"⚠️ جاروب ضعیف (Sweep Score={sweep:.2f}): احتمال جاروب داخلی یا فیک.")
        else:
            lines.append(f"❌ بدون جاروب معتبر.")

        # تحلیل Displacement
        if disp > 0.7:
            lines.append(f"🚀 جابجایی نهادی قوی (Disp={disp:.2f}): ورود سفارشات بزرگ تأیید می‌شود.")
        elif disp > 0.5:
            lines.append(f"🔸 جابجایی متوسط (Disp={disp:.2f}): حرکت نسبتاً معنی‌دار.")
        else:
            lines.append(f"🔹 جابجایی ضعیف (Disp={disp:.2f}): نبود تأیید حجمی قوی.")

        # تحلیل Zones
        if ob > 0.6:
            lines.append(f"🧱 Order Block معتبر (OB={ob:.2f}): ناحیه‌ای با حجم بالا که بازارساز از آن دفاع می‌کند.")
        if fvg > 0.5:
            lines.append(f"💨 FVG معتبر (FVG={fvg:.2f}): عدم تعادل قیمتی تأییدشده.")

        # سطوح کلیدی MTF
        levels = self.mtf.get_key_levels(timestamp)
        if levels:
            lines.append(f"📏 سطوح روزانه: High={levels['daily_high']:.2f} Low={levels['daily_low']:.2f} Close={levels['daily_close']:.2f}")
            if close > levels['daily_high']:
                lines.append("🔔 قیمت بالای های دیروز شکسته شده (نشانه قدرت).")
            elif close < levels['daily_low']:
                lines.append("🔔 قیمت زیر لو دیروز (ضعف).")

        # نتیجه‌گیری
        if setup > 80:
            lines.append("✨ نتیجه: ستاپ با کیفیت بالا. ورود با اطمینان بیشتر.")
        elif setup > 70:
            lines.append("👍 نتیجه: ستاپ قابل قبول. مدیریت سرمایه ضروری است.")
        else:
            lines.append("⛔ نتیجه: ستاپ زیر آستانه. بهتر است صبر کنید.")

        return "\n".join(lines)
