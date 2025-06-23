"""
Test script for OrderManagerClient

This script focuses on methodically testing each functionality of the OrderManagerClient,
including market data retrieval, order placement (simulated), position management,
and instrument information.
"""

import os
import sys
import asyncio
import time
from decimal import Decimal
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.core.client import BybitClientTransport
from pybit_bot.core.order_manager_client import OrderManagerClient
from pybit_bot.utils.credentials import load_credentials
from pybit_bot.utils.logger import Logger

# Create a logger for the tests
logger = Logger("TestOrderClient")

class OrderClientTester:
    """Test class for OrderManagerClient"""
    
    def __init__(self):
        """Initialize the tester"""
        self.client = None
        self.symbol = "BTCUSDT"  # Default test symbol
        self.results = []
    
    async def setup(self):
        """Set up the test environment"""
        logger.info("=== Setting up test environment ===")
        
        # Load credentials
        credentials = load_credentials()
        logger.info(f"Loaded credentials (testnet: {credentials.testnet})")
        
        # Create transport client
        transport = BybitClientTransport(credentials)
        logger.info("Created transport client")
        
        # Create order manager client
        self.client = OrderManagerClient(transport, logger=logger)
        logger.info("Created OrderManagerClient")
        
        # Check if client is initialized properly
        if not hasattr(self.client, "transport") or not self.client.transport:
            logger.error("Client transport not properly initialized")
            return False
            
        return True
    
    async def run_all_tests(self):
        """Run all tests"""
        setup_success = await self.setup()
        if not setup_success:
            logger.error("Setup failed, aborting tests")
            return False
        
        # Define tests
        tests = [
            self.test_instrument_info,
            self.test_positions,
            self.test_market_ticker,
            self.test_open_orders,
            self.test_order_history,
            self.test_account_balance,
            self.test_position_sizing,
            self.test_price_rounding,
            self.test_quantity_rounding,
            self.test_order_methods_signatures
        ]
        
        # Run each test
        for test_func in tests:
            test_name = test_func.__name__
            logger.info(f"\n=== Running test: {test_name} ===")
            
            try:
                result = await test_func()
                passed = "PASSED ✓" if result else "FAILED ✗"
                logger.info(f"Test {test_name}: {passed}")
                self.results.append((test_name, result))
            except Exception as e:
                logger.error(f"Test {test_name} raised exception: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                self.results.append((test_name, False))
        
        # Print summary
        await self.print_summary()
        
        return True
    
    async def print_summary(self):
        """Print test results summary"""
        logger.info("\n=== TEST RESULTS SUMMARY ===")
        passed = sum(1 for _, result in self.results if result)
        failed = len(self.results) - passed
        
        for name, result in self.results:
            status = "PASSED ✓" if result else "FAILED ✗"
            logger.info(f"{name}: {status}")
        
        logger.info(f"\nTotal: {len(self.results)}, Passed: {passed}, Failed: {failed}")
    
    async def test_instrument_info(self):
        """Test instrument info methods"""
        logger.info("Testing get_instruments_info() and get_instrument_info()")
        
        # Test get_instruments_info
        instruments = self.client.get_instruments_info()
        if not instruments or "list" not in instruments:
            logger.error("Failed to get instruments info")
            return False
            
        instrument_count = len(instruments["list"])
        logger.info(f"Retrieved {instrument_count} instruments")
        
        # Test get_instrument_info for specific symbol
        symbol_info = self.client.get_instrument_info(self.symbol)
        
        if not symbol_info:
            logger.error(f"Failed to get instrument info for {self.symbol}")
            return False
            
        # Print key instrument info
        logger.info(f"Instrument info for {self.symbol}:")
        lot_size_filter = symbol_info.get("lotSizeFilter", {})
        price_filter = symbol_info.get("priceFilter", {})
        
        logger.info(f"  Min Order Qty: {lot_size_filter.get('minOrderQty', 'N/A')}")
        logger.info(f"  Qty Step: {lot_size_filter.get('qtyStep', 'N/A')}")
        logger.info(f"  Tick Size: {price_filter.get('tickSize', 'N/A')}")
        
        return True
    
    async def test_positions(self):
        """Test position retrieval methods"""
        logger.info("Testing get_positions()")
        
        # Test getting all positions
        positions = self.client.get_positions()
        if positions is None:
            logger.error("get_positions() returned None")
            return False
            
        logger.info(f"Retrieved {len(positions)} positions")
        
        # Test position cache
        logger.info("Testing position cache")
        cached_positions = self.client.position_cache
        logger.info(f"Position cache contains {len(cached_positions)} positions")
        
        # Test for specific symbol
        symbol_positions = self.client.get_positions(self.symbol)
        logger.info(f"Retrieved {len(symbol_positions)} positions for {self.symbol}")
        
        return True
    
    async def test_market_ticker(self):
        """Test market ticker retrieval"""
        logger.info(f"Testing get_ticker({self.symbol})")
        
        # Get ticker data
        ticker = self.client.get_ticker(self.symbol)
        
        if not ticker:
            logger.error(f"Failed to get ticker for {self.symbol}")
            return False
            
        # Print key ticker info
        price = ticker.get("lastPrice", "N/A")
        bid = ticker.get("bidPrice", "N/A")
        ask = ticker.get("askPrice", "N/A")
        volume = ticker.get("volume24h", "N/A")
        
        logger.info(f"Ticker for {self.symbol}:")
        logger.info(f"  Last Price: {price}")
        logger.info(f"  Bid/Ask: {bid}/{ask}")
        logger.info(f"  24h Volume: {volume}")
        
        return True
    
    async def test_open_orders(self):
        """Test open orders retrieval"""
        logger.info("Testing get_open_orders()")
        
        # Get all open orders
        open_orders = self.client.get_open_orders()
        if open_orders is None:
            logger.error("get_open_orders() returned None")
            return False
            
        logger.info(f"Retrieved {len(open_orders)} open orders")
        
        # Test for specific symbol
        symbol_orders = self.client.get_open_orders(self.symbol)
        logger.info(f"Retrieved {len(symbol_orders)} open orders for {self.symbol}")
        
        # Print order details if any exist
        if symbol_orders:
            order = symbol_orders[0]
            order_id = order.get("orderId", "N/A")
            side = order.get("side", "N/A")
            price = order.get("price", "N/A")
            qty = order.get("qty", "N/A")
            
            logger.info(f"Order details: {order_id} - {side} {qty} @ {price}")
        
        return True
    
    async def test_order_history(self):
        """Test order history retrieval"""
        logger.info("Testing get_order_history()")
        
        # Get order history
        history = self.client.get_order_history(self.symbol)
        if history is None:
            logger.error("get_order_history() returned None")
            return False
            
        logger.info(f"Retrieved {len(history)} historical orders for {self.symbol}")
        
        # Print recent order details if any exist
        if history:
            # Sort by creation time if available
            if "createdTime" in history[0]:
                sorted_history = sorted(
                    history, 
                    key=lambda x: int(x.get("createdTime", 0)), 
                    reverse=True
                )
                recent = sorted_history[0]
            else:
                recent = history[0]
                
            order_id = recent.get("orderId", "N/A")
            status = recent.get("orderStatus", "N/A")
            side = recent.get("side", "N/A")
            price = recent.get("price", "N/A")
            
            logger.info(f"Recent order: {order_id} - {side} @ {price} - {status}")
            
            # Test get_order method with this order ID
            if order_id != "N/A":
                logger.info(f"Testing get_order({self.symbol}, {order_id})")
                order_details = self.client.get_order(self.symbol, order_id)
                
                if order_details and "status" not in order_details:
                    logger.info(f"Successfully retrieved details for order {order_id}")
                else:
                    logger.warning(f"Order details incomplete: {order_details}")
        
        return True
    
    async def test_account_balance(self):
        """Test account balance retrieval"""
        logger.info("Testing get_account_balance()")
        
        # Get account balance
        balance = self.client.get_account_balance()
        if balance is None:
            logger.error("get_account_balance() returned None")
            return False
            
        # Print balance details
        total = balance.get("totalBalance", "N/A")
        available = balance.get("totalAvailableBalance", "N/A")
        
        logger.info(f"Account Balance:")
        logger.info(f"  Total: {total} USDT")
        logger.info(f"  Available: {available} USDT")
        
        return True
    
    async def test_position_sizing(self):
        """Test position sizing calculation"""
        logger.info("Testing calculate_position_size()")
        
        # Get current price
        ticker = self.client.get_ticker(self.symbol)
        if not ticker or "lastPrice" not in ticker:
            logger.error(f"Failed to get current price for {self.symbol}")
            return False
            
        current_price = float(ticker["lastPrice"])
        
        # Test different USD amounts
        test_amounts = [10.0, 100.0, 1000.0]
        
        for amount in test_amounts:
            qty = self.client.calculate_position_size(self.symbol, amount, current_price)
            expected_raw = amount / current_price
            
            logger.info(f"Position size for ${amount} at price {current_price}:")
            logger.info(f"  Raw quantity: ~{expected_raw:.8f}")
            logger.info(f"  Rounded quantity: {qty}")
            
            # Verify result is not zero and is a string
            if not qty or qty == "0" or not isinstance(qty, str):
                logger.error(f"Invalid position size result: {qty}")
                return False
        
        return True
    
    async def test_price_rounding(self):
        """Test price rounding functionality"""
        logger.info("Testing _round_price()")
        
        # Get current price
        ticker = self.client.get_ticker(self.symbol)
        if not ticker or "lastPrice" not in ticker:
            logger.error(f"Failed to get current price for {self.symbol}")
            return False
            
        current_price = float(ticker["lastPrice"])
        
        # Test different price variations
        test_variations = [
            current_price * 0.95,  # 5% lower
            current_price,         # Current price
            current_price * 1.05   # 5% higher
        ]
        
        for test_price in test_variations:
            rounded = self.client._round_price(self.symbol, test_price)
            
            logger.info(f"Price rounding for {test_price}:")
            logger.info(f"  Rounded result: {rounded}")
            
            # Verify result is not empty and is a string
            if not rounded or not isinstance(rounded, str):
                logger.error(f"Invalid price rounding result: {rounded}")
                return False
                
            # Verify it's a valid decimal number
            try:
                decimal_val = Decimal(rounded)
                if decimal_val <= 0:
                    logger.error(f"Rounded price <= 0: {rounded}")
                    return False
            except:
                logger.error(f"Rounded price is not a valid decimal: {rounded}")
                return False
        
        return True
    
    async def test_quantity_rounding(self):
        """Test quantity rounding functionality"""
        logger.info("Testing _round_quantity()")
        
        # Test different quantities
        test_quantities = [0.001, 0.12345, 1.0, 10.5]
        
        for qty in test_quantities:
            rounded = self.client._round_quantity(self.symbol, qty)
            
            logger.info(f"Quantity rounding for {qty}:")
            logger.info(f"  Rounded result: {rounded}")
            
            # Verify result is not empty and is a string
            if not rounded or not isinstance(rounded, str):
                logger.error(f"Invalid quantity rounding result: {rounded}")
                return False
                
            # Verify it's a valid decimal number
            try:
                decimal_val = Decimal(rounded)
                if decimal_val <= 0:
                    logger.error(f"Rounded quantity <= 0: {rounded}")
                    return False
            except:
                logger.error(f"Rounded quantity is not a valid decimal: {rounded}")
                return False
        
        return True
    
    async def test_order_methods_signatures(self):
        """Test order method signatures without placing actual orders"""
        logger.info("Testing order method signatures")
        
        # Verify place_active_order method exists
        if not hasattr(self.client, "place_active_order"):
            logger.error("Method place_active_order does not exist")
            return False
            
        # Check method signatures
        methods_to_check = [
            "place_active_order",
            "amend_order",
            "enter_position_market",
            "set_trading_stop",
            "cancel_order",
            "cancel_all_orders",
            "close_position"
        ]
        
        all_methods_valid = True
        
        for method_name in methods_to_check:
            if not hasattr(self.client, method_name):
                logger.error(f"Method {method_name} does not exist")
                all_methods_valid = False
                continue
                
            method = getattr(self.client, method_name)
            if not callable(method):
                logger.error(f"{method_name} is not callable")
                all_methods_valid = False
                continue
                
            logger.info(f"Method {method_name} exists and is callable")
            
            # Check docstring to ensure it's documented
            doc = method.__doc__
            if not doc:
                logger.warning(f"Method {method_name} has no documentation")
        
        return all_methods_valid

async def main():
    """Main entry point"""
    logger.info("=== ORDER MANAGER CLIENT TESTS ===")
    
    # Load environment variables
    load_dotenv()
    
    # Create and run tester
    tester = OrderClientTester()
    await tester.run_all_tests()
    
    logger.info("=== ALL TESTS COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())