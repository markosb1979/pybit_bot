# config_loader_test.py
import os
import sys
import json

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pybit_bot.utils.config_loader import ConfigLoader

def test_config_loader():
    # Test case 1: Create with default settings
    config = ConfigLoader()
    print(f"Default config path: {config.config_path}")
    
    # Test case 2: Load custom config file
    test_config = {
        "trading": {"symbol": "ETHUSDT", "position_size_usdt": 25.0},
        "indicators": {"atr": {"enabled": True, "length": 10}}
    }
    
    # Create test config file
    with open("test_config.json", "w") as f:
        json.dump(test_config, f)
    
    config = ConfigLoader(config_path="test_config.json")
    print(f"Custom config loaded: {config.get('trading.symbol') == 'ETHUSDT'}")
    
    # Test case 3: Test get method
    print(f"Config value: {config.get('trading.symbol')}")
    print(f"Default value test: {config.get('nonexistent.path', 'default_value')}")
    
    # Test case 4: Test update method
    config.update('trading.symbol', 'BTCUSDT')
    print(f"Updated value: {config.get('trading.symbol')}")
    
    # Test case 5: Test indicator config loading
    indicator_config = config.load_indicator_config()
    print(f"Indicator config loaded: {indicator_config is not None}")
    
    # Cleanup
    os.remove("test_config.json")

if __name__ == "__main__":
    test_config_loader()