# PyBit Bot Strategy Development Guide

This guide explains how to develop trading strategies for PyBit Bot, including the strategy interface, signal generation, and indicator usage.

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Strategy Interface](#strategy-interface)
3. [Signal Generation](#signal-generation)
4. [Indicator Integration](#indicator-integration)
5. [Strategy Configuration](#strategy-configuration)
6. [Testing Strategies](#testing-strategies)
7. [Best Practices](#best-practices)

## Strategy Overview

PyBit Bot uses a modular strategy architecture that separates signal generation from order execution. Each strategy is responsible for:

1. Processing market data
2. Applying technical indicators
3. Generating trade signals
4. Setting take profit and stop loss levels

The strategy manager handles strategy instantiation, data routing, and signal aggregation.

## Strategy Interface

All strategies must inherit from the `BaseStrategy` class and implement the required methods:

```python
from pybit_bot.strategies.base_strategy import BaseStrategy, TradeSignal

class MyCustomStrategy(BaseStrategy):
    def __init__(self, config: dict, symbol: str, timeframe: str):
        super().__init__(config, symbol, timeframe)
        # Initialize strategy-specific variables
        self.fast_length = self.params.get('fast_length', 12)
        self.slow_length = self.params.get('slow_length', 26)
        self.signal_length = self.params.get('signal_length', 9)
        
    def process_candle(self, candle: dict) -> Optional[TradeSignal]:
        """
        Process a new candle and generate a trade signal if conditions are met.
        
        Args:
            candle: Dictionary with OHLCV data
            
        Returns:
            TradeSignal object if a signal is generated, None otherwise
        """
        # Strategy logic implementation
        # ...
        
        # Return a signal if conditions are met
        if signal_conditions:
            return TradeSignal(
                symbol=self.symbol,
                timeframe=self.timeframe,
                strategy_name=self.name,
                signal_type='LONG',  # or 'SHORT', 'EXIT'
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timestamp=candle['timestamp'],
                metadata={
                    'reason': 'Crossover detected',
                    'indicator_values': {
                        'macd': macd_value,
                        'signal': signal_value
                    }
                }
            )
        
        return None