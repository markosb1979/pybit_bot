#!/usr/bin/env python3
"""
OrderManager Dollar Input Test Suite
Tests OrderManager with various dollar input values
Ensures correct behavior across monetary ranges
"""

import asyncio
import os
import sys
import time
from datetime import datetime
import json
from pathlib import Path
import traceback

# Add the parent directory to Python path
current_dir = Path(__file__).parent
project_root = current_dir.parent if current_dir.name == "pybit_bot" else current_dir
sys.path.insert(0, str(project_root))

# Try to import dotenv for better .env handling
try:
    from dotenv import load_dotenv
    have_dotenv = True
except ImportError:
    have_dotenv = False

# Import our modules
try:
    from pybit_bot import BybitClient, APICredentials, Logger, ConfigLoader
    from pybit_bot.managers.order_manager import OrderManager
    from pybit_bot.managers.data_manager import DataManager
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print("Please ensure you're running from the correct directory")
    sys.exit(1)

def load_env_file():
    """Load environment variables from .env file"""
    # Try different possible locations for the .env file
    possible_locations = [
        Path('.env'),                      # Current directory
        Path(project_root) / '.env',       # Project root
        Path.home() / '.env',              # User's home directory
        Path('/etc/pybit_bot/.env')        # System config directory
    ]
    
    env_file = None
    for loc in possible_locations:
        if loc.exists():
            print(f"Found .env file at: {loc}")
            env_file = loc
            break
    
    if not env_file:
        print("ERROR: No .env file found. Please create one with your API credentials.")
        return False
    
    # Load the .env file
    if have_dotenv:
        load_dotenv(env_file)
        print(f"Loaded .env file using python-dotenv: {env_file}")
    else:
        # Manual loading as fallback
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#') and line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip('"\'')
            print(f"Loaded .env file manually: {env_file}")
        except Exception as e:
            print(f"ERROR: Failed to load .env file: {e}")
            return False
    
    return True

