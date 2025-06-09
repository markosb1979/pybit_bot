#!/usr/bin/env python3
"""
Cancel All Orders Script
Cancels all open orders for a specified symbol
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add the parent directory to Python path to enable proper imports
current_dir = Path(__file__).parent
project_root = current_dir.parent if current_dir.name == "pybit_bot" else current_dir
sys.path.insert(0, str(project_root))

# Now import our modules
try:
    from pybit_bot.core.client import BybitClient, APICredentials
    from pybit_bot.utils.logger import Logger
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print("Please ensure you're running from the correct directory")
    sys.exit(1)

def load_credentials_from_env() -> APICredentials:
    """Load API credentials from environment file"""
    logger = Logger("CancelAllOrders")
    
    try:
        # Try to load from .env file
        env_file = Path('.env')
        if env_file.exists():
            logger.info("Loading credentials from .env file")
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#') and line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip('"\'')
        else:
            logger.warning(".env file not found, using environment variables")
        
        api_key = os.getenv('BYBIT_API_KEY')
        api_secret = os.getenv('BYBIT_API_SECRET')
        testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
        
        if not api_key or not api_secret:
            logger.error("Missing API credentials!")
            logger.info("Please ensure .env file contains:")
            logger.info("BYBIT_API_KEY=your_api_key")
            logger.info("BYBIT_API_SECRET=your_api_secret")
            logger.info("BYBIT_TESTNET=true")
            raise Exception("API credentials not found in environment")
            
        logger.info(f"Loaded credentials for {'testnet' if testnet else 'mainnet'}")
        
        return APICredentials(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet
        )
        
    except Exception as e:
        logger.error(f"Failed to load credentials: {str(e)}")
        raise

def main():
    """Cancel all open orders for specified symbol"""
    logger = Logger("CancelAllOrders")
    logger.info("=" * 50)
    logger.info("CANCEL ALL ORDERS UTILITY")
    logger.info("=" * 50)
    
    # Default symbol
    symbol = "BTCUSDT"
    
    # Allow symbol override from command line
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    
    logger.info(f"Cancelling all orders for {symbol}")
    
    try:
        # Load credentials and initialize client
        credentials = load_credentials_from_env()
        client = BybitClient(credentials, logger)
        
        # Test connection
        if client.test_connection():
            logger.info("Connection to Bybit API successful")
        else:
            logger.error("Failed to connect to Bybit API")
            return
        
        # Get active orders first - use the correct method from your client
        active_orders = client.get_open_orders(symbol)
        
        if not active_orders:
            logger.info(f"No active orders found for {symbol}")
            return
        
        logger.info(f"Found {len(active_orders)} active orders for {symbol}")
        
        # Cancel each order individually
        for order in active_orders:
            order_id = order.get("orderId")
            try:
                result = client.cancel_order(symbol=symbol, order_id=order_id)
                logger.info(f"Cancelled order: {order_id}")
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")
        
        logger.info("All orders have been cancelled!")
    
    except Exception as e:
        logger.error(f"Error cancelling orders: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()