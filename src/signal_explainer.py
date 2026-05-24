"""Signal explanation engine."""


class SignalExplainer:
    """Explain generated trading signals."""

    def __init__(self, liq_engine, disp_engine, zone_engine):
        """Initialize signal explainer."""
        self.liq = liq_engine
        self.disp = disp_engine
        self.zone = zone_engine

    def explain_signal(self, idx: int, direction: str) -> dict:
        """Generate explanation for a signal."""
        sweep_score = self.liq.get_sweep(idx)
        disp_score = self.disp.get_score(idx)
        fvg_score = self.zone.get_fvg_score(idx)
        ob_score = self.zone.get_ob_score(idx)

        explanation = {
            'sweep': sweep_score,
            'displacement': disp_score,
            'fvg': fvg_score,
            'order_block': ob_score,
            'direction': direction,
            'quality': max(sweep_score, disp_score, fvg_score,
                          ob_score)
        }
        return explanation
