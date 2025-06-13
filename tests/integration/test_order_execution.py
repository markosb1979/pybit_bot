#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import sys
import time
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TestOrderExecution(unittest.TestCase):
    """Integration tests for order execution pipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        print("Setting up Order Execution test")
        
        # Create a mock configuration
        self.config = {
            "risk_management": {
                "max_positions_per_symbol": 2
            },
            "tpsl_manager": {
                "check_interval_ms": 100,
                "default_stop_type": "TRAILING"
            }
        }
        
        # Create a mock order executor
        self.order_executor = MagicMock()
        self.order_executor.execute_order = MagicMock(return_value={"order_id": "test123"})
    
    def test_position_tracking_flow(self):
        """Test the flow of position creation, tracking, and closing."""
        print("Testing position tracking flow")
        
        try:
            from pybit_bot.managers.tpsl_manager import TPSLManager
            
            # Create TPSL manager
            tpsl_manager = TPSLManager(self.config, self.order_executor)
            
            # Add a position
            result = tpsl_manager.add_position(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=20000.0,
                quantity=0.01,
                timestamp=int(time.time() * 1000),
                position_id="test_position_1",
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
            
            # Assert position was added
            self.assertTrue(result)
            
            # Get the position
            position = tpsl_manager.get_position("test_position_1")
            self.assertIsNotNone(position)
            
            print("Position tracking test successful")
            
        except ImportError as e:
            self.fail(f"Failed to import TPSLManager: {e}")
        except Exception as e:
            self.fail(f"Error during test: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)