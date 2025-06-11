"""
Unit tests for Strategy B implementation.
Tests SMA crossover signal generation and ATR-based stop levels.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategies.strategy_b import StrategyB
from strategies.base_strategy import SignalType, OrderType


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
                'atr_timeframe': '5m'
            }
        }
        
        # Create a sample symbol
        self.symbol = 'BTCUSDT'
        
        # Create a strategy instance
        self.strategy = StrategyB(self.config, self.symbol)
        
        # Create sample data
        self.create_sample_data()
    
    def create_sample_data(self):
        """Create sample market data for testing."""
        # Create date range for 1m data
        start_date = datetime(2023, 1, 1)
        dates_1m = [start_date + timedelta(minutes=i) for i in range(100)]
        
        # Create date range for 5m data
        dates_5m = [start_date + timedelta(minutes=i*5) for i in range(20)]
        
        # Create price data for 1m
        np.random.seed(42)  # For reproducibility
        close = 20000 + np.cumsum(np.random.normal(0, 100, 100))
        high = close + np.random.uniform(50, 200, 100)
        low = close - np.random.uniform(50, 200, 100)
        open_price = close - np.random.normal(0, 100, 100)
        volume = np.random.uniform(1, 10, 100) * 100
        
        # Create DataFrame for 1m
        self.df_1m = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates_1m)
        
        # Create price data for 5m (resampled)
        close_5m = close[::5]
        high_5m = [max(high[i:i+5]) for i in range(0, 100, 5)]
        low_5m = [min(low[i:i+5]) for i in range(0, 100, 5)]
        open_5m = open_price[::5]
        volume_5m = [sum(volume[i:i+5]) for i in range(0, 100, 5)]
        
        # Create DataFrame for 5m
        self.df_5m = pd.DataFrame({
            'open': open_5m,
            'high': high_5m,
            'low': low_5m,
            'close': close_5m,
            'volume': volume_5m
        }, index=dates_5m)
        
        # Add SMA values to 1m dataframe
        fast_sma = np.zeros(100)
        slow_sma = np.zeros(100)
        
        # First 30 bars: fast SMA above slow SMA
        fast_sma[:30] = close[:30] + 200
        slow_sma[:30] = close[:30]
        
        # Bars 30-35: fast SMA crosses below slow SMA (bearish crossover)
        fast_sma[30:33] = close[30:33] + 100
        fast_sma[33:35] = close[33:35] - 100
        slow_sma[30:35] = close[30:35]
        
        # Bars 35-60: fast SMA below slow SMA
        fast_sma[35:60] = close[35:60] - 200
        slow_sma[35:60] = close[35:60]
        
        # Bars 60-65: fast SMA crosses above slow SMA (bullish crossover)
        fast_sma[60:63] = close[60:63] - 100
        fast_sma[63:65] = close[63:65] + 100
        slow_sma[60:65] = close[60:65]
        
        # Bars 65-100: fast SMA above slow SMA
        fast_sma[65:] = close[65:] + 200
        slow_sma[65:] = close[65:]
        
        self.df_1m['fast_sma'] = fast_sma
        self.df_1m['slow_sma'] = slow_sma
        
        # Add ATR to 5m dataframe
        self.df_5m['atr'] = np.ones(20) * 100  # Constant ATR of 100
        
        # Create data dictionary
        self.data = {
            '1m': self.df_1m,
            '5m': self.df_5m
        }
    
    def test_required_timeframes(self):
        """Test that required timeframes are correctly returned."""
        timeframes = self.strategy.get_required_timeframes()
        self.assertIn('1m', timeframes)
        self.assertIn('5m', timeframes)
    
    def test_validate_config(self):
        """Test configuration validation."""
        is_valid, _ = self.strategy.validate_config()
        self.assertTrue(is_valid)
        
        # Test with invalid config (fast SMA > slow SMA)
        invalid_config = self.config.copy()
        invalid_config['strategy_b'] = self.config['strategy_b'].copy()
        invalid_config['strategy_b']['sma_fast_length'] = 40
        invalid_config['strategy_b']['sma_slow_length'] = 30
        invalid_strategy = StrategyB(invalid_config, self.symbol)
        is_valid, error = invalid_strategy.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("Fast SMA length", error)
    
    def test_bullish_signal_generation(self):
        """Test generation of bullish signals at crossover."""
        # Generate signals
        signals = self.strategy.generate_signals(self.data)
        
        # Filter for BUY signals
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        
        # We should have a BUY signal from the crossover at index 63
        self.assertTrue(len(buy_signals) > 0)
        
        if buy_signals:
            # Verify signal attributes
            signal = buy_signals[0]
            self.assertEqual(signal.signal_type, SignalType.BUY)
            self.assertEqual(signal.symbol, self.symbol)
            self.assertEqual(signal.order_type, OrderType.MARKET)
            
            # Check TP/SL calculation
            atr = 100.0
            tp_mult = self.config['strategy_b']['tp_atr_mult']
            trail_mult = self.config['strategy_b']['trail_atr_mult']
            
            # TP should be entry_price + (atr * tp_mult)
            self.assertAlmostEqual(
                signal.tp_price, 
                signal.price + (atr * tp_mult),
                delta=0.01
            )
            
            # SL should be entry_price - (atr * trail_mult)
            self.assertAlmostEqual(
                signal.sl_price, 
                signal.price - (atr * trail_mult),
                delta=0.01
            )
    
    def test_bearish_signal_generation(self):
        """Test generation of bearish signals at crossover."""
        # Generate signals
        signals = self.strategy.generate_signals(self.data)
        
        # Filter for SELL signals
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        # We should have a SELL signal from the crossover at index 33
        self.assertTrue(len(sell_signals) > 0)
        
        if sell_signals:
            # Verify signal attributes
            signal = sell_signals[0]
            self.assertEqual(signal.signal_type, SignalType.SELL)
            self.assertEqual(signal.symbol, self.symbol)
            self.assertEqual(signal.order_type, OrderType.MARKET)
            
            # Check TP/SL calculation
            atr = 100.0
            tp_mult = self.config['strategy_b']['tp_atr_mult']
            trail_mult = self.config['strategy_b']['trail_atr_mult']
            
            # TP should be entry_price - (atr * tp_mult)
            self.assertAlmostEqual(
                signal.tp_price, 
                signal.price - (atr * tp_mult),
                delta=0.01
            )
            
            # SL should be entry_price + (atr * trail_mult)
            self.assertAlmostEqual(
                signal.sl_price, 
                signal.price + (atr * trail_mult),
                delta=0.01
            )
    
    def test_no_signal_without_crossover(self):
        """Test that no signals are generated when there's no crossover."""
        # Create data with no crossovers
        no_crossover_df_1m = self.df_1m.copy()
        
        # Set SMAs with constant relationship (fast always above slow)
        no_crossover_df_1m['fast_sma'] = no_crossover_df_1m['close'] + 200
        no_crossover_df_1m['slow_sma'] = no_crossover_df_1m['close']
        
        no_crossover_data = {
            '1m': no_crossover_df_1m,
            '5m': self.df_5m
        }
        
        # Generate signals
        signals = self.strategy.generate_signals(no_crossover_data)
        
        # We should have no signals
        self.assertEqual(len(signals), 0)
    
    def test_metadata_includes_trailing_params(self):
        """Test that signal metadata includes trailing stop parameters."""
        # Generate signals
        signals = self.strategy.generate_signals(self.data)
        
        # Check that signals include trailing stop parameters
        for signal in signals:
            self.assertIn('trail_activation_pct', signal.metadata)
            self.assertIn('trail_atr_mult', signal.metadata)
            self.assertEqual(signal.metadata['trail_activation_pct'], 
                            self.config['strategy_b']['trail_activation_pct'])
            self.assertEqual(signal.metadata['trail_atr_mult'], 
                            self.config['strategy_b']['trail_atr_mult'])


if __name__ == '__main__':
    unittest.main()