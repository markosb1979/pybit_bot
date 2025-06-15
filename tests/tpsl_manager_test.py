# tpsl_manager_test.py
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
from pybit_bot.managers.order_manager import OrderManager
from pybit_bot.managers.tpsl_manager import TPSLManager

async def test_tpsl_manager():
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
    
    order_manager = OrderManager(client, config)
    await order_manager.initialize()
    
    # Test case 1: Initialize TPSLManager
    tpsl_manager = TPSLManager(order_manager, data_manager, config)
    await tpsl_manager.start()
    print("TPSLManager started")
    
    # Test case 2: Test TP/SL calculation
    symbol = "BTCUSDT"
    entry_price = 50000.0
    side = "Buy"
    atr = 500.0
    
    tp_price, sl_price = tpsl_manager._calculate_tp_sl(entry_price, side, atr)
    print(f"TP calculation test: Entry {entry_price}, TP {tp_price}, SL {sl_price}")
    
    # Test case 3: Test simulated position management
    # This is a simulation - we're not actually placing orders
    print("Simulating position management...")
    
    # Create a simulated position
    tpsl_manager.active_trades[symbol] = {
        "symbol": symbol,
        "entry_price": entry_price,
        "side": side,
        "atr": atr,
        "position_size": 0.01,
        "entry_order_id": "sim_order_1",
        "tp_order_id": "sim_tp_1",
        "sl_order_id": "sim_sl_1",
        "tp_price": tp_price,
        "sl_price": sl_price,
        "initial_sl_price": sl_price,
        "initial_tp_price": tp_price,
        "trailing_active": False,
        "best_price": entry_price,
        "timestamp": asyncio.get_event_loop().time()
    }
    
    # Simulate price movement to activate trailing stop
    current_price = entry_price + (tp_price - entry_price) * 0.6  # 60% toward TP
    print(f"Simulating price movement to {current_price}")
    
    # Update trailing stop based on new price
    result = await tpsl_manager._update_trailing_stop(symbol, current_price)
    print(f"Trailing stop activated: {result}")
    print(f"New stop price: {tpsl_manager.active_trades[symbol]['sl_price']}")
    
    # Test case 4: Test cancellation
    cancel_result = await tpsl_manager.cancel_tpsl(symbol)
    print(f"Cancel TP/SL result: {cancel_result}")
    
    # Test case 5: Stop TPSLManager
    await tpsl_manager.stop()
    print("TPSLManager stopped")
    
    # Cleanup
    await data_manager.close()
    await order_manager.close()

if __name__ == "__main__":
    asyncio.run(test_tpsl_manager())