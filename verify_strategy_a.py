"""
Unit tests for TPSL Manager.
Tests position tracking, trailing stops, and TP/SL execution.
"""

import unittest
import time
from unittest.mock import MagicMock
import sys
import os

# Add parent directory to the path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.managers.tpsl_manager import TPSLManager, Position, PositionSide, StopType


class TestTPSLManager(unittest.TestCase):
    """Test suite for TPSL Manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        print("Setting up TPSL Manager test")
        
        # Create a mock order executor
        self.order_executor = MagicMock()
        self.order_executor.execute_order = MagicMock(return_value={"order_id": "123456"})
        
        # Create a sample configuration
        self.config = {
            'tpsl_manager': {
                'check_interval_ms': 100,
                'default_stop_type': 'TRAILING'
            },
            'risk_management': {
                'max_positions_per_symbol': 2
            }
        }
        
        # Create TPSL Manager
        self.manager = TPSLManager(self.config, self.order_executor)
        
        # Create sample positions
        self.create_sample_positions()
    
    def create_sample_positions(self):
        """Create sample positions for testing."""
        print("Creating sample positions")
        
        # Add a long position
        self.manager.add_position(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=20000.0,
            quantity=0.1,
            timestamp=int(time.time() * 1000),
            position_id="long_position_1",
            sl_price=19500.0,
            tp_price=21000.0,
            stop_type="TRAILING",
            trail_config={
                'activation_pct': 0.5,
                'callback_rate': 0.3,
                'atr_multiplier': 2.0,
                'current_atr': 100.0
            }
        )
        
        # Add a short position
        self.manager.add_position(
            symbol="ETHUSDT",
            side="SHORT",
            entry_price=1500.0,
            quantity=1.0,
            timestamp=int(time.time() * 1000),
            position_id="short_position_1",
            sl_price=1550.0,
            tp_price=1400.0,
            stop_type="FIXED",
            trail_config=None
        )
    
    def test_add_position(self):
        """Test adding positions."""
        # Check that existing positions were added in setUp
        positions = self.manager.get_active_positions()
        self.assertEqual(len(positions), 2, "Should have 2 positions from setUp")
        
        # Add another position with new ID
        result = self.manager.add_position(
            symbol="BTCUSDT",
            side="SHORT",
            entry_price=21000.0,
            quantity=0.1,
            timestamp=int(time.time() * 1000),
            position_id="short_position_2", # New unique ID
            sl_price=21500.0,
            tp_price=20000.0,
            stop_type="TRAILING",
            trail_config={
                'activation_pct': 0.5,
                'callback_rate': 0.3,
                'atr_multiplier': 2.0,
                'current_atr': 100.0
            }
        )
        
        # Check that position was added
        self.assertTrue(result, "Should successfully add a new position")
        positions = self.manager.get_active_positions()
        self.assertEqual(len(positions), 3, "Should now have 3 positions total")
        
        # Try to add a position with existing ID (should fail)
        result = self.manager.add_position(
            symbol="XRPUSDT", # Different symbol to avoid max position limit
            side="LONG",
            entry_price=0.5,
            quantity=100.0,
            timestamp=int(time.time() * 1000),
            position_id="long_position_1",  # Duplicate ID
            sl_price=0.45,
            tp_price=0.55
        )
        
        # Check that position was not added
        self.assertFalse(result, "Should fail to add position with duplicate ID")
        positions = self.manager.get_active_positions()
        self.assertEqual(len(positions), 3, "Should still have 3 positions total")
        
        # Now test max positions per symbol
        # Get BTC positions to check current count
        btc_positions = self.manager.get_active_positions("BTCUSDT")
        self.assertEqual(len(btc_positions), 2, "Should have 2 BTCUSDT positions")
        
        # Try to add one more BTCUSDT position (should fail, as max is 2)
        result = self.manager.add_position(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=20000.0,
            quantity=0.1,
            timestamp=int(time.time() * 1000),
            position_id="long_position_3",
            sl_price=19500.0,
            tp_price=21000.0
        )
        
        # Check that position was not added due to max positions limit
        self.assertFalse(result, "Should fail to add position beyond max limit")
        btc_positions = self.manager.get_active_positions("BTCUSDT")
        self.assertEqual(len(btc_positions), 2, "Should still have 2 BTCUSDT positions")
        
        # Add a position for a new symbol (should succeed)
        result = self.manager.add_position(
            symbol="SOLUSDT",
            side="LONG",
            entry_price=100.0,
            quantity=1.0,
            timestamp=int(time.time() * 1000),
            position_id="sol_position_1",
            sl_price=95.0,
            tp_price=110.0
        )
        
        # Check that position was added
        self.assertTrue(result, "Should add position for new symbol")
        positions = self.manager.get_active_positions()
        self.assertEqual(len(positions), 4, "Should now have 4 positions total")
    
    def test_trailing_stop(self):
        """Test trailing stop functionality."""
        # Get the initial long position
        position = self.manager.get_position("long_position_1")
        self.assertIsNotNone(position)
        
        initial_sl = position['sl_price']
        
        # Trailing should not yet be activated
        self.assertFalse(position['is_trailing_activated'])
        
        # Calculate activation level (entry + 50% of TP distance)
        entry = position['entry_price']
        tp = position['tp_price']
        activation_level = entry + (tp - entry) * 0.5  # 20000 + (21000 - 20000) * 0.5 = 20500
        
        # Update price but below activation (should not change SL)
        actions = self.manager.update_market_data("BTCUSDT", 20300.0, 100.0)
        self.assertEqual(len(actions), 0)
        
        position = self.manager.get_position("long_position_1")
        self.assertFalse(position['is_trailing_activated'])
        self.assertEqual(position['sl_price'], initial_sl)
        
        # Update price above activation (should activate trailing)
        actions = self.manager.update_market_data("BTCUSDT", 20600.0, 100.0)
        self.assertEqual(len(actions), 0)
        
        position = self.manager.get_position("long_position_1")
        self.assertTrue(position['is_trailing_activated'])
        
        # Update with a higher price (should move SL up)
        actions = self.manager.update_market_data("BTCUSDT", 20800.0, 100.0)
        self.assertEqual(len(actions), 0)
        
        position = self.manager.get_position("long_position_1")
        self.assertGreater(position['sl_price'], initial_sl)
        
        # Update with an even higher price
        actions = self.manager.update_market_data("BTCUSDT", 21000.0, 100.0)
        
        # This should hit the TP
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['action'], 'TAKE_PROFIT')
        
        # Position should be closed
        position = self.manager.get_position("long_position_1")
        self.assertFalse(position['is_active'])
    
    def test_stop_loss_trigger(self):
        """Test stop loss triggering."""
        # Get the initial short position
        position = self.manager.get_position("short_position_1")
        self.assertIsNotNone(position)
        
        initial_sl = position['sl_price']
        
        # Update price but below SL (for short position, SL is above entry)
        actions = self.manager.update_market_data("ETHUSDT", 1520.0, 50.0)
        self.assertEqual(len(actions), 0)
        
        # Position should still be active
        position = self.manager.get_position("short_position_1")
        self.assertTrue(position['is_active'])
        
        # Update price above SL
        actions = self.manager.update_market_data("ETHUSDT", 1560.0, 50.0)
        
        # This should hit the SL
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['action'], 'STOP_LOSS')
        
        # Position should be closed
        position = self.manager.get_position("short_position_1")
        self.assertFalse(position['is_active'])
        
        # Check that order executor was called
        self.order_executor.execute_order.assert_called_once()
    
    def test_position_update(self):
        """Test updating position parameters."""
        # Update stop loss and take profit levels
        result = self.manager.update_position("long_position_1", {
            'sl_price': 19000.0,
            'tp_price': 22000.0
        })
        
        self.assertTrue(result)
        
        # Check that the update was applied
        position = self.manager.get_position("long_position_1")
        self.assertEqual(position['sl_price'], 19000.0)
        self.assertEqual(position['tp_price'], 22000.0)
        
        # Try to update a non-existent position
        result = self.manager.update_position("non_existent", {
            'sl_price': 19000.0
        })
        
        self.assertFalse(result)
    
    def test_manual_close(self):
        """Test manually closing a position."""
        # Close a position
        close_price = 20500.0
        close_timestamp = int(time.time() * 1000)
        realized_pnl = 50.0
        
        result = self.manager.close_position(
            "long_position_1",
            close_price,
            close_timestamp,
            realized_pnl
        )
        
        self.assertTrue(result)
        
        # Check that the position is closed
        position = self.manager.get_position("long_position_1")
        self.assertFalse(position['is_active'])
        self.assertEqual(position['close_price'], close_price)
        self.assertEqual(position['close_timestamp'], close_timestamp)
        self.assertEqual(position['realized_pnl'], realized_pnl)
        
        # Check that it's in the closed positions list
        closed = self.manager.get_closed_positions()
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]['position_id'], "long_position_1")
        
        # Try to close a non-existent position
        result = self.manager.close_position(
            "non_existent",
            close_price,
            close_timestamp,
            realized_pnl
        )
        
        self.assertFalse(result)
    
    def test_position_stats(self):
        """Test position statistics."""
        # Close positions with PnL
        self.manager.close_position(
            "long_position_1",
            21000.0,
            int(time.time() * 1000),
            100.0  # Profit
        )
        
        self.manager.close_position(
            "short_position_1",
            1550.0,
            int(time.time() * 1000),
            -50.0  # Loss
        )
        
        # Get overall stats
        stats = self.manager.get_position_stats()
        
        self.assertEqual(stats['active_count'], 0)
        self.assertEqual(stats['closed_count'], 2)
        self.assertEqual(stats['win_count'], 1)
        self.assertEqual(stats['loss_count'], 1)
        self.assertEqual(stats['win_rate'], 0.5)
        self.assertEqual(stats['total_pnl'], 50.0)
        self.assertEqual(stats['average_pnl'], 25.0)
        
        # Get stats for BTC only
        btc_stats = self.manager.get_position_stats("BTCUSDT")
        
        self.assertEqual(btc_stats['active_count'], 0)
        self.assertEqual(btc_stats['closed_count'], 1)
        self.assertEqual(btc_stats['win_count'], 1)
        self.assertEqual(btc_stats['loss_count'], 0)
        self.assertEqual(btc_stats['win_rate'], 1.0)
        self.assertEqual(btc_stats['total_pnl'], 100.0)
        self.assertEqual(btc_stats['average_pnl'], 100.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)