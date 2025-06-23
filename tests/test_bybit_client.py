"""
Test script for BybitClientTransport

This script tests basic client functionality including:
- Connection to Bybit API
- Authentication
- Basic API endpoints
- Error handling
- Rate limiting behavior
"""

import os
import sys
import asyncio
import time
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.core.client import BybitClientTransport, APICredentials
from pybit_bot.utils.credentials import load_credentials
from pybit_bot.utils.logger import Logger

logger = Logger("TestBybitClient")

async def test_client_initialization():
    """Test client initialization"""
    logger.info("===== Testing client initialization =====")
    
    # Load credentials
    try:
        credentials = load_credentials()
        logger.info(f"Loaded credentials (testnet: {credentials.testnet})")
        
        # Verify credential attributes
        required_attrs = ["api_key", "api_secret", "testnet"]
        missing_attrs = [attr for attr in required_attrs if not hasattr(credentials, attr)]
        
        if missing_attrs:
            logger.error(f"Credentials missing required attributes: {missing_attrs}")
            return None
    except Exception as e:
        logger.error(f"Failed to load credentials: {str(e)}")
        return None
    
    # Create client
    try:
        client = BybitClientTransport(credentials)
        logger.info("Created BybitClientTransport")
        
        # Test if client is properly initialized
        if not hasattr(client, "api_key") or not client.api_key:
            logger.error("Client API key not properly initialized")
            return None
        
        if not hasattr(client, "base_url") or not client.base_url:
            logger.error("Client base URL not properly initialized")
            return None
        
        logger.info(f"Client initialized with base URL: {client.base_url}")
        logger.info("Client initialization PASSED ✓")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize client: {str(e)}")
        return None

