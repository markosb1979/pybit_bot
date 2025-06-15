"""
Test Bybit API connectivity directly without any extra dependencies
"""
import os
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api():
    """Direct API testing"""
    print("=" * 60)
    print("DIRECT BYBIT API TEST")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Get API credentials
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    
    if not api_key or not api_secret:
        print("ERROR: API credentials not found in .env file")
        return False
    
    print(f"API Key: {api_key[:4]}...{api_key[-4:]}")
    print("API Secret: ********")
    
    try:
        # Import the client directly
        from pybit_bot.core.client import BybitClient, APICredentials
        print("✓ Successfully imported BybitClient")
        
        # Create credentials
        print("\nCreating API credentials (testnet=True)...")
        credentials = APICredentials(api_key=api_key, api_secret=api_secret, testnet=True)
        
        # Create client
        print("Initializing Bybit client...")
        client = BybitClient(credentials=credentials)
        
        # Test basic API calls
        print("\nTesting API calls:")
        
        print("  - Testing connection...")
        result = client.test_connection()
        print(f"    ✓ Connection test: {result}")
        
        print("  - Getting server time...")
        server_time = client.get_server_time()
        print(f"    ✓ Server time: {json.dumps(server_time, indent=2)}")
        
        print("  - Getting wallet balance...")
        balance = client.get_wallet_balance()
        print(f"    ✓ Wallet balance: {json.dumps(balance, indent=2)}")
        
        print("  - Getting BTCUSDT ticker...")
        ticker = client.get_ticker("BTCUSDT")
        print(f"    ✓ Current BTCUSDT price: {ticker.get('lastPrice', 'N/A')}")
        
        print("\n✓ All API tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_api()