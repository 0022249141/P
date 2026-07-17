from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest


def execution_plan() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "direction": "LONG",
                "entry_price": 2400.0,
                "stop_loss": 2390.0,
                "take_profit": 2420.0,
                "lots": 0.01,
            }
        ]
    )


def mock_broker() -> Mock:
    broker = Mock()
    broker.TRADE_ACTION_PENDING = 5
    broker.ORDER_TYPE_BUY_STOP = 4
    broker.ORDER_TYPE_SELL_STOP = 5
    broker.ORDER_TIME_GTC = 0
    broker.ORDER_FILLING_IOC = 1
    broker.TRADE_RETCODE_DONE = 10009
    broker.initialize.return_value = True
    broker.symbol_select.return_value = True
    broker.order_send.return_value = SimpleNamespace(
        retcode=broker.TRADE_RETCODE_DONE,
        order=42,
        comment="mock accepted",
    )
    return broker


@pytest.mark.parametrize("module_name", ["mt5_executor", "live_data_server"])
def test_import_has_no_file_or_runtime_side_effects(monkeypatch, module_name):
    read_csv = Mock(side_effect=AssertionError("import attempted a CSV read"))
    file_open = Mock(side_effect=AssertionError("import attempted a file write"))
    sleep = Mock(side_effect=AssertionError("import started a polling loop"))
    fake_mt5 = mock_broker()

    monkeypatch.setattr(pd, "read_csv", read_csv)
    monkeypatch.setattr("pathlib.Path.open", file_open)
    monkeypatch.setattr("time.sleep", sleep)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
    sys.modules.pop(module_name, None)

    importlib.import_module(module_name)

    read_csv.assert_not_called()
    file_open.assert_not_called()
    sleep.assert_not_called()
    fake_mt5.initialize.assert_not_called()
    fake_mt5.symbol_select.assert_not_called()
    fake_mt5.order_send.assert_not_called()
    fake_mt5.order_modify.assert_not_called()
    fake_mt5.order_cancel.assert_not_called()
    fake_mt5.shutdown.assert_not_called()


def test_default_execution_is_dry_run_and_never_loads_broker(monkeypatch):
    executor = importlib.import_module("mt5_executor")
    load_mt5 = Mock(side_effect=AssertionError("dry-run loaded MetaTrader5"))
    monkeypatch.setattr(executor, "load_mt5", load_mt5)
    broker = mock_broker()

    results = executor.execute_orders(execution_plan(), broker=broker)

    assert [result.status for result in results] == ["DRY_RUN"]
    assert results[0].request["type"] == "BUY_STOP"
    load_mt5.assert_not_called()
    broker.initialize.assert_not_called()
    broker.symbol_select.assert_not_called()
    broker.order_send.assert_not_called()
    broker.order_modify.assert_not_called()
    broker.order_cancel.assert_not_called()
    broker.shutdown.assert_not_called()


def test_live_execution_requires_separate_opt_in_before_broker_access():
    executor = importlib.import_module("mt5_executor")
    broker = mock_broker()
    config = executor.ExecutionConfig(dry_run=False)

    with pytest.raises(executor.ExecutionGateError, match="allow_live_execution=True"):
        executor.execute_orders(execution_plan(), config=config, broker=broker)

    broker.initialize.assert_not_called()
    broker.order_send.assert_not_called()


def test_live_execution_requires_all_readiness_evidence():
    executor = importlib.import_module("mt5_executor")
    broker = mock_broker()
    config = executor.ExecutionConfig(
        dry_run=False,
        allow_live_execution=True,
        readiness=executor.ExecutionReadiness(spread="fixture/spread.csv"),
    )

    with pytest.raises(executor.ExecutionGateError, match="slippage"):
        executor.execute_orders(execution_plan(), config=config, broker=broker)

    broker.initialize.assert_not_called()
    broker.order_send.assert_not_called()


def test_explicit_live_path_uses_only_injected_mock_broker():
    executor = importlib.import_module("mt5_executor")
    broker = mock_broker()
    config = executor.ExecutionConfig(
        dry_run=False,
        allow_live_execution=True,
        readiness=executor.ExecutionReadiness(
            spread="mock spread evidence",
            slippage="mock slippage evidence",
            commission="mock commission evidence",
            fill_policy="mock fill policy",
            trade_logs="mock trade-log evidence",
        ),
    )

    results = executor.execute_orders(execution_plan(), config=config, broker=broker)

    assert [result.status for result in results] == ["SUBMITTED"]
    broker.initialize.assert_called_once_with()
    broker.symbol_select.assert_called_once_with("XAUUSD", True)
    broker.order_send.assert_called_once()
    broker.shutdown.assert_called_once_with()


def test_optional_mt5_dependency_is_loaded_only_for_eligible_live_execution(monkeypatch):
    executor = importlib.import_module("mt5_executor")
    import_module = Mock(side_effect=ImportError("MetaTrader5 unavailable"))
    monkeypatch.setattr(executor.importlib, "import_module", import_module)
    config = executor.ExecutionConfig(
        dry_run=False,
        allow_live_execution=True,
        readiness=executor.ExecutionReadiness(
            spread="mock",
            slippage="mock",
            commission="mock",
            fill_policy="mock",
            trade_logs="mock",
        ),
    )

    with pytest.raises(executor.BrokerUnavailableError, match="optional"):
        executor.execute_orders(execution_plan(), config=config)

    import_module.assert_called_once_with("MetaTrader5")
