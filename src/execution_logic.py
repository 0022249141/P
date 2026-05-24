"""Execution logic and signal generation."""
import pandas as pd


class ExecutionLogic:
    """Layer 7 — Execution & Risk Management.

    Generates structured signals for the backtest engine.
    """

    def __init__(self, scoring_engine, market_engine, struct_engine):
        """Initialize execution logic."""
        self.scoring = scoring_engine
        self.mkt = market_engine
        self.struct = struct_engine

    def generate_signals(self, min_setup_score=70):
        """Scan all candles and return a DataFrame of trade signals."""
        signals = []
        df = self.mkt.df

        for idx in range(len(df)):
            score = self.scoring.get_setup_score(idx)
            if score < min_setup_score:
                continue

            # Determine direction from the last displacement candle's direction
            if df['close'].iloc[idx] > df['open'].iloc[idx]:
                direction = 'BUY'
            else:
                direction = 'SELL'

            # Entry: at the close of the signal candle
            entry = df['close'].iloc[idx]

            # Stop Loss: last swing low (for BUY) or swing high (for SELL)
            # with ATR buffer
            if direction == 'BUY':
                valid_lows = self.struct.df['swing_low'].iloc[:idx].dropna()
                if not valid_lows.empty:
                    sl = valid_lows.iloc[-1] - 0.2 * df['ATR14'].iloc[idx]
                else:
                    sl = entry - 1.5 * df['ATR14'].iloc[idx]
            else:
                valid_highs = self.struct.df['swing_high'].iloc[:idx].dropna()
                if not valid_highs.empty:
                    sl = valid_highs.iloc[-1] + 0.2 * df['ATR14'].iloc[idx]
                else:
                    sl = entry + 1.5 * df['ATR14'].iloc[idx]

            # Take Profit: Risk:Reward 1:2 (simplified, can be ATR-based)
            risk = abs(entry - sl)
            if direction == 'BUY':
                tp = entry + 2 * risk
            else:
                tp = entry - 2 * risk

            signals.append({
                'timestamp': df['timestamp'].iloc[idx],
                'direction': direction,
                'market': 'XAU_USD',
                'entry_price': entry,
                'sl_price': sl,
                'tp_price': tp,
                'setup_score': score
            })

        return pd.DataFrame(signals)
