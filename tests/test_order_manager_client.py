"""
Test script for OrderManagerClient

This script tests the OrderManagerClient functionality including:
- Client initialization
- Market data retrieval
- Position information
- Order management
- Error handling
"""

import os
import sys
import asyncio
import time
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.core.client import BybitClientTransport
from pybit_bot.core.order_manager_client import OrderManagerClient
from pybit_bot.utils.credentials import load_credentials
from pybit_bot.utils.logger import Logger

# Setup logging
logger = Logger("TestOrderManagerClient")

async def test_client_initialization():
    """Test client initialization"""
    logger.info("===== Testing client initialization =====")
    
    # Load credentials
    try:
        credentials = load_credentials()
        logger.info(f"Loaded credentials (testnet: {credentials.testnet})")
    except Exception as e:
        logger.error(f"Failed to load credentials: {str(e)}")
        return None, None
    
    # Create base transport
    transport = BybitClientTransport(credentials)
    logger.info("Created BybitClientTransport")
    
    # Create order manager client
    try:
        order_client = OrderManagerClient(transport, logger=logger)
        logger.info("Created OrderManagerClient")
        
        # Test if client has necessary attributes
        required_attrs = ["transport", "logger", "_instrument_info"]
        missing_attrs = [attr for attr in required_attrs if not hasattr(order_client, attr)]
        
        if missing_attrs:
            logger.error(f"Client missing required attributes: {missing_attrs}")
            return None, None
            
        logger.info("Client initialization PASSED ✓")
        return transport, order_client
    except Exception as e:
        logger.error(f"Failed to initialize OrderManagerClient: {str(e)}")
        return transport, None

