"""Explicit, dry-run-first MetaTrader 5 execution boundary.

Importing this module is inert. MetaTrader5 is loaded only after live execution
has been explicitly enabled and all readiness evidence has been declared.
"""

from __future__ import annotations

import argparse
import importlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, Sequence

import pandas as pd


REQUIRED_PLAN_COLUMNS = {
    "direction",
    "entry_price",
    "stop_loss",
    "take_profit",
    "lots",
}


class ExecutionGateError(RuntimeError):
    """Raised before broker access when live execution is not eligible."""


class BrokerUnavailableError(RuntimeError):
    """Raised when the optional MetaTrader5 package cannot be loaded."""


class BrokerAPI(Protocol):
    """Small module-like boundary used by the executor and mock tests."""

    TRADE_ACTION_PENDING: int
    ORDER_TYPE_BUY_STOP: int
    ORDER_TYPE_SELL_STOP: int
    ORDER_TIME_GTC: int
    ORDER_FILLING_IOC: int
    TRADE_RETCODE_DONE: int

    def initialize(self) -> bool: ...

    def symbol_select(self, symbol: str, enable: bool) -> bool: ...

    def order_send(self, request: dict[str, Any]) -> Any: ...

    def shutdown(self) -> None: ...


@dataclass(frozen=True)
class ExecutionReadiness:
    """References to evidence required by the execution-readiness policy."""

    spread: str | None = None
    slippage: str | None = None
    commission: str | None = None
    fill_policy: str | None = None
    trade_logs: str | None = None

    def missing(self) -> list[str]:
        return [
            name
            for name, value in (
                ("spread", self.spread),
                ("slippage", self.slippage),
                ("commission", self.commission),
                ("fill_policy", self.fill_policy),
                ("trade_logs", self.trade_logs),
            )
            if not value or not value.strip()
        ]


@dataclass(frozen=True)
class ExecutionConfig:
    """Execution settings with a deliberately inert default."""

    symbol: str = "XAUUSD"
    dry_run: bool = True
    allow_live_execution: bool = False
    readiness: ExecutionReadiness = field(default_factory=ExecutionReadiness)
    deviation: int = 10
    magic: int = 123456
    comment_prefix: str = "AI_Setup"


@dataclass(frozen=True)
class PendingOrder:
    """Broker-neutral pending order parsed from an execution plan."""

    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    lots: float

    def preview(self, config: ExecutionConfig, index: int) -> dict[str, Any]:
        return {
            "action": "PENDING",
            "symbol": config.symbol,
            "volume": self.lots,
            "type": "BUY_STOP" if self.direction == "LONG" else "SELL_STOP",
            "price": self.entry_price,
            "sl": self.stop_loss,
            "tp": self.take_profit,
            "deviation": config.deviation,
            "magic": config.magic,
            "comment": f"{config.comment_prefix}_{index}",
            "type_time": "GTC",
            "type_filling": "IOC",
        }

    def broker_request(
        self, broker: BrokerAPI, config: ExecutionConfig, index: int
    ) -> dict[str, Any]:
        request = self.preview(config, index)
        request.update(
            action=broker.TRADE_ACTION_PENDING,
            type=(
                broker.ORDER_TYPE_BUY_STOP
                if self.direction == "LONG"
                else broker.ORDER_TYPE_SELL_STOP
            ),
            type_time=broker.ORDER_TIME_GTC,
            type_filling=broker.ORDER_FILLING_IOC,
        )
        return request


@dataclass(frozen=True)
class ExecutionResult:
    """Auditable result for either a preview or a broker response."""

    index: int
    status: str
    request: dict[str, Any]
    broker_order: int | None = None
    broker_comment: str | None = None


def load_execution_plan(plan_file: str | Path) -> pd.DataFrame:
    """Load and validate an execution plan after an explicit invocation."""

    path = Path(plan_file).expanduser()
    trades = pd.read_csv(path)
    return validate_execution_plan(trades)


