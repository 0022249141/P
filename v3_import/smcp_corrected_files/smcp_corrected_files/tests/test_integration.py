"""Basic integration smoke test for the institutional engine chain."""
import numpy as np
import pandas as pd
from engines.market_state_machine import MarketStateMachine
from engines.dealer_inventory_engine import DealerInventoryEngine
from engines.market_delivery_engine import MarketDeliveryEngine
from engines.liquidity_classifier import LiquidityClassifier
from engines.probability_engine import ProbabilityEngine
from engines.regime_engine import RegimeEngine
from narratives.narrative_engine import NarrativeEngine
from engines.institutional_signal_engine import InstitutionalSignalEngine

def test_full_pipeline():
    rng=np.random.default_rng(42)
    dates=pd.date_range('2024-01-01',periods=100,freq='1h')
    close=100+np.cumsum(rng.normal(0,0.1,100)); open_=close+rng.normal(0,0.05,100)
    df=pd.DataFrame({'timestamp':dates,'open':open_,'high':np.maximum(open_,close)+0.5,'low':np.minimum(open_,close)-0.5,'close':close,'volume':rng.integers(100,1000,100)})
    state=MarketStateMachine().determine_state(df)
    liq=LiquidityClassifier().build_liquidity_map(df)
    inv=DealerInventoryEngine().evaluate(df, liq, state)
    delivery=MarketDeliveryEngine().evaluate(df, inv, liq)
    prob=ProbabilityEngine().evaluate(inv, delivery, liq, state)
    regime=RegimeEngine().evaluate(df, state)
    narr=NarrativeEngine().generate_signal_narrative('test', inv, delivery, prob, liq)
    signal=InstitutionalSignalEngine().evaluate(inv, delivery, prob, regime, liq, candles=df)
    assert signal.direction.value in {'long','short','neutral'}
    assert narr.english_text and narr.persian_text
    for v in [prob.confidence_score, prob.delivery_probability, signal.probability]: assert 0.0 <= v <= 1.0
