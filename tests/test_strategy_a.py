"""
Unit tests for Strategy A implementation.
Tests signal generation and indicator confluence logic.
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
    from pybit_bot.strategies.strategy_a import StrategyA
    from pybit_bot.strategies.base_strategy import SignalType, OrderType
    print("Successfully imported strategy modules")
except Exception as e:
    print(f"Import error: {str(e)}")
    raise


class TestStrategyA(unittest.TestCase):
    """Test suite for Strategy A."""
    
    def setUp(self):
        """Set up test fixtures."""
        print("Setting up test fixtures")
        # Create a sample configuration
        self.config = {
            'timeframes': {
                'default': '1m',
                'indicator_specific': {
                    'atr': '1m',
                    'cvd': '1m',
                    'tva': '1m',
                    'vfi': '1m',
                    'luxfvgtrend': '1m'
                }
            },
            'indicators': {
                'atr': {
                    'enabled': True,
                    'length': 14
                },
                'cvd': {
                    'enabled': True,
                    'cumulation_length': 25
                },
                'tva': {
                    'enabled': True,
                    'length': 15
                },
                'vfi': {
                    'enabled': True,
                    'lookback': 50
                },
                'luxfvgtrend': {
                    'enabled': True,
                    'step_size': 1.0
                }
            },
            'strategy_a': {
                'enabled': True,
                'filter_confluence': True,
                'use_limit_entries': True,
                'entry_settings': {
                    'max_long_trades': 1,
                    'max_short_trades': 1,
                    'order_timeout_seconds': 30
                },
                'risk_settings': {
                    'stop_loss_multiplier': 2.0,
                    'take_profit_multiplier': 4.0,
                    'trailing_stop': {
                        'enabled': True,
                        'activation_threshold': 0.5,
                        'atr_multiplier': 2.0
                    }
                }
            }
        }
        
        # Create a sample symbol
        self.symbol = 'BTCUSDT'
        
        # Create a strategy instance
        try:
            self.strategy = StrategyA(self.config, self.symbol)
            print("Successfully created StrategyA instance")
        except Exception as e:
            print(f"Error creating StrategyA instance: {str(e)}")
            raise
    
    def create_bullish_data(self):
        """Create sample data for bullish signal testing."""
        print("Creating bullish test data")
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
        
        # Add bullish indicator values
        df['atr'] = np.ones(100) * 100  # Constant ATR of 100
        df['cvd'] = np.ones(100) * 1.0  # Positive CVD
        df['vfi'] = np.ones(100) * 0.5  # Positive VFI
        df['tva_rb'] = np.ones(100) * 2.0  # Positive Rising Bull
        df['tva_rr'] = np.zeros(100)  # No Rising Bear
        df['tva_db'] = np.zeros(100)  # No Dropping Bull
        df['tva_dr'] = np.zeros(100)  # No Dropping Bear
        df['tva_upper'] = np.ones(100) * 0.5
        df['tva_lower'] = np.zeros(100)
        
        # Set bullish FVG values for the last few bars
        fvg_signal = np.zeros(100)
        fvg_signal[-10:] = 1  # Bullish signal for last 10 bars
        
        fvg_midpoint = np.zeros(100)
        fvg_midpoint[-10:] = df['close'].iloc[-10:] * 0.98  # FVG midpoint below price
        
        fvg_counter = np.zeros(100)
        fvg_counter[-10:] = np.arange(1, 11)  # Incrementing counter
        
        df['fvg_signal'] = fvg_signal
        df['fvg_midpoint'] = fvg_midpoint
        df['fvg_counter'] = fvg_counter
        
        return {'1m': df}
    
    def create_bearish_data(self):
        """Create sample data for bearish signal testing."""
        print("Creating bearish test data")
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
        
        # Add bearish indicator values
        df['atr'] = np.ones(100) * 100  # Constant ATR of 100
        df['cvd'] = np.ones(100) * -1.0  # Negative CVD
        df['vfi'] = np.ones(100) * -0.5  # Negative VFI
        df['tva_rb'] = np.zeros(100)  # No Rising Bull
        df['tva_rr'] = np.ones(100) * 2.0  # Positive Rising Bear
        df['tva_db'] = np.zeros(100)  # No Dropping Bull
        df['tva_dr'] = np.zeros(100)  # No Dropping Bear
        df['tva_upper'] = np.zeros(100)
        df['tva_lower'] = np.ones(100) * -0.5
        
        # Set bearish FVG values for the last few bars
        fvg_signal = np.zeros(100)
        fvg_signal[-10:] = -1  # Bearish signal for last 10 bars
        
        fvg_midpoint = np.zeros(100)
        fvg_midpoint[-10:] = df['close'].iloc[-10:] * 1.02  # FVG midpoint above price
        
        fvg_counter = np.zeros(100)
        fvg_counter[-10:] = -np.arange(1, 11)  # Decreasing counter
        
        df['fvg_signal'] = fvg_signal
        df['fvg_midpoint'] = fvg_midpoint
        df['fvg_counter'] = fvg_counter
        
        return {'1m': df}
    
    def test_required_timeframes(self):
        """Test that required timeframes are correctly returned."""
        print("Testing required timeframes")
        timeframes = self.strategy.get_required_timeframes()
        self.assertIn('1m', timeframes)
        print(f"Required timeframes: {timeframes}")
    
    def test_validate_config(self):
        """Test configuration validation."""
        print("Testing config validation")
        is_valid, error_msg = self.strategy.validate_config()
        self.assertTrue(is_valid, f"Config validation failed: {error_msg}")
        
        # Test with invalid config (no ATR)
        invalid_config = self.config.copy()
        invalid_config['indicators'] = invalid_config['indicators'].copy()
        invalid_config['indicators']['atr'] = {'enabled': False}
        
        invalid_strategy = StrategyA(invalid_config, self.symbol)
        is_valid, error = invalid_strategy.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("ATR indicator must be enabled", error)
        print(f"Invalid config error message: {error}")
    
    def test_bullish_signal_generation(self):
        """Test generation of bullish signals."""
        print("Testing bullish signal generation")
        # Get bullish test data
        bullish_data = self.create_bullish_data()
        
        # Generate signals
        signals = self.strategy.generate_signals(bullish_data)
        
        # Debug output
        print(f"Generated {len(signals)} signals")
        for s in signals:
            print(f"Signal: {s}")
        
        # Filter for BUY signals
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        
        # We should have at least one BUY signal
        self.assertTrue(len(buy_signals) > 0, "No buy signals generated")
        print(f"Found {len(buy_signals)} buy signals")
    
    def test_bearish_signal_generation(self):
        """Test generation of bearish signals."""
        print("Testing bearish signal generation")
        # Get bearish test data
        bearish_data = self.create_bearish_data()
        
        # Generate signals
        signals = self.strategy.generate_signals(bearish_data)
        
        # Debug output
        print(f"Generated {len(signals)} signals")
        for s in signals:
            print(f"Signal: {s}")
        
        # Filter for SELL signals
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        # We should have at least one SELL signal
        self.assertTrue(len(sell_signals) > 0, "No sell signals generated")
        print(f"Found {len(sell_signals)} sell signals")


if __name__ == '__main__':
    print("Starting Strategy A tests")
    unittest.main(verbosity=2)