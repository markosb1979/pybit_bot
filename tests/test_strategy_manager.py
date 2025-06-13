"""
Unit tests for Strategy Manager.
Tests loading of strategies, market data routing, and signal collection.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to the path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.managers.strategy_manager import StrategyManager
from pybit_bot.strategies.base_strategy import SignalType


class TestStrategyManager(unittest.TestCase):
    """Test suite for Strategy Manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        print("Setting up Strategy Manager test")
        
        # Create a sample configuration
        self.config = {
            'trading': {
                'symbols': ['BTCUSDT', 'ETHUSDT']
            },
            'strategies': {
                'strategy_a': {
                    'enabled': True
                },
                'strategy_b': {
                    'enabled': True
                }
            },
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
            },
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
        
        # Create Strategy Manager
        try:
            self.manager = StrategyManager(self.config)
            print(f"Strategy Manager initialized with {len(self.manager.strategies)} strategies")
        except Exception as e:
            print(f"Error creating Strategy Manager: {str(e)}")
            raise
            
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
        df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        # Add indicators for both bullish and bearish signals
        df['atr'] = np.ones(100) * 100  # Constant ATR of 100
        df['cvd'] = np.ones(100) * 1.0  # Positive CVD for bullish
        df['vfi'] = np.ones(100) * 0.5  # Positive VFI for bullish
        
        # Add FVG indicator for bullish
        df['fvg_signal'] = np.ones(100)  # Bullish FVG signal
        df['fvg_midpoint'] = df['close'] * 0.98
        df['fvg_counter'] = np.arange(1, 101)
        
        # Create SMA crossover for strategy B
        # Important: Set up a proper crossover pattern at the end of the data
        # Previous bar: fast SMA below slow SMA
        # Current bar: fast SMA above slow SMA (bullish crossover)
        df['fast_sma'] = 20100  # Default value
        df['slow_sma'] = 20100  # Default value
        
        # Create a bullish crossover at the end of the DataFrame
        df.loc[df.index[-2], 'fast_sma'] = 20000  # Previous bar: fast below slow
        df.loc[df.index[-2], 'slow_sma'] = 20100
        df.loc[df.index[-1], 'fast_sma'] = 20200  # Current bar: fast above slow
        df.loc[df.index[-1], 'slow_sma'] = 20100
        
        # Add indicator values for bearish signals in another timeframe
        df_5m = df.copy()
        df_5m['cvd'] = -1.0  # Negative CVD for bearish
        df_5m['vfi'] = -0.5  # Negative VFI for bearish
        df_5m['fvg_signal'] = -1.0  # Bearish FVG signal
        
        # Create a bearish crossover for the 5m timeframe
        df_5m.loc[df_5m.index[-2], 'fast_sma'] = 20200  # Previous bar: fast above slow
        df_5m.loc[df_5m.index[-2], 'slow_sma'] = 20100
        df_5m.loc[df_5m.index[-1], 'fast_sma'] = 20000  # Current bar: fast below slow
        df_5m.loc[df_5m.index[-1], 'slow_sma'] = 20100
        
        # Store data in dictionary
        self.data = {
            'BTCUSDT': {'1m': df, '5m': df_5m},
            'ETHUSDT': {'1m': df.copy(), '5m': df_5m.copy()}
        }
    
    def test_strategy_loading(self):
        """Test that strategies are loaded correctly."""
        # We should have 4 strategies (2 strategies x 2 symbols)
        self.assertEqual(len(self.manager.strategies), 4)
        
        # Check that we have the expected strategy IDs
        expected_strategies = [
            'strategy_a_BTCUSDT', 'strategy_a_ETHUSDT',
            'strategy_b_BTCUSDT', 'strategy_b_ETHUSDT'
        ]
        
        for strategy_id in expected_strategies:
            self.assertIn(strategy_id, self.manager.strategies)
            self.assertIn(strategy_id, self.manager.active_strategies)
    
    def test_required_timeframes(self):
        """Test that required timeframes are collected correctly."""
        # Get timeframes for BTC
        btc_timeframes = self.manager.get_required_timeframes('BTCUSDT')
        
        # We should have at least '1m' timeframe
        self.assertIn('1m', btc_timeframes)
        
        # Check that we get the same for ETH
        eth_timeframes = self.manager.get_required_timeframes('ETHUSDT')
        self.assertEqual(set(btc_timeframes), set(eth_timeframes))
    
    def test_signal_generation(self):
        """Test that signals are generated correctly from strategies."""
        # Process BTC data
        signals = self.manager.process_market_data('BTCUSDT', self.data['BTCUSDT'])
        
        # We should have at least one signal
        self.assertTrue(len(signals) > 0)
        
        # Check that we have both BUY and SELL signals
        signal_types = [s.signal_type for s in signals]
        self.assertIn(SignalType.BUY, signal_types)
        
        # Process ETH data
        eth_signals = self.manager.process_market_data('ETHUSDT', self.data['ETHUSDT'])
        
        # Should also generate signals for ETH
        self.assertTrue(len(eth_signals) > 0)
    
    def test_strategy_activation(self):
        """Test activating and deactivating strategies."""
        # First verify both strategies generate signals to start with
        initial_signals = self.manager.process_market_data('BTCUSDT', self.data['BTCUSDT'])
        print(f"Initial signals: {len(initial_signals)}")
        
        # Deactivate strategy A
        result = self.manager.deactivate_strategy('strategy_a_BTCUSDT')
        self.assertTrue(result)
        
        # Check that it's not active
        self.assertFalse(self.manager.is_strategy_active('strategy_a_BTCUSDT'))
        
        # Process data again - should get signals from strategy B only
        signals = self.manager.process_market_data('BTCUSDT', self.data['BTCUSDT'])
        print(f"Signals after deactivating strategy_a: {len(signals)}")
        
        # Debug output if no signals
        if not signals:
            # Check if strategy B is active
            print(f"strategy_b_BTCUSDT active: {self.manager.is_strategy_active('strategy_b_BTCUSDT')}")
            
            # Check the SMA values in the data
            df = self.data['BTCUSDT']['1m']
            print(f"Previous fast SMA: {df['fast_sma'].iloc[-2]}")
            print(f"Previous slow SMA: {df['slow_sma'].iloc[-2]}")
            print(f"Current fast SMA: {df['fast_sma'].iloc[-1]}")
            print(f"Current slow SMA: {df['slow_sma'].iloc[-1]}")
        
        # We should still have signals from strategy_b
        self.assertTrue(len(signals) > 0, "No signals after deactivating strategy_a")
        
        # Reactivate the strategy
        result = self.manager.activate_strategy('strategy_a_BTCUSDT')
        self.assertTrue(result)
        
        # Check that it's active again
        self.assertTrue(self.manager.is_strategy_active('strategy_a_BTCUSDT'))
        
        # Process data again - should get signals from both strategies
        final_signals = self.manager.process_market_data('BTCUSDT', self.data['BTCUSDT'])
        print(f"Final signals after reactivating strategy_a: {len(final_signals)}")
        
        # Should have at least as many signals as before
        self.assertTrue(len(final_signals) >= len(signals))
    
    def test_get_all_symbols(self):
        """Test getting all symbols with strategies."""
        symbols = self.manager.get_all_symbols()
        self.assertEqual(set(symbols), {'BTCUSDT', 'ETHUSDT'})


if __name__ == '__main__':
    unittest.main(verbosity=2)