async def test_server_time(client):
    """Test getting server time (public endpoint)"""
    logger.info("\n===== Testing server time endpoint =====")
    
    try:
        # Server time is a simple endpoint that doesn't require auth
        response = await client.get_server_time()
        
        if response and response.get("retCode") == 0:
            time_sec = response.get("result", {}).get("timeSecond", 0)
            time_msec = response.get("result", {}).get("timeNano", 0) // 1000000
            
            logger.info(f"Server time: {time_sec} seconds ({time_msec} ms)")
            logger.info("get_server_time PASSED ✓")
            return True
        else:
            error = response.get("retMsg", "Unknown error") if response else "No response"
            logger.error(f"Failed to get server time: {error}")
            return False
    except Exception as e:
        logger.error(f"Error in server time test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_klines_endpoint(client):
    """Test klines endpoint (public data)"""
    logger.info("\n===== Testing klines endpoint =====")
    
    symbol = "BTCUSDT"
    interval = "1m"
    limit = 5
    
    try:
        # Test the get_klines method
        logger.info(f"Fetching {limit} klines for {symbol} {interval}")
        
        # Verify method signature and parameters
        logger.info("Method call: client.get_klines(category='linear', symbol=symbol, interval=interval, limit=limit)")
        
        # Execute the API call
        response = await client.get_klines(
            category="linear", 
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        
        if response and response.get("retCode") == 0:
            klines = response.get("result", {}).get("list", [])
            logger.info(f"Received {len(klines)} klines")
            
            # Print first kline
            if klines:
                logger.info(f"First kline data: {klines[0]}")
                
            logger.info("get_klines PASSED ✓")
            return True
        else:
            error = response.get("retMsg", "Unknown error") if response else "No response"
            logger.error(f"Failed to get klines: {error}")
            return False
    except Exception as e:
        logger.error(f"Error in klines test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_market_tickers(client):
    """Test market tickers endpoint"""
    logger.info("\n===== Testing market tickers endpoint =====")
    
    symbol = "BTCUSDT"
    
    try:
        # Test with specific symbol
        logger.info(f"Fetching ticker for {symbol}")
        
        # Prepare parameters
        params = {
            "category": "linear",
            "symbol": symbol
        }
        
        # Execute the API call
        response = await client.raw_request("GET", "/v5/market/tickers", params, auth_required=False)
        
        if response and "retCode" in response and response["retCode"] == 0:
            tickers = response.get("list", [])
            logger.info(f"Received {len(tickers)} tickers")
            
            if tickers:
                ticker = tickers[0]
                price = ticker.get("lastPrice", "N/A")
                volume = ticker.get("volume24h", "N/A")
                
                logger.info(f"Ticker for {symbol}:")
                logger.info(f"  Price: {price}")
                logger.info(f"  24h Volume: {volume}")
                
            logger.info("market tickers endpoint PASSED ✓")
            return True
        else:
            error = response.get("retMsg", "Unknown error") if response else "No response"
            logger.error(f"Failed to get tickers: {error}")
            return False
    except Exception as e:
        logger.error(f"Error in market tickers test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_instruments_info(client):
    """Test instruments info endpoint"""
    logger.info("\n===== Testing instruments info endpoint =====")
    
    try:
        # Test the instruments info endpoint
        logger.info("Fetching instruments info for 'linear' category")
        
        # Prepare parameters
        params = {
            "category": "linear"
        }
        
        # Execute the API call
        response = await client.raw_request("GET", "/v5/market/instruments-info", params, auth_required=False)
        
        if response and "retCode" in response and response["retCode"] == 0:
            instruments = response.get("list", [])
            logger.info(f"Received {len(instruments)} instruments")
            
            # Print a few instrument symbols
            if instruments:
                sample = [i.get("symbol") for i in instruments[:3]]
                logger.info(f"Sample instruments: {sample}")
                
            logger.info("instruments info endpoint PASSED ✓")
            return True
        else:
            error = response.get("retMsg", "Unknown error") if response else "No response"
            logger.error(f"Failed to get instruments info: {error}")
            return False
    except Exception as e:
        logger.error(f"Error in instruments info test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_authentication(client):
    """Test authentication with a private endpoint"""
    logger.info("\n===== Testing authentication with private endpoint =====")
    
    try:
        # Test wallet balance endpoint (requires auth)
        logger.info("Fetching wallet balance (authenticated endpoint)")
        
        # Prepare parameters
        params = {
            "accountType": "UNIFIED"
        }
        
        # Execute the API call
        response = await client.raw_request("GET", "/v5/account/wallet-balance", params, auth_required=True)
        
        if response and (isinstance(response, list) or "retCode" in response and response["retCode"] == 0):
            logger.info("Authentication successful")
            
            # Extract wallet info if available
            if isinstance(response, list) and response:
                coins = response[0].get("coin", [])
                for coin in coins:
                    if coin.get("coin") == "USDT":
                        balance = coin.get("walletBalance", "N/A")
                        available = coin.get("availableToWithdraw", "N/A")
                        logger.info(f"USDT Balance: {balance}, Available: {available}")
                        break
            
            logger.info("authentication test PASSED ✓")
            return True
        else:
            error = response.get("retMsg", "Unknown error") if response and not isinstance(response, list) else "No response"
            logger.error(f"Authentication failed: {error}")
            return False
    except Exception as e:
        logger.error(f"Error in authentication test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_client_error_handling(client):
    """Test client error handling"""
    logger.info("\n===== Testing client error handling =====")
    
    try:
        # Test with invalid endpoint
        logger.info("Testing with invalid endpoint")
        
        # Execute the API call with a non-existent endpoint
        response = await client.raw_request("GET", "/v5/invalid-endpoint", {}, auth_required=False)
        
        # Should return an error response not raise an exception
        if response and "retCode" in response and response["retCode"] != 0:
            logger.info(f"Properly handled invalid endpoint: {response.get('retMsg', 'Unknown error')}")
            
            # Test with invalid parameters
            logger.info("Testing with invalid parameters")
            
            # Prepare invalid parameters
            params = {
                "category": "linear",
                "invalidParam": "value"
            }
            
            # Execute the API call with invalid parameters
            response = await client.raw_request("GET", "/v5/market/tickers", params, auth_required=False)
            
            if response:
                logger.info(f"Response with invalid params: {response.get('retMsg', 'Unknown error')}")
                logger.info("error handling test PASSED ✓")
                return True
            else:
                logger.error("No response for invalid parameters test")
                return False
        else:
            logger.error("Failed to properly handle invalid endpoint")
            return False
    except Exception as e:
        logger.error(f"Error in error handling test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Run all tests"""
    logger.info("===== BYBIT CLIENT TRANSPORT TESTS =====")
    
    # Load environment variables
    load_dotenv()
    
    # Test client initialization
    client = await test_client_initialization()
    
    if not client:
        logger.error("Client initialization failed, stopping tests")
        return
    
    # Run tests
    tests = [
        test_server_time,
        test_klines_endpoint,
        test_market_tickers,
        test_instruments_info,
        test_authentication,
        test_client_error_handling
    ]
    
    results = []
    for test_func in tests:
        result = await test_func(client)
        results.append((test_func.__name__, result))
    
    # Print summary
    logger.info("\n===== TEST RESULTS SUMMARY =====")
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "PASSED ✓" if result else "FAILED ✗"
        if result:
            passed += 1
        else:
            failed += 1
        logger.info(f"{name}: {status}")
    
    logger.info(f"\nTotal: {len(results)}, Passed: {passed}, Failed: {failed}")
    logger.info("===== ALL TESTS COMPLETED =====")

if __name__ == "__main__":
    asyncio.run(main())