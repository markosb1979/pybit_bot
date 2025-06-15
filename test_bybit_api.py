"""
Test Bybit API connectivity directly
"""
import os
import json
from dotenv import load_dotenv
from pybit_bot.core.client import BybitClient, APICredentials

# Load environment variables
load_dotenv()

def main():
    """Test API connectivity"""
    print("=" * 50)
    print("BYBIT API CONNECTION TEST")
    print("=" * 50)
    
    # Get API credentials from environment
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    
    if not api_key or not api_secret:
        print("ERROR: API credentials not found in .env file")
        return
    
    print(f"API Key: {api_key[:4]}...{api_key[-4:]}")
    print(f"Using testnet: YES")
    
    # Create API credentials
    credentials = APICredentials(api_key=api_key, api_secret=api_secret, testnet=True)
    
    # Create client
    client = BybitClient(credentials=credentials)
    
    try:
        # Test connection
        print("\nTesting server time...")
        server_time = client.get_server_time()
        print(f"✓ Server time: {json.dumps(server_time, indent=2)}")
        
        # Get wallet balance
        print("\nGetting wallet balance...")
        balance = client.get_wallet_balance()
        print(f"✓ Wallet balance: {json.dumps(balance, indent=2)}")
        
        # Get BTCUSDT ticker
        print("\nGetting BTCUSDT ticker...")
        ticker = client.get_ticker("BTCUSDT")
        print(f"✓ BTCUSDT ticker: {json.dumps(ticker, indent=2)}")
        
        print("\n✓ All API tests completed successfully!")
        
    except Exception as e:
        print(f"\n✗ API ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()