def validate_execution_plan(trades: pd.DataFrame) -> pd.DataFrame:
    """Validate required columns and broker-relevant values."""

    missing = sorted(REQUIRED_PLAN_COLUMNS.difference(trades.columns))
    if missing:
        raise ValueError(f"Execution plan is missing columns: {', '.join(missing)}")

    validated = trades.copy()
    validated["direction"] = validated["direction"].astype(str).str.upper()
    invalid_directions = ~validated["direction"].isin({"LONG", "SHORT"})
    if invalid_directions.any():
        raise ValueError("Execution plan directions must be LONG or SHORT")

    numeric_columns = ["entry_price", "stop_loss", "take_profit", "lots"]
    for column in numeric_columns:
        validated[column] = pd.to_numeric(validated[column], errors="raise")
        if (
            validated[column].isna().any()
            or not validated[column].map(math.isfinite).all()
            or (validated[column] <= 0).any()
        ):
            raise ValueError(
                f"Execution plan column {column} must be finite and positive"
            )

    return validated


def prepare_orders(trades: pd.DataFrame) -> list[PendingOrder]:
    """Convert a validated plan into broker-neutral pending orders."""

    validated = validate_execution_plan(trades)
    return [
        PendingOrder(
            direction=row.direction,
            entry_price=float(row.entry_price),
            stop_loss=float(row.stop_loss),
            take_profit=float(row.take_profit),
            lots=float(row.lots),
        )
        for row in validated.itertuples(index=False)
    ]


def validate_live_execution(config: ExecutionConfig) -> None:
    """Block live access unless opt-in and readiness evidence are explicit."""

    if config.dry_run:
        return
    if not config.allow_live_execution:
        raise ExecutionGateError(
            "Live execution requires allow_live_execution=True in addition to dry_run=False"
        )

    missing = config.readiness.missing()
    if missing:
        raise ExecutionGateError(
            "Live execution is missing readiness evidence: " + ", ".join(missing)
        )


def load_mt5() -> ModuleType:
    """Load the optional broker dependency only at the explicit live boundary."""

    try:
        return importlib.import_module("MetaTrader5")
    except ImportError as exc:
        raise BrokerUnavailableError(
            "MetaTrader5 is optional; install the live-broker extra to execute live"
        ) from exc


def execute_orders(
    trades: pd.DataFrame,
    config: ExecutionConfig | None = None,
    broker: BrokerAPI | None = None,
) -> list[ExecutionResult]:
    """Preview orders by default or submit through an explicitly enabled broker."""

    active_config = config or ExecutionConfig()
    orders = prepare_orders(trades)

    if active_config.dry_run:
        return [
            ExecutionResult(
                index=index,
                status="DRY_RUN",
                request=order.preview(active_config, index),
            )
            for index, order in enumerate(orders)
        ]

    validate_live_execution(active_config)
    active_broker = broker if broker is not None else load_mt5()

    if not active_broker.initialize():
        raise RuntimeError("MetaTrader5 initialization failed")

    try:
        if not active_broker.symbol_select(active_config.symbol, True):
            raise RuntimeError(f"Broker symbol is unavailable: {active_config.symbol}")

        results = []
        for index, order in enumerate(orders):
            request = order.broker_request(active_broker, active_config, index)
            response = active_broker.order_send(request)
            status = (
                "SUBMITTED"
                if response.retcode == active_broker.TRADE_RETCODE_DONE
                else "REJECTED"
            )
            results.append(
                ExecutionResult(
                    index=index,
                    status=status,
                    request=request,
                    broker_order=getattr(response, "order", None),
                    broker_comment=getattr(response, "comment", None),
                )
            )
        return results
    finally:
        active_broker.shutdown()


def execute_plan(
    plan_file: str | Path,
    config: ExecutionConfig | None = None,
    broker: BrokerAPI | None = None,
) -> list[ExecutionResult]:
    """Load a plan explicitly, then preview or execute its orders."""

    return execute_orders(load_execution_plan(plan_file), config=config, broker=broker)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_file", type=Path)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--allow-live-execution", action="store_true")
    parser.add_argument("--spread-evidence")
    parser.add_argument("--slippage-evidence")
    parser.add_argument("--commission-evidence")
    parser.add_argument("--fill-policy")
    parser.add_argument("--trade-log-evidence")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = ExecutionConfig(
        symbol=args.symbol,
        dry_run=not args.execute_live,
        allow_live_execution=args.allow_live_execution,
        readiness=ExecutionReadiness(
            spread=args.spread_evidence,
            slippage=args.slippage_evidence,
            commission=args.commission_evidence,
            fill_policy=args.fill_policy,
            trade_logs=args.trade_log_evidence,
        ),
    )
    for result in execute_plan(args.plan_file, config=config):
        print(f"{result.index}: {result.status} {result.request}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