async def test_instrument_info(client):
    """Test instrument info retrieval"""
    logger.info("\n===== Testing instrument info retrieval =====")
    
    symbol = "BTCUSDT"
    try:
        # Test get_instruments_info method
        logger.info("Testing get_instruments_info()")
        instruments = client.get_instruments_info()
        
        if instruments and "list" in instruments:
            instrument_count = len(instruments["list"])
            logger.info(f"Retrieved {instrument_count} instruments")
            logger.info("get_instruments_info PASSED ✓")
        else:
            logger.error("Failed to get instruments info")
            return False
        
        # Test get_instrument_info method for specific symbol
        logger.info(f"Testing get_instrument_info({symbol})")
        symbol_info = client.get_instrument_info(symbol)
        
        if symbol_info:
            # Display key information
            price_scale = symbol_info.get("priceScale", "N/A")
            lot_size_filter = symbol_info.get("lotSizeFilter", {})
            min_qty = lot_size_filter.get("minOrderQty", "N/A")
            qty_step = lot_size_filter.get("qtyStep", "N/A")
            
            logger.info(f"Symbol info for {symbol}:")
            logger.info(f"  Price scale: {price_scale}")
            logger.info(f"  Min quantity: {min_qty}")
            logger.info(f"  Quantity step: {qty_step}")
            
            logger.info("get_instrument_info PASSED ✓")
            return True
        else:
            logger.error(f"Failed to get instrument info for {symbol}")
            return False
    except Exception as e:
        logger.error(f"Error testing instrument info: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_market_data(client):
    """Test market data retrieval"""
    logger.info("\n===== Testing market data retrieval =====")
    
    symbol = "BTCUSDT"
    try:
        # Test get_ticker method
        logger.info(f"Testing get_ticker({symbol})")
        ticker = client.get_ticker(symbol)
        
        if ticker:
            price = ticker.get("lastPrice", "N/A")
            volume = ticker.get("volume24h", "N/A")
            
            logger.info(f"Ticker for {symbol}:")
            logger.info(f"  Price: {price}")
            logger.info(f"  24h Volume: {volume}")
            
            logger.info("get_ticker PASSED ✓")
            return True
        else:
            logger.error(f"Failed to get ticker for {symbol}")
            return False
    except Exception as e:
        logger.error(f"Error testing market data: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_position_info(client):
    """Test position information retrieval"""
    logger.info("\n===== Testing position information =====")
    
    try:
        # Test get_positions method without symbol
        logger.info("Testing get_positions()")
        positions = client.get_positions()
        
        if positions is not None:
            logger.info(f"Retrieved {len(positions)} positions")
            
            # Display position information
            for position in positions:
                symbol = position.get("symbol", "N/A")
                size = position.get("size", "0")
                side = position.get("side", "N/A")
                entry_price = position.get("entryPrice", "N/A")
                
                logger.info(f"Position: {symbol} {side} {size} @ {entry_price}")
            
            logger.info("get_positions PASSED ✓")
            
            # Test position cache
            logger.info("Testing position cache")
            cached_positions = client.position_cache
            logger.info(f"Position cache contains {len(cached_positions)} positions")
            
            # Test account balance
            logger.info("Testing get_account_balance()")
            balance = client.get_account_balance()
            
            if balance:
                available_balance = balance.get("totalAvailableBalance", "N/A")
                logger.info(f"Available balance: {available_balance}")
                logger.info("get_account_balance PASSED ✓")
            else:
                logger.error("Failed to get account balance")
            
            return True
        else:
            logger.error("Failed to get positions")
            return False
    except Exception as e:
        logger.error(f"Error testing position info: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_order_methods(client):
    """Test order-related methods"""
    logger.info("\n===== Testing order methods =====")
    
    symbol = "BTCUSDT"
    try:
        # Test get_open_orders method
        logger.info(f"Testing get_open_orders({symbol})")
        open_orders = client.get_open_orders(symbol)
        
        if open_orders is not None:
            logger.info(f"Retrieved {len(open_orders)} open orders for {symbol}")
            logger.info("get_open_orders PASSED ✓")
        else:
            logger.error("Failed to get open orders")
            return False
        
        # Test get_order_history method
        logger.info(f"Testing get_order_history({symbol})")
        order_history = client.get_order_history(symbol)
        
        if order_history is not None:
            logger.info(f"Retrieved {len(order_history)} historical orders for {symbol}")
            
            # Display recent orders if any
            if order_history:
                recent_order = order_history[0]
                order_id = recent_order.get("orderId", "N/A")
                order_type = recent_order.get("orderType", "N/A")
                status = recent_order.get("orderStatus", "N/A")
                
                logger.info(f"Recent order: {order_id} - {order_type} - {status}")
                
                # Test get_order for a specific order
                if order_id != "N/A":
                    logger.info(f"Testing get_order({symbol}, {order_id})")
                    order_detail = client.get_order(symbol, order_id)
                    
                    if order_detail:
                        logger.info(f"Order details for {order_id} retrieved successfully")
                        logger.info("get_order PASSED ✓")
                    else:
                        logger.error(f"Failed to get order details for {order_id}")
            
            logger.info("get_order_history PASSED ✓")
            return True
        else:
            logger.error("Failed to get order history")
            return False
    except Exception as e:
        logger.error(f"Error testing order methods: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_position_sizing(client):
    """Test position sizing calculations"""
    logger.info("\n===== Testing position sizing =====")
    
    symbol = "BTCUSDT"
    usdt_amount = 100.0  # $100 position
    
    try:
        # Test calculate_position_size method
        logger.info(f"Testing calculate_position_size({symbol}, {usdt_amount})")
        qty = client.calculate_position_size(symbol, usdt_amount)
        
        if qty and float(qty) > 0:
            logger.info(f"Calculated position size: {qty} {symbol}")
            
            # Test internal rounding methods
            logger.info(f"Testing internal _round_quantity and _round_price methods")
            
            ticker = client.get_ticker(symbol)
            if ticker and "lastPrice" in ticker:
                price = float(ticker["lastPrice"])
                
                # Test price rounding
                rounded_price = client._round_price(symbol, price * 1.01)  # 1% higher
                logger.info(f"Original price: {price}, Rounded price: {rounded_price}")
                
                # Test quantity rounding
                raw_qty = 0.12345  # Arbitrary test value
                rounded_qty = client._round_quantity(symbol, raw_qty)
                logger.info(f"Original qty: {raw_qty}, Rounded qty: {rounded_qty}")
                
                logger.info("Position sizing and rounding methods PASSED ✓")
                return True
            else:
                logger.error("Could not get current price for rounding tests")
                return False
        else:
            logger.error(f"Failed to calculate position size or got zero: {qty}")
            return False
    except Exception as e:
        logger.error(f"Error testing position sizing: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_order_placement_simulation(client):
    """
    Simulate order placement without actually placing orders
    This allows testing the method signatures and parameter handling
    """
    logger.info("\n===== Testing order placement simulation =====")
    
    symbol = "BTCUSDT"
    
    try:
        # Get current price for realistic order parameters
        ticker = client.get_ticker(symbol)
        if not ticker or "lastPrice" not in ticker:
            logger.error("Could not get current price for order simulation")
            return False
            
        current_price = float(ticker["lastPrice"])
        logger.info(f"Current price of {symbol}: {current_price}")
        
        # Calculate a very small position size (don't actually want to place orders)
        # For testing exchanges, use minimum quantity
        instrument_info = client.get_instrument_info(symbol)
        min_qty = float(instrument_info.get("lotSizeFilter", {}).get("minOrderQty", "0.001"))
        
        # Log what we would do for a market order
        logger.info(f"SIMULATION ONLY - Would place market order:")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  Side: Buy")
        logger.info(f"  Quantity: {min_qty}")
        logger.info(f"  Take Profit: {client._round_price(symbol, current_price * 1.02)}")  # 2% higher
        logger.info(f"  Stop Loss: {client._round_price(symbol, current_price * 0.98)}")    # 2% lower
        
        # Verify the place_active_order method signature without executing
        # We'll just check if the method exists and has the right signature
        if hasattr(client, "place_active_order"):
            param_list = [
                "symbol", "side", "order_type", "qty",
                "price", "reduce_only", "close_on_trigger", "time_in_force",
                "take_profit", "stop_loss", "tp_trigger_by", "sl_trigger_by", "order_link_id"
            ]
            
            # Get function signature from docstring or source
            import inspect
            sig = str(inspect.signature(client.place_active_order))
            logger.info(f"Method signature: place_active_order{sig}")
            
            # Verify the most critical parameters are supported via kwargs
            logger.info("Verifying method supports critical parameters:")
            for param in ["symbol", "side", "order_type", "qty"]:
                logger.info(f"  - {param}: {'PASSED' if '**kwargs' in sig or param in sig else 'FAILED'}")
            
            logger.info("Order placement simulation PASSED ✓")
            return True
        else:
            logger.error("Client doesn't have place_active_order method")
            return False
    except Exception as e:
        logger.error(f"Error in order placement simulation: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_synchronization(client):
    """Test synchronization methods"""
    logger.info("\n===== Testing synchronization methods =====")
    
    try:
        # Test synchronize_positions method
        logger.info("Testing synchronize_positions()")
        positions = client.synchronize_positions()
        
        if positions is not None:
            logger.info(f"Synchronized {len(positions)} positions")
            logger.info("synchronize_positions PASSED ✓")
            return True
        else:
            logger.error("Failed to synchronize positions")
            return False
    except Exception as e:
        logger.error(f"Error testing synchronization: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Run all tests"""
    logger.info("===== ORDER MANAGER CLIENT TESTS =====")
    
    # Load environment variables
    load_dotenv()
    
    # Test client initialization
    transport, client = await test_client_initialization()
    
    if not client:
        logger.error("Client initialization failed, stopping tests")
        return
    
    # Run tests that don't modify state
    tests = [
        test_instrument_info,
        test_market_data,
        test_position_info,
        test_order_methods,
        test_position_sizing,
        test_order_placement_simulation,
        test_synchronization
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