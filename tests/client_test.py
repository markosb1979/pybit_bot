# client_test.py
import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pybit_bot.core.client import BybitClient
from pybit_bot.utils.credentials import APICredentials
from pybit_bot.utils.logger import Logger

def test_client():
    # Load API keys from .env file
    load_dotenv()
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    
    # Create credentials object
    credentials = APICredentials(
        api_key=api_key,
        api_secret=api_secret,
        testnet=True
    )
    
    # Initialize client with correct parameter name 'credentials'
    client = BybitClient(credentials=credentials, logger=Logger("TestClient"))
    print("Client initialized with testnet")
    
    # Test case 2: Get server time - no await
    time_response = client.get_server_time()
    print(f"Server time: {time_response}")
    
    # Test case 3: Get wallet balance - no await
    balance = client.get_wallet_balance()
    print(f"Wallet balance: {balance}")
    
    # Test case 4: Get ticker - no await
    ticker = client.get_ticker("BTCUSDT")
    print(f"BTC ticker: {ticker}")
    
    # Test case 5: Get klines - no await
    klines = client.get_klines("BTCUSDT", "1m", limit=5)
    print(f"Klines count: {len(klines)}")
    
    # Test case 6: Test API error handling
    try:
        invalid_response = client.get_ticker("INVALID")
        print("This should not print if error handling works")
    except Exception as e:
        print(f"Error handling test passed: {str(e)}")

if __name__ == "__main__":
    test_client()  # Regular function call, not asyncio.run()