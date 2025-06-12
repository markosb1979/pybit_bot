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

# Update imports to use full package path
from pybit_bot.strategies.strategy_a import StrategyA
from pybit_bot.strategies.base_strategy import SignalType, OrderType


class TestStrategyA(unittest.TestCase):
    """Test suite for Strategy A."""
    
    def setUp(self):
        """Set up test fixtures."""
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
        self.strategy = StrategyA(self.config, self.symbol)
        
        # Create sample data
        self.create_sample_data()
    
    def create_sample_data(self):
        """Create sample market data for testing."""
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
        self.df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        # Add indicators (simplified for testing)
        self.df['atr'] = np.ones(100) * 100  # Constant ATR of 100
        self.df['cvd'] = np.random.uniform(-1, 1, 100)  # Random CVD
        self.df['tva_rb'] = np.random.uniform(0, 1, 100)  # Random TVA values
        self.df['tva_rr'] = np.random.uniform(0, 1, 100)
        self.df['tva_db'] = np.random.uniform(-1, 0, 100)
        self.df['tva_dr'] = np.random.uniform(-1, 0, 100)
        self.df['tva_upper'] = np.ones(100) * 0.5
        self.df['tva_lower'] = np.ones(100) * -0.5
        self.df['vfi'] = np.random.uniform(-1, 1, 100)  # Random VFI
        
        # Add FVG values
        fvg_signal = np.zeros(100)
        fvg_signal[30:40] = 1  # Bullish FVG
        fvg_signal[60:70] = -1  # Bearish FVG
        
        fvg_midpoint = np.zeros(100)
        fvg_midpoint[30:40] = close[30:40]  # Midpoints for bullish FVG
        fvg_midpoint[60:70] = close[60:70]  # Midpoints for bearish FVG
        
        fvg_counter = np.zeros(100)
        fvg_counter[30:40] = np.arange(1, 11)  # Counter for bullish FVG
        fvg_counter[60:70] = -np.arange(1, 11)  # Counter for bearish FVG
        
        self.df['fvg_signal'] = fvg_signal
        self.df['fvg_midpoint'] = fvg_midpoint
        self.df['fvg_counter'] = fvg_counter
        
        # Create data dictionary
        self.data = {'1m': self.df}
    
    def test_required_timeframes(self):
        """Test that required timeframes are correctly returned."""
        timeframes = self.strategy.get_required_timeframes()
        self.assertIn('1m', timeframes)
    
    def test_validate_config(self):
        """Test configuration validation."""
        is_valid, _ = self.strategy.validate_config()
        self.assertTrue(is_valid)
        
        # Test with invalid config (no ATR)
        invalid_config = self.config.copy()
        invalid_config['indicators']['atr']['enabled'] = False
        invalid_strategy = StrategyA(invalid_config, self.symbol)
        is_valid, error = invalid_strategy.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("ATR indicator must be enabled", error)
    
    def test_bullish_signal_generation(self):
        """Test generation of bullish signals."""
        # Set indicators to produce a bullish signal
        bullish_df = self.df.copy()
        bullish_df['cvd'] = 1.0  # Positive CVD
        bullish_df['vfi'] = 0.5  # Positive VFI
        bullish_df['tva_rb'] = 2.0  # Positive Rising Bull
        bullish_df['fvg_signal'] = 1.0  # Bullish FVG
        bullish_df['fvg_midpoint'] = bullish_df['close']  # FVG midpoint at close
        
        bullish_data = {'1m': bullish_df}
        
        # Generate signals
        signals = self.strategy.generate_signals(bullish_data)
        
        # We should have a BUY signal
        self.assertTrue(any(s.signal_type == SignalType.BUY for s in signals))
    
    def test_bearish_signal_generation(self):
        """Test generation of bearish signals."""
        # Set indicators to produce a bearish signal
        bearish_df = self.df.copy()
        bearish_df['cvd'] = -1.0  # Negative CVD
        bearish_df['vfi'] = -0.5  # Negative VFI
        bearish_df['tva_rr'] = 2.0  # Positive Rising Bear
        bearish_df['fvg_signal'] = -1.0  # Bearish FVG
        bearish_df['fvg_midpoint'] = bearish_df['close']  # FVG midpoint at close
        
        bearish_data = {'1m': bearish_df}
        
        # Generate signals
        signals = self.strategy.generate_signals(bearish_data)
        
        # We should have a SELL signal
        self.assertTrue(any(s.signal_type == SignalType.SELL for s in signals))


if __name__ == '__main__':
    unittest.main()