import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report

class MLFilter:
    def __init__(self, liq_engine, disp_engine, zone_engine, vp_engine=None, ice_engine=None):
        self.liq = liq_engine
        self.disp = disp_engine
        self.zone = zone_engine
        self.vp = vp_engine
        self.ice = ice_engine
        self.model = RandomForestClassifier(n_estimators=50, max_depth=3, random_state=42)
        self.feature_names = ['sweep', 'disp', 'zone', 'vpoc_dist', 'iceberg', 'regime_low', 'regime_normal', 'regime_high']
        self.is_trained = False

    def build_dataset(self, signals_df, market_df, horizon=20):
        """
        برچسب‌گذاری سیگنال‌ها: 1 اگر در horizon کندل به TP قبل از SL برسد، 0 درغیراینصورت.
        """
        features = []
        labels = []
        for _, sig in signals_df.iterrows():
            ts = sig['timestamp']
            idx = market_df.index[market_df['timestamp'] == ts]
            if len(idx) == 0: continue
            i = idx[0]
            # استخراج ویژگی‌ها
            feat = {
                'sweep': self.liq.get_sweep(i),
                'disp': self.disp.get_score(i),
                'zone': max(self.zone.get_fvg_score(i), self.zone.get_ob_score(i)),
                'vpoc_dist': 0.0,
                'iceberg': 0.0,
                'regime_low': 1 if self.liq.mkt.get_regime(i) == 'LOW_VOL' else 0,
                'regime_normal': 1 if self.liq.mkt.get_regime(i) == 'NORMAL' else 0,
                'regime_high': 1 if self.liq.mkt.get_regime(i) == 'HIGH_VOL' else 0,
            }
            if self.vp:
                vpoc = self.vp.get_vpoc(i)
                if vpoc is not None:
                    feat['vpoc_dist'] = min(abs(market_df['close'].iloc[i] - vpoc) / market_df['ATR14'].iloc[i], 2.0)
            if self.ice:
                feat['iceberg'] = self.ice.get_iceberg(i)

            # برچسب
            future = market_df.iloc[i+1 : min(i+horizon+1, len(market_df))]
            if sig['direction'] == 'BUY':
                tp_hit = (future['high'] >= sig['tp_price']).any()
                sl_hit = (future['low'] <= sig['sl_price']).any()
            else:
                tp_hit = (future['low'] <= sig['tp_price']).any()
                sl_hit = (future['high'] >= sig['sl_price']).any()
            # اولویت با TP
            if tp_hit and not sl_hit:
                label = 1
            elif sl_hit:
                label = 0
            else:
                continue  # نامشخص
            features.append(feat)
            labels.append(label)
        return pd.DataFrame(features), np.array(labels)

    def train_walk_forward(self, signals_df, market_df, n_splits=5):
        X, y = self.build_dataset(signals_df, market_df)
        if len(X) < 50:
            return None
        tscv = TimeSeriesSplit(n_splits=n_splits)
        reports = []
        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            self.model.fit(X_train, y_train)
            y_pred = self.model.predict(X_test)
            report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
            reports.append(report)
        self.is_trained = True
        return reports

    def predict(self, signal_dict):
        if not self.is_trained:
            return 0.5
        X = pd.DataFrame([signal_dict])
        proba = self.model.predict_proba(X)[0][1]
        return proba