class OrderManagerDollarTester:
    """Test OrderManager with various dollar input values"""
    
    def __init__(self, symbol="BTCUSDT"):
        self.logger = Logger("DollarTest")
        self.config_loader = ConfigLoader()
        self.client = None
        self.data_manager = None
        self.order_manager = None
        self.symbol = symbol
        self.test_results = {}
        
    async def initialize(self):
        """Initialize the test environment"""
        try:
            self.logger.info(f"Initializing Dollar Input Test for {self.symbol}")
            
            # Load credentials from environment
            api_key = os.getenv('BYBIT_API_KEY')
            api_secret = os.getenv('BYBIT_API_SECRET')
            testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
            
            if not api_key or not api_secret:
                self.logger.error("API credentials not found in environment")
                raise ValueError("Missing API credentials")
            
            self.logger.info(f"Using API key: {api_key[:5]}...{api_key[-5:]} (testnet={testnet})")
            
            credentials = APICredentials(
                api_key=api_key, 
                api_secret=api_secret,
                testnet=testnet
            )
            
            # Initialize client
            self.client = BybitClient(credentials, self.logger)
            
            # Initialize data manager
            self.data_manager = DataManager(
                client=self.client,
                config=self.config_loader,
                logger=self.logger
            )
            
            # Initialize data manager first
            data_init_result = await self.data_manager.initialize()
            if not data_init_result:
                self.logger.error("Failed to initialize DataManager")
                return False
            
            # Initialize order manager
            self.order_manager = OrderManager(
                client=self.client,
                config=self.config_loader,
                logger=self.logger
            )
            
            # Initialize order manager
            order_init_result = await self.order_manager.initialize()
            if not order_init_result:
                self.logger.error("Failed to initialize OrderManager")
                return False
            
            self.logger.info("Test environment initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            traceback.print_exc()
            return False
            
    async def shutdown(self):
        """Properly clean up resources"""
        self.logger.info("Shutting down test environment...")
        
        # First, close order manager if it exists
        if self.order_manager:
            try:
                await self.order_manager.close()
                self.logger.info("OrderManager closed")
            except Exception as e:
                self.logger.error(f"Error closing OrderManager: {e}")
        
        # Then close data manager
        if self.data_manager:
            try:
                await self.data_manager.close()
                self.logger.info("DataManager closed")
            except Exception as e:
                self.logger.error(f"Error closing DataManager: {e}")
        
        self.logger.info("Shutdown complete")
    
    async def test_position_sizing(self, dollar_amounts):
        """Test position sizing with various dollar amounts"""
        self.logger.info(f"Testing position sizing with dollar amounts: {dollar_amounts}")
        
        results = {}
        
        try:
            # Get current price
            current_price = await self.data_manager.get_latest_price(self.symbol)
            
            if current_price <= 0:
                self.logger.error("Invalid price data")
                return False
            
            self.logger.info(f"Current {self.symbol} price: {current_price}")
            
            # Table header
            self.logger.info("\nPosition Sizing Results:")
            self.logger.info("-" * 80)
            self.logger.info(f"{'USDT Amount':<15} {'BTC Quantity':<20} {'Actual USD Value':<20} {'Difference':<15}")
            self.logger.info("-" * 80)
            
            for amount in dollar_amounts:
                # Calculate position size
                position_size = await self.order_manager.calculate_position_size(
                    symbol=self.symbol,
                    usdt_amount=amount
                )
                
                # Calculate actual USDT value
                actual_usdt = float(position_size) * current_price
                
                # Calculate difference
                difference = actual_usdt - amount
                diff_percent = (difference / amount) * 100 if amount > 0 else 0
                
                self.logger.info(f"${amount:<14,.2f} {position_size:<20} ${actual_usdt:<19,.2f} ${difference:+.2f} ({diff_percent:+.2f}%)")
                
                results[str(amount)] = {
                    "position_size": position_size,
                    "actual_usdt": actual_usdt,
                    "difference": difference,
                    "diff_percent": diff_percent,
                    "valid": abs(diff_percent) < 2.0  # Consider valid if within 2%
                }
            
            self.logger.info("-" * 80)
            
            # Check for any invalid results
            invalid_results = [amt for amt, res in results.items() if not res["valid"]]
            if invalid_results:
                self.logger.warning(f"Some position sizes exceed acceptable difference: {invalid_results}")
                return {"success": False, "results": results}
            else:
                self.logger.info("All position sizes within acceptable range")
                return {"success": True, "results": results}
            
        except Exception as e:
            self.logger.error(f"Position sizing test failed: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_market_orders(self, dollar_amounts):
        """Test market orders with various dollar amounts"""
        self.logger.info(f"Testing market orders with dollar amounts: {dollar_amounts}")
        
        results = {}
        
        try:
            # Get account balance to check we're not exceeding it
            account = await self.order_manager.get_account_balance()
            available_balance = float(account.get("totalAvailableBalance", 0))
            
            self.logger.info(f"Account balance: {available_balance} USDT")
            
            # Table header
            self.logger.info("\nMarket Order Results:")
            self.logger.info("-" * 120)
            self.logger.info(f"{'USDT Amount':<15} {'BTC Quantity':<15} {'Order Type':<10} {'Order ID':<25} {'Status':<15} {'Filled Price':<15}")
            self.logger.info("-" * 120)
            
            # Test a buy and sell for each amount
            for amount in dollar_amounts:
                # Skip if amount exceeds available balance
                if amount > available_balance * 0.9:  # 90% of available balance as safety
                    self.logger.warning(f"Skipping ${amount} test: exceeds 90% of available balance")
                    results[str(amount)] = {"skipped": True, "reason": "Exceeds balance"}
                    continue
                
                # Calculate position size
                position_size = await self.order_manager.calculate_position_size(
                    symbol=self.symbol,
                    usdt_amount=amount
                )
                
                # Test buy order
                buy_result = await self.order_manager.place_market_order(
                    symbol=self.symbol,
                    side="Buy",
                    qty=position_size
                )
                
                if "error" in buy_result or not buy_result.get("orderId"):
                    self.logger.error(f"Failed to place buy order for ${amount}: {buy_result}")
                    results[f"{amount}_buy"] = {"success": False, "error": str(buy_result)}
                    continue
                
                buy_order_id = buy_result.get("orderId")
                
                # Wait for order to execute
                await asyncio.sleep(3)
                
                # Check order status
                buy_status = await self.order_manager.get_order_status(self.symbol, buy_order_id)
                
                self.logger.info(f"${amount:<14,.2f} {position_size:<15} {'Buy':<10} {buy_order_id:<25} {buy_status:<15} {'N/A':<15}")
                
                results[f"{amount}_buy"] = {
                    "order_id": buy_order_id,
                    "qty": position_size,
                    "status": buy_status,
                    "success": buy_status in ["Filled", "PartiallyFilled"]
                }
                
                # Wait a moment before selling
                await asyncio.sleep(1)
                
                # Test sell order
                sell_result = await self.order_manager.place_market_order(
                    symbol=self.symbol,
                    side="Sell",
                    qty=position_size
                )
                
                if "error" in sell_result or not sell_result.get("orderId"):
                    self.logger.error(f"Failed to place sell order for ${amount}: {sell_result}")
                    results[f"{amount}_sell"] = {"success": False, "error": str(sell_result)}
                    continue
                
                sell_order_id = sell_result.get("orderId")
                
                # Wait for order to execute
                await asyncio.sleep(3)
                
                # Check order status
                sell_status = await self.order_manager.get_order_status(self.symbol, sell_order_id)
                
                self.logger.info(f"${amount:<14,.2f} {position_size:<15} {'Sell':<10} {sell_order_id:<25} {sell_status:<15} {'N/A':<15}")
                
                results[f"{amount}_sell"] = {
                    "order_id": sell_order_id,
                    "qty": position_size,
                    "status": sell_status,
                    "success": sell_status in ["Filled", "PartiallyFilled"]
                }
                
                # Wait a moment before next test
                await asyncio.sleep(2)
            
            self.logger.info("-" * 120)
            
            # Check for any failed orders
            failed_orders = [(k, v) for k, v in results.items() if not v.get("skipped") and not v.get("success")]
            if failed_orders:
                self.logger.warning(f"Some orders failed: {[k for k, v in failed_orders]}")
                return {"success": False, "results": results}
            else:
                self.logger.info("All orders completed successfully")
                return {"success": True, "results": results}
            
        except Exception as e:
            self.logger.error(f"Market order test failed: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_limit_orders(self, dollar_amounts):
        """Test limit orders with various dollar amounts"""
        self.logger.info(f"Testing limit orders with dollar amounts: {dollar_amounts}")
        
        results = {}
        
        try:
            # Get current price
            current_price = await self.data_manager.get_latest_price(self.symbol)
            
            if current_price <= 0:
                self.logger.error("Invalid price data")
                return {"success": False, "error": "Invalid price data"}
            
            # Table header
            self.logger.info("\nLimit Order Results:")
            self.logger.info("-" * 130)
            self.logger.info(f"{'USDT Amount':<15} {'BTC Quantity':<15} {'Order Type':<10} {'Price':<15} {'Order ID':<25} {'Status':<15}")
            self.logger.info("-" * 130)
            
            for amount in dollar_amounts:
                # Calculate position size
                position_size = await self.order_manager.calculate_position_size(
                    symbol=self.symbol,
                    usdt_amount=amount
                )
                
                # Set limit prices significantly away from market to avoid immediate fills
                buy_price = str(round(current_price * 0.95, 2))  # 5% below market
                sell_price = str(round(current_price * 1.05, 2))  # 5% above market
                
                # Test buy limit order
                buy_result = await self.order_manager.place_limit_order(
                    symbol=self.symbol,
                    side="Buy",
                    qty=position_size,
                    price=buy_price
                )
                
                if "error" in buy_result or not buy_result.get("orderId"):
                    self.logger.error(f"Failed to place buy limit order for ${amount}: {buy_result}")
                    results[f"{amount}_buy_limit"] = {"success": False, "error": str(buy_result)}
                    continue
                
                buy_order_id = buy_result.get("orderId")
                
                # Wait a moment
                await asyncio.sleep(2)
                
                # Check order status
                buy_status = await self.order_manager.get_order_status(self.symbol, buy_order_id)
                
                self.logger.info(f"${amount:<14,.2f} {position_size:<15} {'Buy Limit':<10} {buy_price:<15} {buy_order_id:<25} {buy_status:<15}")
                
                results[f"{amount}_buy_limit"] = {
                    "order_id": buy_order_id,
                    "qty": position_size,
                    "price": buy_price,
                    "status": buy_status,
                    "success": buy_status in ["New", "PartiallyFilled", "Filled"]
                }
                
                # Test sell limit order
                sell_result = await self.order_manager.place_limit_order(
                    symbol=self.symbol,
                    side="Sell",
                    qty=position_size,
                    price=sell_price
                )
                
                if "error" in sell_result or not sell_result.get("orderId"):
                    self.logger.error(f"Failed to place sell limit order for ${amount}: {sell_result}")
                    results[f"{amount}_sell_limit"] = {"success": False, "error": str(sell_result)}
                    continue
                
                sell_order_id = sell_result.get("orderId")
                
                # Wait a moment
                await asyncio.sleep(2)
                
                # Check order status
                sell_status = await self.order_manager.get_order_status(self.symbol, sell_order_id)
                
                self.logger.info(f"${amount:<14,.2f} {position_size:<15} {'Sell Limit':<10} {sell_price:<15} {sell_order_id:<25} {sell_status:<15}")
                
                results[f"{amount}_sell_limit"] = {
                    "order_id": sell_order_id,
                    "qty": position_size,
                    "price": sell_price,
                    "status": sell_status,
                    "success": sell_status in ["New", "PartiallyFilled", "Filled"]
                }
                
                # Cancel the orders after testing to clean up
                await self.order_manager.cancel_order(self.symbol, buy_order_id)
                await self.order_manager.cancel_order(self.symbol, sell_order_id)
                
                # Wait a moment before next test
                await asyncio.sleep(2)
            
            self.logger.info("-" * 130)
            
            # Check for any failed orders
            failed_orders = [(k, v) for k, v in results.items() if not v.get("success")]
            if failed_orders:
                self.logger.warning(f"Some limit orders failed: {[k for k, v in failed_orders]}")
                return {"success": False, "results": results}
            else:
                self.logger.info("All limit orders completed successfully")
                return {"success": True, "results": results}
            
        except Exception as e:
            self.logger.error(f"Limit order test failed: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    async def run_all_tests(self, dollar_amounts=None):
        """Run all dollar input tests"""
        if dollar_amounts is None:
            # Default test amounts - a range of values
            dollar_amounts = [5, 10, 50, 100, 250, 500, 1000]
        
        self.logger.info("=" * 60)
        self.logger.info("STARTING ORDER MANAGER DOLLAR INPUT TESTING")
        self.logger.info(f"Test Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        self.logger.info(f"Test Amounts: {dollar_amounts}")
        self.logger.info("=" * 60)
        
        # Test sequence
        test_sequence = [
            ("Position Sizing", self.test_position_sizing),
            ("Market Orders", self.test_market_orders),
            ("Limit Orders", self.test_limit_orders),
        ]
        
        for test_name, test_func in test_sequence:
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"TESTING: {test_name}")
            self.logger.info(f"{'='*50}")
            
            try:
                result = await test_func(dollar_amounts)
                self.test_results[test_name] = {
                    "status": "PASS" if result.get("success", False) else "FAIL",
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": result
                }
                
                status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
                self.logger.info(f"Result: {status}")
                
            except Exception as e:
                self.test_results[test_name] = {
                    "status": "ERROR",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
                self.logger.error(f"Result: ❌ ERROR - {str(e)}")
                traceback.print_exc()
            
            # Small delay between tests
            await asyncio.sleep(2)
        
        # Generate test report
        self.generate_test_report()
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("DOLLAR INPUT TEST REPORT")
        self.logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results.values() if r["status"] == "PASS")
        failed_tests = sum(1 for r in self.test_results.values() if r["status"] == "FAIL")
        error_tests = sum(1 for r in self.test_results.values() if r["status"] == "ERROR")
        
        self.logger.info(f"Total Tests: {total_tests}")
        self.logger.info(f"Passed: {passed_tests} ✅")
        self.logger.info(f"Failed: {failed_tests} ❌")
        self.logger.info(f"Errors: {error_tests} ⚠️")
        
        if total_tests > 0:
            success_rate = (passed_tests/total_tests)*100
            self.logger.info(f"Success Rate: {success_rate:.1f}%")
        
        self.logger.info("\nDetailed Results:")
        self.logger.info("-" * 60)
        
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
            self.logger.info(f"{status_icon} {test_name}: {result['status']}")
            
            if result["status"] != "PASS":
                if "error" in result:
                    self.logger.info(f"    Error: {result.get('error', 'Unknown error')}")
                elif "details" in result and "error" in result["details"]:
                    self.logger.info(f"    Error: {result['details'].get('error', 'Unknown error')}")
        
        # Save detailed report to file
        report_file = f"dollar_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, indent=2, default=str)
            self.logger.info(f"\nDetailed report saved to: {report_file}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")
        
        # Final verdict
        if passed_tests == total_tests:
            self.logger.info(f"\n🎉 ALL TESTS PASSED! OrderManager handles all dollar inputs correctly.")
        elif passed_tests / total_tests >= 0.8:
            self.logger.info(f"\n⚠️ Most tests passed. OrderManager handles most dollar inputs correctly.")
        else:
            self.logger.info(f"\n❌ Multiple test failures. OrderManager has issues with dollar input handling.")

async def main():
    """Main function to run the tests"""
    print("OrderManager Dollar Input Test Suite")
    print("=" * 50)
    
    # Load environment variables
    if not load_env_file():
        print("Failed to load environment variables. Cannot proceed with tests.")
        sys.exit(1)
    
    # Get dollar amounts from command line arguments
    dollar_amounts = None
    if len(sys.argv) > 1:
        try:
            dollar_amounts = [float(arg) for arg in sys.argv[1:]]
            print(f"Using custom dollar amounts: {dollar_amounts}")
        except ValueError:
            print("Invalid dollar amounts provided. Must be numerical values.")
            print("Example usage: python order_manager_dollar_test.py 250 500 1000")
            sys.exit(1)
    
    tester = OrderManagerDollarTester()
    
    try:
        if await tester.initialize():
            print("Initialization successful!")
            
            # Run the tests with specified or default amounts
            await tester.run_all_tests(dollar_amounts)
        else:
            print("Initialization failed, cannot proceed with tests")
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test suite failed: {str(e)}")
        traceback.print_exc()
    finally:
        # Proper cleanup
        await tester.shutdown()
        print("Test environment shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())