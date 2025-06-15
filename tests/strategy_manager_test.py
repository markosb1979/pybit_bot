# strategy_manager_test.py
import asyncio
import os
import sys
import pandas as pd
from dotenv import load_dotenv

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pybit_bot.utils.config_loader import ConfigLoader
from pybit_bot.core.client import BybitClient
from pybit_bot.utils.credentials import APICredentials
from pybit_bot.utils.logger import Logger
from pybit_bot.managers.data_manager import DataManager
from pybit_bot.managers.order_manager import OrderManager
from pybit_bot.managers.tpsl_manager import TPSLManager
from pybit_bot.managers.strategy_manager import StrategyManager
from tests.data_manager_adapter import DataManagerTestAdapter

async def test_strategy_manager():
    # Load API keys from .env file
    load_dotenv()
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    
    # Initialize dependencies
    config = ConfigLoader()
    
    # Create credentials object
    credentials = APICredentials(
        api_key=api_key,
        api_secret=api_secret,
        testnet=True
    )
    
    # Initialize client
    client = BybitClient(credentials=credentials, logger=Logger("TestClient"))
    
    # Initialize managers
    data_manager = DataManager(client, config)
    await data_manager.initialize()
    
    # Wrap data manager in adapter for testing
    adapted_manager = DataManagerTestAdapter(data_manager)
    
    order_manager = OrderManager(client, config)
    await order_manager.initialize()
    
    tpsl_manager = TPSLManager(order_manager, data_manager, config)
    await tpsl_manager.start()
    
    # Test case 1: Initialize StrategyManager
    # Use the adapted manager for the strategy
    strategy_manager = StrategyManager(order_manager, adapted_manager, tpsl_manager, config)
    print("StrategyManager initialized")
    
    # Test case 2: Test signal checking
    symbol = "BTCUSDT"
    
    # Create a sample DataFrame row with indicator values
    test_row = pd.Series({
        'open': 50000.0,
        'high': 51000.0,
        'low': 49000.0,
        'close': 50500.0,
        'volume': 100.0,
        'cvd': 5.0,           # Positive for long signal
        'rb': 2.0,            # Positive for long signal
        'rr': -1.0,           # Negative for long signal
        'vfi': 0.5,           # Positive for long signal
        'fvg_signal': 1,      # 1 for bullish gap
        'fvg_midpoint': 49800.0,
        'atr': 500.0
    })
    
    # Check if this generates a signal - adjust for your actual implementation
    if hasattr(strategy_manager, "_check_signal"):
        signal = strategy_manager._check_signal(test_row, symbol)
        print(f"Signal check result: {signal}")
    else:
        print("Signal checking method not available with that name")
    
    # Test case 3: Start and stop StrategyManager
    await strategy_manager.start()
    print("StrategyManager started")
    
    await asyncio.sleep(5)  # Let it run briefly
    
    await strategy_manager.stop()
    print("StrategyManager stopped")
    
    # Cleanup
    await tpsl_manager.stop()
    await data_manager.close()
    await order_manager.close()

if __name__ == "__main__":
    asyncio.run(test_strategy_manager())