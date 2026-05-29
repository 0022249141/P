"""Central orchestrator coordinating engines, events, and recalculation."""
from __future__ import annotations
import logging, time
from typing import Any, Dict, Tuple
import pandas as pd
from core.schemas import EventType, Market, SystemEvent, TimeFrame
from events.event_bus import EventBus
from services.csv_watcher import CSVWatcher
from engines.market_state_machine import MarketStateMachine
from engines.liquidity_classifier import LiquidityClassifier
from engines.dealer_inventory_engine import DealerInventoryEngine
from engines.market_delivery_engine import MarketDeliveryEngine
from engines.probability_engine import ProbabilityEngine
from engines.regime_engine import RegimeEngine
from engines.tehran_session_engine import TehranSessionEngine
from engines.microstructure_engine import MicrostructureEngine
from engines.risk_engine import RiskEngine
from engines.scenario_engine import ScenarioEngine
from engines.institutional_signal_engine import InstitutionalSignalEngine
from narratives.narrative_engine import NarrativeEngine
logger=logging.getLogger(__name__)
class Orchestrator:
    def __init__(self,data_dir:str='./data'):
        self.event_bus=EventBus(); self.watcher=CSVWatcher(data_dir,self.event_bus)
        self.state_machine=MarketStateMachine(); self.liquidity_engine=LiquidityClassifier(); self.inventory_engine=DealerInventoryEngine(); self.delivery_engine=MarketDeliveryEngine(); self.prob_engine=ProbabilityEngine(); self.regime_engine=RegimeEngine(); self.tehran_engine=TehranSessionEngine(); self.microstructure_engine=MicrostructureEngine(); self.risk_engine=RiskEngine(); self.scenario_engine=ScenarioEngine(); self.signal_engine=InstitutionalSignalEngine(); self.narrative_engine=NarrativeEngine()
        self.market_data_cache:Dict[Tuple[Market,TimeFrame],pd.DataFrame]={}; self.state_cache={}; self.latest_outputs={}
        self.event_bus.subscribe(EventType.CSV_UPDATED,self.on_csv_update)
    async def start(self): await self.watcher.start()
    def on_csv_update(self,event:SystemEvent):
        try:
            market=Market(event.payload['market']); timeframe=TimeFrame(event.payload['timeframe']); path=event.payload['file_path']
            df=pd.read_csv(path); df['timestamp']=pd.to_datetime(df['timestamp'],errors='coerce')
            self.market_data_cache[(market,timeframe)]=df
            out=self.run_single_market_pipeline(df,market,timeframe)
            self.latest_outputs[(market,timeframe)]=out
            self.event_bus.publish(SystemEvent(event_id=f"pipeline_{int(time.time()*1000)}",event_type=EventType.NARRATIVE_UPDATED,source_engine='orchestrator',payload={'market':market.value,'timeframe':timeframe.value,'signal_id':out['signal'].id}))
        except Exception: logger.exception('Failed to process CSV update')
    def run_single_market_pipeline(self,df,market,tf)->Dict[str,Any]:
        liquidity=self.liquidity_engine.build_liquidity_map(df,market,tf); state=self.state_machine.step(df,liquidity); regime=self.regime_engine.evaluate(df,state,market,tf); session=self.tehran_engine.evaluate(df,market); micro=self.microstructure_engine.evaluate(df); inventory=self.inventory_engine.evaluate(df,liquidity,state,market,tf); delivery=self.delivery_engine.evaluate(df,inventory,liquidity,market,tf); probability=self.prob_engine.evaluate(inventory,delivery,liquidity,state,market,tf,df); risk=self.risk_engine.evaluate(inventory,delivery,probability,regime,liquidity); scenario=self.scenario_engine.build_scenarios(probability,state); signal=self.signal_engine.evaluate(inventory,delivery,probability,regime,liquidity,market,candles=df); narrative=self.narrative_engine.generate_signal_narrative(signal.id,inventory,delivery,probability,liquidity,market)
        self.state_cache[(market,tf)]=state
        return {'liquidity_map':liquidity,'state':state,'regime':regime,'session':session,'microstructure':micro,'inventory':inventory,'delivery':delivery,'probability':probability,'risk':risk,'scenario':scenario,'signal':signal,'narrative':narrative}
