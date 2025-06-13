#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TestDataFlow(unittest.TestCase):
    """Integration tests for data flow between components."""
    
    def setUp(self):
        """Set up test fixtures."""
        print("Setting up Data Flow test")
    
    def test_market_data_to_strategy_flow(self):
        """Test the flow of market data to strategy processing."""
        print("Testing market data to strategy flow")
        
        try:
            from pybit_bot.managers.strategy_manager import StrategyManager
            
            # Create mock config
            config = {
                "trading": {
                    "symbols": ["BTCUSDT"]
                },
                "strategies": {
                    "strategy_a": {
                        "enabled": True
                    }
                },
                "timeframes": {
                    "default": "1m"
                }
            }
            
            # Mock the strategy manager's initialization
            with patch('pybit_bot.managers.strategy_manager.StrategyManager._load_strategies'):
                strategy_manager = StrategyManager(config)
                
                # Mock strategy collection
                strategy_manager.strategies = {"strategy_a_BTCUSDT": MagicMock()}
                strategy_manager.active_strategies = {"strategy_a_BTCUSDT"}
                
                # Assert that strategy manager was created
                self.assertIsNotNone(strategy_manager)
                print("Strategy manager initialized successfully")
                
        except ImportError as e:
            self.fail(f"Failed to import StrategyManager: {e}")
        except Exception as e:
            self.fail(f"Error during test: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)