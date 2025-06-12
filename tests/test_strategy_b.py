"""
Unit tests for Strategy B implementation.
Tests SMA crossover signal generation and ATR-based stop levels.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to the path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Update imports to use full package path
    from pybit_bot.strategies.strategy_b import StrategyB
    from pybit_bot.strategies.base_strategy import SignalType, OrderType
    print("Successfully imported strategy modules")
except Exception as e:
    print(f"Import error: {str(e)}")
    raise


class TestStrategyB(unittest.TestCase):
    """Test suite for Strategy B."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a sample configuration
        self.config = {
            'strategy_b': {
                'enabled': True,
                'sma_fast_length': 10,
                'sma_slow_length': 30,
                'atr_length': 14,
                'tp_atr_mult': 4.0,
                'trail_atr_mult': 2.0,
                'trail_activation_pct': 0.5,
                'sma_timeframe': '1m',
                'atr_timeframe': '1m'
            }
        }
        
        # Create a sample symbol
        self.symbol = 'BTCUSDT'
        
        # Create a strategy instance
        self.strategy = StrategyB(self.config, self.symbol)
    
    def create_bullish_crossover_data(self):
        """Create sample data with a bullish crossover at the end"""
        # Create date range
        start_date = datetime(2023, 1, 1)
        dates = [start_date + timedelta(minutes=i) for i in range(100)]
        
        # Create price data
        np.random.seed(42)  # For reproducibility
        close = 20000 + np.cumsum(np.random.normal(0, 100, 100))
        high = close + np.random.uniform(50, 200, 100)
        low = close - np.random.uniform(50, 200, 100)
        open_price = close - np.random.normal(0, 100, 100)
        volume = np.random.uniform(1, 10, 100) * 100
        
        # Create DataFrame
        df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        # Add indicators for testing
        df['atr'] = np.ones(100) * 100  # Constant ATR of 100
        df['fast_sma'] = calculate_sma(df['close'], 10)
        df['slow_sma'] = calculate_sma(df['close'], 30)
        
        # Create a bullish crossover at the END of the DataFrame (last 2 bars)
        # This is where the strategy looks for signals
        df.loc[df.index[-2], 'fast_sma'] = 20000  # Previous bar: fast below slow
        df.loc[df.index[-2], 'slow_sma'] = 20100
        df.loc[df.index[-1], 'fast_sma'] = 20200  # Current bar: fast above slow
        df.loc[df.index[-1], 'slow_sma'] = 20100
        
        # Create data dictionary
        return {'1m': df}
    
    def create_bearish_crossover_data(self):
        """Create sample data with a bearish crossover at the end"""
        # Create date range
        start_date = datetime(2023, 1, 1)
        dates = [start_date + timedelta(minutes=i) for i in range(100)]
        
        # Create price data
        np.random.seed(42)  # For reproducibility
        close = 20000 + np.cumsum(np.random.normal(0, 100, 100))
        high = close + np.random.uniform(50, 200, 100)
        low = close - np.random.uniform(50, 200, 100)
        open_price = close - np.random.normal(0, 100, 100)
        volume = np.random.uniform(1, 10, 100) * 100
        
        # Create DataFrame
        df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        # Add indicators for testing
        df['atr'] = np.ones(100) * 100  # Constant ATR of 100
        df['fast_sma'] = calculate_sma(df['close'], 10)
        df['slow_sma'] = calculate_sma(df['close'], 30)
        
        # Create a bearish crossover at the END of the DataFrame (last 2 bars)
        # This is where the strategy looks for signals
        df.loc[df.index[-2], 'fast_sma'] = 21000  # Previous bar: fast above slow
        df.loc[df.index[-2], 'slow_sma'] = 20900
        df.loc[df.index[-1], 'fast_sma'] = 20800  # Current bar: fast below slow
        df.loc[df.index[-1], 'slow_sma'] = 20900
        
        # Create data dictionary
        return {'1m': df}
    
    def test_required_timeframes(self):
        """Test that required timeframes are correctly returned."""
        timeframes = self.strategy.get_required_timeframes()
        self.assertIn('1m', timeframes)
    
    def test_validate_config(self):
        """Test configuration validation."""
        is_valid, _ = self.strategy.validate_config()
        self.assertTrue(is_valid)
        
        # Test with invalid config (fast SMA > slow SMA)
        invalid_config = {
            'strategy_b': {
                'enabled': True,
                'sma_fast_length': 40,  # Invalid: faster SMA has larger period
                'sma_slow_length': 30,
                'atr_length': 14,
                'tp_atr_mult': 4.0,
                'trail_atr_mult': 2.0,
                'trail_activation_pct': 0.5
            }
        }
        invalid_strategy = StrategyB(invalid_config, self.symbol)
        is_valid, error = invalid_strategy.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("Fast SMA length", error)
    
    def test_bullish_signal_generation(self):
        """Test generation of bullish signals."""
        # Create data with bullish crossover at the end
        bullish_data = self.create_bullish_crossover_data()
        
        # Generate signals
        signals = self.strategy.generate_signals(bullish_data)
        
        # Filter for BUY signals
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        
        # Debug output
        if not buy_signals:
            print("DEBUG: No buy signals generated")
            print(f"Previous fast SMA: {bullish_data['1m']['fast_sma'].iloc[-2]}")
            print(f"Previous slow SMA: {bullish_data['1m']['slow_sma'].iloc[-2]}")
            print(f"Current fast SMA: {bullish_data['1m']['fast_sma'].iloc[-1]}")
            print(f"Current slow SMA: {bullish_data['1m']['slow_sma'].iloc[-1]}")
        
        # We should have at least one BUY signal
        self.assertTrue(len(buy_signals) > 0, "No buy signals generated")
    
    def test_bearish_signal_generation(self):
        """Test generation of bearish signals."""
        # Create data with bearish crossover at the end
        bearish_data = self.create_bearish_crossover_data()
        
        # Generate signals
        signals = self.strategy.generate_signals(bearish_data)
        
        # Filter for SELL signals
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        # Debug output
        if not sell_signals:
            print("DEBUG: No sell signals generated")
            print(f"Previous fast SMA: {bearish_data['1m']['fast_sma'].iloc[-2]}")
            print(f"Previous slow SMA: {bearish_data['1m']['slow_sma'].iloc[-2]}")
            print(f"Current fast SMA: {bearish_data['1m']['fast_sma'].iloc[-1]}")
            print(f"Current slow SMA: {bearish_data['1m']['slow_sma'].iloc[-1]}")
        
        # We should have at least one SELL signal
        self.assertTrue(len(sell_signals) > 0, "No sell signals generated")


# Helper function for SMA calculation
def calculate_sma(series: pd.Series, length: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return series.rolling(window=length, min_periods=1).mean()


if __name__ == '__main__':
    unittest.main(verbosity=2)