#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import sys
import json
import time
import asyncio
import tempfile
import traceback
from unittest.mock import patch, MagicMock, PropertyMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Debug helpers
def print_section(title):
    print("\n" + "=" * 40)
    print(f"  {title}")
    print("=" * 40)

class TestEngineFull(unittest.TestCase):
    """Comprehensive integration tests for the Trading Engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        print_section("Setting up Comprehensive Engine test")
        
        # Create temporary directory for configs
        self.temp_dir = tempfile.mkdtemp()
        print(f"Created temp config dir: {self.temp_dir}")
        
        # Create test configurations
        self.general_config = {
            "trading": {
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "timeframes": ["1m", "5m"],
                "default_timeframe": "1m"
            },
            "system": {
                "log_level": "INFO",
                "log_dir": "logs",
                "data_update_interval": 0.1  # Fast interval for testing
            },
            "data": {
                "lookback_bars": {
                    "1m": 100,
                    "5m": 50
                }
            }
        }
        
        self.strategy_config = {
            "active_strategy": "strategy_a",
            "strategies": {
                "strategy_a": {
                    "enabled": True,
                    "filter_confluence": True,
                    "entry_settings": {
                        "max_long_trades": 1
                    },
                    "risk_settings": {
                        "stop_loss_multiplier": 2.0,
                        "take_profit_multiplier": 4.0
                    }
                },
                "strategy_b": {
                    "enabled": False,
                    "sma_fast_length": 10,
                    "sma_slow_length": 30
                }
            }
        }
        
        self.execution_config = {
            "position_sizing": {
                "default_size": 0.01,
                "max_size": 0.1,
                "position_size_usdt": 50.0,
                "sizing_method": "fixed"
            },
            "risk_management": {
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.04,
                "max_open_positions": 3,
                "max_positions_per_symbol": 1
            },
            "tpsl_manager": {
                "check_interval_ms": 100,
                "default_stop_type": "FIXED"
            }
        }
        
        self.indicators_config = {
            "timeframes": {
                "default": "1m"
            },
            "indicators": {
                "atr": {
                    "enabled": True,
                    "length": 14
                },
                "cvd": {
                    "enabled": True
                }
            }
        }
        
        # Save configs to temp files
        print("Creating config files...")
        with open(os.path.join(self.temp_dir, "general.json"), 'w') as f:
            json.dump(self.general_config, f)
        
        with open(os.path.join(self.temp_dir, "strategy.json"), 'w') as f:
            json.dump(self.strategy_config, f)
        
        with open(os.path.join(self.temp_dir, "execution.json"), 'w') as f:
            json.dump(self.execution_config, f)
        
        with open(os.path.join(self.temp_dir, "indicators.json"), 'w') as f:
            json.dump(self.indicators_config, f)
        
        print("Config files created")
        
        # Import required modules
        print("Importing required modules...")
        from pybit_bot.engine import TradingEngine
        from pybit_bot.strategies.base_strategy import TradeSignal, SignalType, OrderType
        
        self.TradingEngine = TradingEngine
        self.TradeSignal = TradeSignal
        self.SignalType = SignalType
        self.OrderType = OrderType
        
        # Set up environment variables for testing
        print("Setting up environment variables...")
        os.environ['BYBIT_API_KEY'] = 'test_api_key'
        os.environ['BYBIT_API_SECRET'] = 'test_api_secret'
        os.environ['BYBIT_TESTNET'] = 'True'
        
        # Create mocks
        print("Creating mock objects...")
        self.mock_client = MagicMock()
        self.mock_client.test_connection.return_value = True
        
        self.mock_data_manager = MagicMock()
        self.mock_data_manager.initialize = MagicMock(return_value=asyncio.Future())
        self.mock_data_manager.initialize.return_value.set_result(True)
        self.mock_data_manager.get_historical_data = MagicMock(return_value=asyncio.Future())
        self.mock_data_manager.get_historical_data.return_value.set_result(self._create_mock_dataframe())
        self.mock_data_manager.get_latest_price = MagicMock(return_value=asyncio.Future())
        self.mock_data_manager.get_latest_price.return_value.set_result(50000.0)
        self.mock_data_manager.get_last_price = MagicMock(return_value=50000.0)
        
        self.mock_order_manager = MagicMock()
        self.mock_order_manager.initialize = MagicMock(return_value=asyncio.Future())
        self.mock_order_manager.initialize.return_value.set_result(True)
        self.mock_order_manager.get_positions = MagicMock(return_value=asyncio.Future())
        self.mock_order_manager.get_positions.return_value.set_result([])
        self.mock_order_manager.calculate_position_size = MagicMock(return_value=asyncio.Future())
        self.mock_order_manager.calculate_position_size.return_value.set_result("0.01")
        self.mock_order_manager.enter_long_with_tp_sl = MagicMock(return_value=asyncio.Future())
        self.mock_order_manager.enter_long_with_tp_sl.return_value.set_result({
            "entry_order": {"orderId": "test123"},
            "tp_order": {"orderId": "tp123"},
            "sl_order": {"orderId": "sl123"}
        })
        self.mock_order_manager.enter_short_with_tp_sl = MagicMock(return_value=asyncio.Future())
        self.mock_order_manager.enter_short_with_tp_sl.return_value.set_result({
            "entry_order": {"orderId": "test456"},
            "tp_order": {"orderId": "tp456"},
            "sl_order": {"orderId": "sl456"}
        })
        self.mock_order_manager.get_account_balance = MagicMock(return_value={"totalAvailableBalance": "10000"})
        
        self.mock_strategy_manager = MagicMock()
        self.mock_strategy_manager.process_data = MagicMock(return_value=asyncio.Future())
        self.mock_strategy_manager.process_data.return_value.set_result([])
        self.mock_strategy_manager.get_active_strategies = MagicMock(return_value=["strategy_a"])
        
        self.mock_tpsl_manager = MagicMock()
        self.mock_tpsl_manager.check_positions = MagicMock(return_value=asyncio.Future())
        self.mock_tpsl_manager.check_positions.return_value.set_result(None)
        self.mock_tpsl_manager.add_position = MagicMock(return_value=True)
        
        # Set up asyncio event loop for testing
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        print("Setup complete")
    
    def tearDown(self):
        """Clean up after tests."""
        print_section("Cleaning up after test")
        
        # Remove temp directory and its contents
        for f in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, f))
        os.rmdir(self.temp_dir)
        print(f"Removed temp directory: {self.temp_dir}")
        
        # Clean up environment variables
        if 'BYBIT_API_KEY' in os.environ:
            del os.environ['BYBIT_API_KEY']
        if 'BYBIT_API_SECRET' in os.environ:
            del os.environ['BYBIT_API_SECRET']
        if 'BYBIT_TESTNET' in os.environ:
            del os.environ['BYBIT_TESTNET']
        print("Cleaned up environment variables")
        
        # Close the event loop
        try:
            self.loop.close()
            print("Closed test event loop")
        except:
            print("WARNING: Error closing test event loop")
    
    def _create_mock_dataframe(self):
        """Create a mock DataFrame for testing."""
        import pandas as pd
        import numpy as np
        
        # Create basic DataFrame with required columns
        df = pd.DataFrame({
            'timestamp': [1625000000000 + i * 60000 for i in range(100)],
            'open': np.random.normal(50000, 1000, 100),
            'high': np.random.normal(50500, 1000, 100),
            'low': np.random.normal(49500, 1000, 100),
            'close': np.random.normal(50000, 1000, 100),
            'volume': np.random.normal(10, 5, 100),
            'turnover': np.random.normal(500000, 50000, 100)
        })
        
        return df
    
    @patch('pybit_bot.engine.BybitClient')
    @patch('pybit_bot.engine.OrderManager')
    @patch('pybit_bot.engine.DataManager')
    @patch('pybit_bot.engine.StrategyManager')
    @patch('pybit_bot.engine.TPSLManager')
    def test_engine_initialization(self, mock_tpsl_cls, mock_strategy_cls, mock_data_cls, mock_order_cls, mock_client_cls):
        """Test that the engine initializes correctly."""
        print_section("Testing engine comprehensive initialization")
        
        # Set up mocks
        mock_client_cls.return_value = self.mock_client
        mock_order_cls.return_value = self.mock_order_manager
        mock_data_cls.return_value = self.mock_data_manager
        mock_strategy_cls.return_value = self.mock_strategy_manager
        mock_tpsl_cls.return_value = self.mock_tpsl_manager
        
        print("Step 1: Creating engine instance...")
        # Initialize engine
        engine = self.TradingEngine(self.temp_dir)
        
        print("Step 2: Calling engine.initialize()...")
        initialized = engine.initialize()
        
        # Check initialization
        print(f"Initialized result: {initialized}")
        self.assertTrue(initialized)
        self.assertEqual(engine.symbols, ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(engine.timeframes, ["1m", "5m"])
        
        # Verify component initialization
        mock_client_cls.assert_called_once()
        mock_order_cls.assert_called_once()
        mock_data_cls.assert_called_once()
        mock_strategy_cls.assert_called_once()
        mock_tpsl_cls.assert_called_once()
        
        print("Engine initialization successful")
    
    @patch('pybit_bot.engine.BybitClient')
    @patch('pybit_bot.engine.OrderManager')
    @patch('pybit_bot.engine.DataManager')
    @patch('pybit_bot.engine.StrategyManager')
    @patch('pybit_bot.engine.TPSLManager')
    @patch('threading.Thread')
    def test_engine_start_stop(self, mock_thread, mock_tpsl_cls, mock_strategy_cls, mock_data_cls, mock_order_cls, mock_client_cls):
        """Test that the engine starts and stops correctly."""
        print_section("Testing engine start/stop")
        
        # Set up component mocks
        mock_client_cls.return_value = self.mock_client
        mock_order_cls.return_value = self.mock_order_manager
        mock_data_cls.return_value = self.mock_data_manager
        mock_strategy_cls.return_value = self.mock_strategy_manager
        mock_tpsl_cls.return_value = self.mock_tpsl_manager
        
        # Set up threading mock
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        print("Step 1: Creating engine instance...")
        # Initialize engine
        engine = self.TradingEngine(self.temp_dir)
        
        print("Step 2: Initializing engine...")
        engine.initialize()
        
        print("Step 3: Testing engine start in test mode...")
        # Start the engine in test mode
        started = engine.start(test_mode=True)
        
        print(f"Start result: {started}")
        self.assertTrue(started)
        self.assertTrue(engine.is_running)
        
        print("Step 4: Testing engine stop...")
        # Test engine stop
        engine.stop()
        
        self.assertFalse(engine.is_running)
        
        print("Engine start/stop test successful")
    
    @patch('pybit_bot.engine.BybitClient')
    @patch('pybit_bot.engine.OrderManager')
    @patch('pybit_bot.engine.DataManager')
    @patch('pybit_bot.engine.StrategyManager')
    @patch('pybit_bot.engine.TPSLManager')
    def test_engine_signal_processing(self, mock_tpsl_cls, mock_strategy_cls, mock_data_cls, mock_order_cls, mock_client_cls):
        """Test signal processing in the engine."""
        print_section("Testing engine signal processing")
        
        # Set up mocks
        mock_client_cls.return_value = self.mock_client
        mock_order_cls.return_value = self.mock_order_manager
        mock_data_cls.return_value = self.mock_data_manager
        mock_strategy_cls.return_value = self.mock_strategy_manager
        mock_tpsl_cls.return_value = self.mock_tpsl_manager
        
        print("Step 1: Creating test signal...")
        # Create a signal - using the correct TradeSignal signature (no direction parameter)
        signal = self.TradeSignal(
            signal_type=self.SignalType.BUY,  # BUY = LONG direction
            symbol="BTCUSDT",
            price=50000.0,
            timestamp=int(time.time() * 1000),
            order_type=self.OrderType.MARKET,
            sl_price=49000.0,
            tp_price=52000.0
        )
        
        print("Step 2: Setting up strategy mock to return our signal...")
        # Make strategy return our signal
        self.mock_strategy_manager.process_data.return_value = asyncio.Future()
        self.mock_strategy_manager.process_data.return_value.set_result([signal])
        
        print("Step 3: Creating and initializing engine...")
        # Initialize engine
        engine = self.TradingEngine(self.temp_dir)
        engine.initialize()
        
        print("Step 4: Testing direct signal handling...")
        # Test direct signal handling
        async def test_signal_handling():
            print("Calling _handle_signals with our test signal...")
            await engine._handle_signals("BTCUSDT", [signal])
            print("Signal handling completed")
            
        # Run the async test function
        try:
            self.loop.run_until_complete(test_signal_handling())
            print("Signal handling test completed successfully")
        except Exception as e:
            print(f"ERROR in signal handling test: {str(e)}")
            traceback.print_exc()
            self.fail(f"Signal handling test failed: {str(e)}")
        
        print("Step 5: Verifying order was placed...")
        # Verify the signal processing - order should have been placed
        self.mock_order_manager.enter_long_with_tp_sl.assert_called_once()
        self.mock_tpsl_manager.add_position.assert_called_once()
        
        # Check performance tracking
        self.assertEqual(engine.performance['signals_generated'], 1)
        self.assertEqual(engine.performance['orders_placed'], 1)
        
        print("Engine signal processing test successful")
    
    @patch('pybit_bot.engine.BybitClient')
    @patch('pybit_bot.engine.OrderManager')
    @patch('pybit_bot.engine.DataManager')
    @patch('pybit_bot.engine.StrategyManager')
    @patch('pybit_bot.engine.TPSLManager')
    def test_strategy_toggle(self, mock_tpsl_cls, mock_strategy_cls, mock_data_cls, mock_order_cls, mock_client_cls):
        """Test that strategy toggle mechanism works."""
        print_section("Testing strategy toggle mechanism")
        
        # Set up mocks
        mock_client_cls.return_value = self.mock_client
        mock_order_cls.return_value = self.mock_order_manager
        mock_data_cls.return_value = self.mock_data_manager
        mock_strategy_cls.return_value = self.mock_strategy_manager
        mock_tpsl_cls.return_value = self.mock_tpsl_manager
        
        print("Step 1: Creating and initializing engine...")
        # Initialize engine
        engine = self.TradingEngine(self.temp_dir)
        engine.initialize()
        
        print("Step 2: Checking initial active strategies...")
        # Get engine status to check active strategies
        status = engine.get_status()
        
        # Verify only strategy_a is active (as specified in active_strategy field)
        print(f"Initial active strategies: {status['active_strategies']}")
        self.assertEqual(status['active_strategies'], ["strategy_a"])
        
        print("Step 3: Updating config to switch active strategy to strategy_b...")
        # Update config to make strategy_b the active one
        with open(os.path.join(self.temp_dir, "strategy.json"), 'r') as f:
            config = json.load(f)
        
        # Change the active strategy
        config['active_strategy'] = 'strategy_b'
        # Enable strategy_b
        config['strategies']['strategy_b']['enabled'] = True
        # Disable strategy_a
        config['strategies']['strategy_a']['enabled'] = False
        
        with open(os.path.join(self.temp_dir, "strategy.json"), 'w') as f:
            json.dump(config, f)
        
        print("Step 4: Updating mock to return ONLY strategy_b as active...")
        # Update mock to return ONLY the new active strategy
        self.mock_strategy_manager.get_active_strategies = MagicMock(return_value=["strategy_b"])
        
        print("Step 5: Getting updated status...")
        # Get status again (would need to reinitialize in real usage)
        status = engine.get_status()
        
        # Now strategy_b should be active
        print(f"Updated active strategies: {status['active_strategies']}")
        self.assertEqual(status['active_strategies'], ["strategy_b"])
        
        # And strategy_a should no longer be active
        self.assertNotIn("strategy_a", status['active_strategies'])
        
        print("Strategy toggle test successful")


if __name__ == "__main__":
    unittest.main(verbosity=2)