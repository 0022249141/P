"""Machine learning filter for signal classification."""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report


class MLFilter:
    """Machine learning based signal filtering."""

    def __init__(self, liq_engine, disp_engine, zone_engine,
                 vp_engine=None, ice_engine=None):
        """Initialize ML filter."""
        self.liq = liq_engine
        self.disp = disp_engine
        self.zone = zone_engine
        self.vp = vp_engine
        self.ice = ice_engine
        self.model = RandomForestClassifier(
            n_estimators=50, max_depth=3, random_state=42
        )
        self.feature_names = [
            'sweep', 'disp', 'zone', 'vpoc_dist', 'iceberg',
            'regime_low', 'regime_normal', 'regime_high'
        ]
        self.is_trained = False

    def build_dataset(self, signals_df, market_df, horizon=20):
        """Build training dataset with labels.

        برچسب‌گذاری سیگنال‌ها: 1 اگر در horizon کندل به TP قبل از
        SL برسد، 0 درغیراینصورت.
        """
        features = []
        labels = []
        for _, sig in signals_df.iterrows():
            ts = sig['timestamp']
            idx = market_df.index[market_df['timestamp'] == ts]
            if len(idx) == 0:
                continue
            i = idx[0]
            # استخراج ویژگی‌ها
            feat = {
                'sweep': self.liq.get_sweep(i),
                'disp': self.disp.get_score(i),
                'zone': max(
                    self.zone.get_fvg_score(i),
                    self.zone.get_ob_score(i)
                ),
                'vpoc_dist': 0.0,
                'iceberg': 0.0,
                'regime_low': 1 if (
                    self.liq.mkt.get_regime(i) == 'LOW_VOL'
                ) else 0,
                'regime_normal': 1 if (
                    self.liq.mkt.get_regime(i) == 'NORMAL'
                ) else 0,
                'regime_high': 1 if (
                    self.liq.mkt.get_regime(i) == 'HIGH_VOL'
                ) else 0,
            }
            if self.vp:
                vpoc = self.vp.get_vpoc(i)
                if vpoc is not None:
                    feat['vpoc_dist'] = min(
                        abs(
                            market_df['close'].iloc[i] - vpoc
                        ) / market_df['ATR14'].iloc[i], 2.0
                    )
            if self.ice:
                feat['iceberg'] = self.ice.get_iceberg(i)

            # برچسب
            future = market_df.iloc[i+1 : min(
                i+horizon+1, len(market_df)
            )]
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
        """Train model using walk-forward validation."""
        features_df, labels = self.build_dataset(signals_df, market_df)
        if features_df.empty:
            print("No training data available")
            return

        tscv = TimeSeriesSplit(n_splits=n_splits)
        for train_idx, test_idx in tscv.split(features_df):
            X_train = features_df.iloc[train_idx]
            y_train = labels[train_idx]
            X_test = features_df.iloc[test_idx]
            y_test = labels[test_idx]

            self.model.fit(X_train, y_train)
            y_pred = self.model.predict(X_test)
            print(classification_report(y_test, y_pred))

        self.is_trained = True

    def predict(self, X) -> np.ndarray:
        """Predict signal quality."""
        if not self.is_trained:
            return np.zeros(len(X))
        return self.model.predict_proba(X)[:, 1]
