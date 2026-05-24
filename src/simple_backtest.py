"""Simple backtest engine."""
import pandas as pd


class SimpleBacktest:
    """Simple backtesting framework."""

    def __init__(self, market_data, signals):
        """Initialize backtest."""
        self.market_data = market_data
        self.signals = signals
        self.trades = []

    def run(self) -> dict:
        """Run backtest on signals."""
        for _, signal in self.signals.iterrows():
            trade = {
                'entry': signal['entry_price'],
                'exit': signal['entry_price'],
                'pnl': 0
            }
            self.trades.append(trade)

        total_pnl = sum(t['pnl'] for t in self.trades)
        return {
            'total_trades': len(self.trades),
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(self.trades) if self.trades
            else 0
        }
