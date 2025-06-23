"""
Test script for DataManager

This script tests the DataManager's ability to:
- Subscribe to market data
- Fetch historical klines
- Update market data
- Access market data
"""

import os
import sys
import asyncio
import pandas as pd
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.core.client import BybitClientTransport
from pybit_bot.utils.credentials import load_credentials
from pybit_bot.utils.logger import Logger
from pybit_bot.managers.data_manager import DataManager

logger = Logger("TestDataManager")

async def test_data_subscriptions():
    """Test data subscriptions"""
    logger.info("Testing data subscriptions...")
    
    # Load credentials
    credentials = load_credentials()
    
    # Create client
    client = BybitClientTransport(credentials)
    
    # Create a simple config for testing
    config = {
        'general': {
            'data': {
                'lookback_bars': {
                    '1m': 100,
                    '5m': 100,
                    '1h': 50
                }
            }
        }
    }
    
    # Create data manager
    data_manager = DataManager(client, config, logger=logger)
    logger.info("Created DataManager")
    
    # Test subscribing to klines
    symbol = "BTCUSDT"
    timeframes = ["1m", "5m", "1h"]
    
    for timeframe in timeframes:
        result = data_manager.subscribe_klines(symbol, timeframe)
        logger.info(f"Subscription to {symbol} {timeframe}: {'SUCCESS' if result else 'FAILED'}")
    
    logger.info("Data subscriptions test PASSED ✓")
    return data_manager

async def test_fetch_historical_klines(data_manager):
    """Test fetching historical klines"""
    logger.info("Testing historical klines fetching...")
    
    # Load initial data
    logger.info("Loading initial data...")
    result = await data_manager.load_initial_data()
    
    if not result:
        logger.error("Failed to load initial data")
        return False
    
    logger.info("Initial data loaded")
    
    # Check if we have data for all subscriptions
    symbol = "BTCUSDT"
    timeframes = ["1m", "5m", "1h"]
    
    for timeframe in timeframes:
        df = data_manager.get_klines(symbol, timeframe)
        
        if df is None or df.empty:
            logger.error(f"No data for {symbol} {timeframe}")
            continue
            
        logger.info(f"Received {len(df)} klines for {symbol} {timeframe}")
        
        # Print first few rows
        logger.info(f"First few rows:\n{df.head(3)}")
    
    logger.info("Historical klines fetching test PASSED ✓")
    return True

async def test_update_market_data(data_manager):
    """Test updating market data"""
    logger.info("Testing market data updates...")
    
    # Update market data
    logger.info("Updating market data...")
    result = await data_manager.update_market_data()
    
    if not result:
        logger.error("Failed to update market data")
        return False
    
    logger.info("Market data updated")
    
    # Get ticker data
    symbol = "BTCUSDT"
    ticker = data_manager.get_ticker(symbol)
    
    if not ticker:
        logger.warning(f"No ticker data for {symbol}")
    else:
        logger.info(f"Ticker for {symbol}: {ticker}")
    
    # Get current price
    price = data_manager.get_market_price(symbol)
    logger.info(f"Current price for {symbol}: {price}")
    
    logger.info("Market data updates test PASSED ✓")
    return True

async def main():
    """Run all tests"""
    logger.info("===== DATA MANAGER TESTS =====")
    
    # Load environment variables
    load_dotenv()
    
    # Run tests
    data_manager = await test_data_subscriptions()
    if not data_manager:
        logger.error("Data subscriptions test failed, stopping further tests")
        return
    
    await test_fetch_historical_klines(data_manager)
    await test_update_market_data(data_manager)
    
    logger.info("===== ALL TESTS COMPLETED =====")

if __name__ == "__main__":
    asyncio.run(main())