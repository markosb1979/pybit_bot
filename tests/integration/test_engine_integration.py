#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TestEngineIntegration(unittest.TestCase):
    """Integration tests for the Trading Engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        print("Setting up Engine Integration test")
        
        # Create mock configuration
        self.config = {
            "trading": {
                "symbols": ["BTCUSDT"]
            },
            "system": {
                "log_level": "INFO"
            }
        }
    
    def test_engine_initialization(self):
        """Test that the engine initializes correctly."""
        print("Testing engine initialization")
        
        # Import the TradingEngine class
        try:
            from pybit_bot.engine import TradingEngine
            
            # Mock the _load_config method
            with patch.object(TradingEngine, '_load_config', return_value=self.config):
                engine = TradingEngine("dummy_path")
                
                # Assert engine is created
                self.assertIsNotNone(engine)
                self.assertEqual(engine.symbols, ["BTCUSDT"])
                
                print("Engine initialized successfully")
                
        except ImportError as e:
            self.fail(f"Failed to import TradingEngine: {e}")
        except Exception as e:
            self.fail(f"Error during engine initialization: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)