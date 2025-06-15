# order_manager_test.py
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
from pybit_bot.managers.order_manager import OrderManager

async def test_order_manager():
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
    
    # Initialize client with correct parameter name 'credentials'
    client = BybitClient(credentials=credentials, logger=Logger("TestClient"))
    
    # Test case 1: Initialize OrderManager
    order_manager = OrderManager(client, config)
    await order_manager.initialize()
    print("OrderManager initialized")
    
    # Test case 2: Get account balance
    balance = await order_manager.get_account_balance()
    print(f"Account balance: {balance}")
    
    # Test case 3: Calculate position size
    symbol = "BTCUSDT"
    usdt_amount = 50.0
    qty = await order_manager.calculate_position_size(symbol, usdt_amount)
    print(f"Position size for {usdt_amount} USDT: {qty} {symbol}")
    
    # Test case 4: Place and cancel limit order (very small size)
    # Using minimal quantity to avoid actual fills
    small_qty = "0.001"  # Very small BTC quantity
    
    # Get ticker without await
    current_price = client.get_ticker(symbol)
    price_str = str(float(current_price.get("lastPrice", 0)) * 0.8)  # 20% below current price
    
    print(f"Placing limit order: {small_qty} {symbol} @ {price_str}")
    order = await order_manager.place_limit_order(symbol, "Buy", small_qty, price_str)
    print(f"Limit order placed: {order}")
    
    # Wait a moment
    await asyncio.sleep(2)
    
    # Cancel the order
    if "orderId" in order:
        cancel_result = await order_manager.cancel_order(symbol, order["orderId"])
        print(f"Order cancelled: {cancel_result}")
    
    # Test case 5: Get positions
    positions = await order_manager.get_positions(symbol)
    print(f"Current positions: {positions}")
    
    # Test case 6: Get order history
    order_history = await order_manager.get_order_history(symbol)
    print(f"Order history count: {len(order_history)}")
    
    # Test case 7: Close OrderManager
    await order_manager.close()
    print("OrderManager closed")

if __name__ == "__main__":
    asyncio.run(test_order_manager())