class ScoringEngine:
    def __init__(self, liq_engine, disp_engine, zone_engine, vp_engine=None, ice_engine=None, htf_bias=0.5, weights=None):
        self.liq = liq_engine
        self.disp = disp_engine
        self.zone = zone_engine
        self.vp = vp_engine
        self.ice = ice_engine
        self.htf_bias = htf_bias
        # وزن‌های پیش‌فرض
        self.weights = weights or {
            'sweep': 0.25,
            'disp': 0.30,
            'zone': 0.25,
            'htf': 0.10,
            'vpoc': 0.05,
            'iceberg': 0.05
        }

    def get_setup_score(self, idx: int) -> float:
        sweep = self.liq.get_sweep(idx)
        disp = self.disp.get_score(idx)
        fvg = self.zone.get_fvg_score(idx)
        ob = self.zone.get_ob_score(idx)
        zone_quality = max(fvg, ob)

        vpoc_score = 0.0
        if self.vp:
            vpoc = self.vp.get_vpoc(idx)
            if vpoc is not None:
                close = self.liq.mkt.df['close'].iloc[idx]
                vpoc_score = max(0, 1 - abs(close - vpoc) / self.liq.mkt.df['ATR14'].iloc[idx])

        ice_score = 0.0
        if self.ice:
            ice_score = abs(self.ice.get_iceberg(idx))  # magnitude

        score = (self.weights['sweep'] * sweep +
                 self.weights['disp'] * disp +
                 self.weights['zone'] * zone_quality +
                 self.weights['htf'] * self.htf_bias +
                 self.weights['vpoc'] * vpoc_score +
                 self.weights['iceberg'] * ice_score) * 100
        return min(score, 100.0)
