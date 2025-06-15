import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pybit_bot.utils.config_loader import ConfigLoader
from pybit_bot.core.client import BybitClient
from pybit_bot.utils.credentials import APICredentials
from pybit_bot.utils.logger import Logger
from pybit_bot.managers.data_manager import DataManager
from tests.data_manager_adapter import DataManagerTestAdapter
import pandas as pd

async def test_data_manager():
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
    
    # Initialize client without await
    client = BybitClient(credentials=credentials, logger=Logger("TestClient"))
    
    # Test case 1: Initialize DataManager
    data_manager = DataManager(client, config)
    await data_manager.initialize()
    
    # Wrap in adapter for testing
    adapted_manager = DataManagerTestAdapter(data_manager)
    print("DataManager initialized")
    
    # Test case 2: Get supported symbols
    symbols = await adapted_manager.get_symbols()
    print(f"Available symbols: {symbols}")
    
    # Test case 3: Get historical data
    btc_data = await adapted_manager.get_historical_data("BTCUSDT", "1", limit=10)
    # Patch: add columns if missing
    columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
    if isinstance(btc_data, pd.DataFrame):
        if btc_data.shape[1] == 7 and not all(c in btc_data.columns for c in columns):
            btc_data.columns = columns
    print(f"Historical data rows: {len(btc_data)}")
    print(f"Columns: {btc_data.columns.tolist()}")
    
    # Test case 4: Get latest price
    price = await data_manager.get_latest_price("BTCUSDT")
    print(f"Latest BTC price: {price}")
    
    # Test case 5: Calculate indicators - Use adapted_manager here instead of data_manager
    # Patch: ensure correct columns before using
    if isinstance(btc_data, pd.DataFrame):
        # If indicator_data uses btc_data, pass patched df
        indicator_data = await adapted_manager.get_indicator_data("BTCUSDT", klines_df=btc_data)
    else:
        indicator_data = await adapted_manager.get_indicator_data("BTCUSDT")
    print(f"Indicator data columns: {indicator_data.columns.tolist()}")
    
    # Test case 6: Close connections
    await data_manager.close()
    print("DataManager closed")

if __name__ == "__main__":
    asyncio.run(test_data_manager())