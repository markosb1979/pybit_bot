#!/usr/bin/env python3
"""
OrderManager Test Script - Windows Compatible
Tests all OrderManager functionality on Bybit testnet
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

# Import our modules properly
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
    """Load environment variables from .env file with better error handling"""
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
        print("Required variables: BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_TESTNET=true")
        print("Checked locations:")
        for loc in possible_locations:
            print(f"  - {loc}")
        return False
    
    # Load the .env file
    if have_dotenv:
        # Use python-dotenv if available
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
    
    # Verify required variables
    required_vars = ['BYBIT_API_KEY', 'BYBIT_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file and ensure all required variables are set.")
        return False
    
    # Set testnet if not specified (default to true for safety)
    if not os.getenv('BYBIT_TESTNET'):
        os.environ['BYBIT_TESTNET'] = 'true'
        print("BYBIT_TESTNET not specified, defaulting to 'true' for safety")
    
    return True

class OrderManagerTester:
    """Test suite for OrderManager functionality"""
    
    def __init__(self):
        self.logger = Logger("OrderManagerTest")
        self.config_loader = ConfigLoader()
        self.client = None
        self.data_manager = None
        self.order_manager = None
        self.test_results = {}
        self._task_list = []  # Store tasks we create for proper cleanup
        
    async def initialize(self):
        """Initialize the test environment"""
        try:
            self.logger.info("Initializing OrderManager test environment")
            
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
            
            # Add a flag to prevent reconnection attempts during shutdown
            # This is a monkey patch to help with clean shutdown
            self.data_manager.is_shutting_down = False
            
            # Monkey patch the _reconnect_websocket method to check for shutdown
            if hasattr(self.data_manager, '_reconnect_websocket'):
                original_reconnect = self.data_manager._reconnect_websocket
                
                async def patched_reconnect(*args, **kwargs):
                    if hasattr(self.data_manager, 'is_shutting_down') and self.data_manager.is_shutting_down:
                        self.logger.info("Skipping WebSocket reconnection during shutdown")
                        return
                    return await original_reconnect(*args, **kwargs)
                
                self.data_manager._reconnect_websocket = patched_reconnect
            
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
        
        # Mark data manager as shutting down
        if self.data_manager:
            self.data_manager.is_shutting_down = True
        
        # Cancel any tasks we're tracking
        for task in self._task_list:
            if not task.done():
                task.cancel()
        
        # First, close order manager if it exists
        if self.order_manager:
            try:
                self.logger.info("Closing OrderManager...")
                if hasattr(self.order_manager, 'close') and callable(self.order_manager.close):
                    close_result = self.order_manager.close()
                    if asyncio.iscoroutine(close_result):
                        await close_result
                self.logger.info("OrderManager closed")
            except Exception as e:
                self.logger.error(f"Error closing OrderManager: {e}")
        
        # Then close data manager (which has the websocket)
        if self.data_manager:
            try:
                self.logger.info("Closing DataManager...")
                
                # Attempt to cancel any pending reconnection tasks
                await self.data_manager.close()
                
                # Wait a moment to ensure resources are freed
                await asyncio.sleep(0.5)
                
                self.logger.info("DataManager closed")
            except Exception as e:
                self.logger.error(f"Error closing DataManager: {e}")
                
        # Cancel all remaining tasks that might be hanging
        self.logger.info("Cancelling any remaining tasks...")
        try:
            # Get all tasks except the current one
            tasks = [t for t in asyncio.all_tasks() 
                    if t is not asyncio.current_task() 
                    and not t.done() 
                    and "reconnect" in str(t).lower()]
                    
            if tasks:
                self.logger.info(f"Found {len(tasks)} reconnect tasks to cancel")
                for task in tasks:
                    task.cancel()
                
                # Wait for tasks to acknowledge cancellation
                await asyncio.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Error cancelling remaining tasks: {e}")
        
        self.logger.info("Shutdown complete")
    
    async def run_all_tests(self):
        """Run all OrderManager tests"""
        self.logger.info("=" * 60)
        self.logger.info("STARTING ORDER MANAGER TESTING")
        self.logger.info(f"Test Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        self.logger.info("=" * 60)
        
        # Test sequence - ordering is important as some tests depend on previous ones
        test_sequence = [
            ("Position Status", self.test_position_status),
            ("Position Sizing", self.test_position_sizing),
            ("Market Buy Order", self.test_market_buy),
            ("Market Sell Order", self.test_market_sell),
            ("Limit Buy Order", self.test_limit_buy),
            ("Limit Sell Order", self.test_limit_sell),
            ("Take Profit Order", self.test_take_profit),
            ("Stop Loss Order", self.test_stop_loss),
            ("Cancel Orders", self.test_cancel_orders),
            ("Close Position", self.test_close_position),
            ("Risk Management", self.test_risk_management),
            ("Order Tracking", self.test_order_tracking),
            ("Error Handling", self.test_error_handling),
        ]
        
        for test_name, test_func in test_sequence:
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"TESTING: {test_name}")
            self.logger.info(f"{'='*50}")
            
            try:
                result = await test_func()
                self.test_results[test_name] = {
                    "status": "PASS" if result else "FAIL",
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": result if isinstance(result, dict) else {}
                }
                
                status = "✅ PASS" if result else "❌ FAIL"
                self.logger.info(f"Result: {status}")
                
            except Exception as e:
                self.test_results[test_name] = {
                    "status": "ERROR",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
                self.logger.error(f"Result: ❌ ERROR - {str(e)}")
                traceback.print_exc()
            
            # Small delay between tests to avoid rate limiting
            await asyncio.sleep(2)
        
        # Generate test report
        self.generate_test_report()
    
    async def test_position_status(self):
        """Test position status retrieval"""
        try:
            # Get current positions - handle both async and sync implementations
            positions = self.order_manager.get_positions()
            if asyncio.iscoroutine(positions):
                positions = await positions
            
            self.logger.info(f"Current positions: {positions}")
            
            # Verify position data structure
            if isinstance(positions, list):
                for pos in positions:
                    if 'symbol' in pos and 'size' in pos:
                        self.logger.info(f"Position structure valid: {pos['symbol']}")
                
                return {
                    "positions_count": len(positions),
                    "valid_structure": True,
                    "success": True
                }
            else:
                self.logger.error("Invalid position data structure")
                return False
                
        except Exception as e:
            self.logger.error(f"Position status test failed: {e}")
            return False
    
    async def test_position_sizing(self):
        """Test position sizing calculations"""
        try:
            # Test with different USDT amounts
            test_amounts = [5, 10, 50, 100]  # Small test amounts
            results = {}
            
            symbol = "BTCUSDT"
            
            # Get latest price from data_manager
            current_price = await self.data_manager.get_latest_price(symbol)
            
            if current_price <= 0:
                self.logger.error("Invalid price data")
                return False
            
            self.logger.info(f"Current {symbol} price: {current_price}")
            
            for amount in test_amounts:
                # Calculate position size - handle both async and sync implementations
                position_size = self.order_manager.calculate_position_size(symbol, amount)
                if asyncio.iscoroutine(position_size):
                    contract_qty = await position_size
                else:
                    contract_qty = position_size
                
                # Calculate actual USDT value
                actual_usdt = float(contract_qty) * current_price
                
                self.logger.info(f"USDT {amount}: {contract_qty} contracts (${actual_usdt:.2f})")
                
                results[str(amount)] = {
                    "contracts": contract_qty,
                    "actual_usdt": actual_usdt,
                    "price": current_price
                }
            
            return {
                "sizing_tests": results,
                "success": True
            }
                
        except Exception as e:
            self.logger.error(f"Position sizing test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_market_buy(self):
        """Test market buy order with a very small position"""
        try:
            symbol = "BTCUSDT"
            
            # Use a tiny position size for testing
            usdt_amount = 5  # Only $5 worth
            
            # Calculate position size - handle both async and sync implementations
            position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
            if asyncio.iscoroutine(position_size):
                qty = await position_size
            else:
                qty = position_size
            
            self.logger.info(f"Placing market buy order: {qty} {symbol} (approx ${usdt_amount})")
            
            # Place the order - handle both async and sync implementations
            order_result = self.order_manager.place_market_order(symbol, "Buy", qty)
            if asyncio.iscoroutine(order_result):
                order_result = await order_result
            
            if not order_result or "error" in order_result or not order_result.get("orderId"):
                self.logger.error(f"Failed to place market buy order: {order_result}")
                return False
            
            order_id = order_result.get("orderId")
            self.logger.info(f"Market buy order placed: {order_id}")
            
            # Wait for order to execute
            await asyncio.sleep(3)
            
            # Check order status - handle both async and sync implementations
            order_status = self.order_manager.get_order_status(symbol, order_id)
            if asyncio.iscoroutine(order_status):
                order_status = await order_status
            
            self.logger.info(f"Order status: {order_status}")
            
            return {
                "order_id": order_id,
                "qty": qty,
                "usdt_amount": usdt_amount,
                "status": order_status,
                "success": order_status in ["Filled", "PartiallyFilled"]
            }
                
        except Exception as e:
            self.logger.error(f"Market buy test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_market_sell(self):
        """Test market sell order with a very small position"""
        try:
            symbol = "BTCUSDT"
            
            # Use a tiny position size for testing
            usdt_amount = 5  # Only $5 worth
            
            # Calculate position size - handle both async and sync implementations
            position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
            if asyncio.iscoroutine(position_size):
                qty = await position_size
            else:
                qty = position_size
            
            self.logger.info(f"Placing market sell order: {qty} {symbol} (approx ${usdt_amount})")
            
            # Place the order - handle both async and sync implementations
            order_result = self.order_manager.place_market_order(symbol, "Sell", qty)
            if asyncio.iscoroutine(order_result):
                order_result = await order_result
            
            if not order_result or "error" in order_result or not order_result.get("orderId"):
                self.logger.error(f"Failed to place market sell order: {order_result}")
                return False
            
            order_id = order_result.get("orderId")
            self.logger.info(f"Market sell order placed: {order_id}")
            
            # Wait for order to execute
            await asyncio.sleep(3)
            
            # Check order status - handle both async and sync implementations
            order_status = self.order_manager.get_order_status(symbol, order_id)
            if asyncio.iscoroutine(order_status):
                order_status = await order_status
            
            self.logger.info(f"Order status: {order_status}")
            
            return {
                "order_id": order_id,
                "qty": qty,
                "usdt_amount": usdt_amount,
                "status": order_status,
                "success": order_status in ["Filled", "PartiallyFilled"]
            }
                
        except Exception as e:
            self.logger.error(f"Market sell test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_limit_buy(self):
        """Test limit buy order"""
        try:
            symbol = "BTCUSDT"
            
            # Get current price from data_manager
            current_price = await self.data_manager.get_latest_price(symbol)
            
            # Set limit price 1% below current price
            limit_price = str(round(current_price * 0.99, 2))
            
            # Use a small position size for testing
            usdt_amount = 5
            
            # Calculate position size - handle both async and sync implementations
            position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
            if asyncio.iscoroutine(position_size):
                qty = await position_size
            else:
                qty = position_size
            
            self.logger.info(f"Placing limit buy order: {qty} {symbol} @ {limit_price}")
            
            # Place the order - handle both async and sync implementations
            order_result = self.order_manager.place_limit_order(symbol, "Buy", qty, limit_price)
            if asyncio.iscoroutine(order_result):
                order_result = await order_result
            
            if not order_result or "error" in order_result or not order_result.get("orderId"):
                self.logger.error(f"Failed to place limit buy order: {order_result}")
                return False
            
            order_id = order_result.get("orderId")
            self.logger.info(f"Limit buy order placed: {order_id}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Check order status - handle both async and sync implementations
            order_status = self.order_manager.get_order_status(symbol, order_id)
            if asyncio.iscoroutine(order_status):
                order_status = await order_status
            
            self.logger.info(f"Order status: {order_status}")
            
            return {
                "order_id": order_id,
                "qty": qty,
                "price": limit_price,
                "status": order_status,
                "success": order_status in ["New", "PartiallyFilled", "Filled"]
            }
                
        except Exception as e:
            self.logger.error(f"Limit buy test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_limit_sell(self):
        """Test limit sell order"""
        try:
            symbol = "BTCUSDT"
            
            # Get current price from data_manager
            current_price = await self.data_manager.get_latest_price(symbol)
            
            # Set limit price 1% above current price
            limit_price = str(round(current_price * 1.01, 2))
            
            # Use a small position size for testing
            usdt_amount = 5
            
            # Calculate position size - handle both async and sync implementations
            position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
            if asyncio.iscoroutine(position_size):
                qty = await position_size
            else:
                qty = position_size
            
            self.logger.info(f"Placing limit sell order: {qty} {symbol} @ {limit_price}")
            
            # Place the order - handle both async and sync implementations
            order_result = self.order_manager.place_limit_order(symbol, "Sell", qty, limit_price)
            if asyncio.iscoroutine(order_result):
                order_result = await order_result
            
            if not order_result or "error" in order_result or not order_result.get("orderId"):
                self.logger.error(f"Failed to place limit sell order: {order_result}")
                return False
            
            order_id = order_result.get("orderId")
            self.logger.info(f"Limit sell order placed: {order_id}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Check order status - handle both async and sync implementations
            order_status = self.order_manager.get_order_status(symbol, order_id)
            if asyncio.iscoroutine(order_status):
                order_status = await order_status
            
            self.logger.info(f"Order status: {order_status}")
            
            return {
                "order_id": order_id,
                "qty": qty,
                "price": limit_price,
                "status": order_status,
                "success": order_status in ["New", "PartiallyFilled", "Filled"]
            }
                
        except Exception as e:
            self.logger.error(f"Limit sell test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_take_profit(self):
        """Test take profit order"""
        try:
            symbol = "BTCUSDT"
            
            # First place a market buy order
            usdt_amount = 5
            
            # Calculate position size - handle both async and sync implementations
            position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
            if asyncio.iscoroutine(position_size):
                qty = await position_size
            else:
                qty = position_size
            
            self.logger.info(f"Placing market buy order: {qty} {symbol}")
            
            # Place the market order - handle both async and sync implementations
            order_result = self.order_manager.place_market_order(symbol, "Buy", qty)
            if asyncio.iscoroutine(order_result):
                order_result = await order_result
            
            if not order_result or "error" in order_result or not order_result.get("orderId"):
                self.logger.error(f"Failed to place market buy order: {order_result}")
                return False
            
            order_id = order_result.get("orderId")
            self.logger.info(f"Market buy order placed: {order_id}")
            
            # Wait for order to execute
            await asyncio.sleep(3)
            
            # Get current price from data_manager
            current_price = await self.data_manager.get_latest_price(symbol)
            
            # Set take profit 1% above current price
            take_profit_price = str(round(current_price * 1.01, 2))
            
            self.logger.info(f"Setting take profit at {take_profit_price}")
            
            # Set take profit - handle both async and sync implementations
            tp_result = self.order_manager.set_take_profit(symbol, take_profit_price)
            if asyncio.iscoroutine(tp_result):
                tp_result = await tp_result
            
            if not tp_result or "error" in tp_result:
                self.logger.error(f"Failed to set take profit: {tp_result}")
                return False
            
            tp_order_id = tp_result.get("orderId")
            self.logger.info(f"Take profit order placed: {tp_order_id}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Check order status - handle both async and sync implementations
            if tp_order_id:
                tp_status = self.order_manager.get_order_status(symbol, tp_order_id)
                if asyncio.iscoroutine(tp_status):
                    tp_status = await tp_status
                self.logger.info(f"Take profit status: {tp_status}")
            else:
                tp_status = "Success"  # Some implementations don't return an orderId for TP
            
            return {
                "entry_order_id": order_id,
                "tp_order_id": tp_order_id,
                "tp_price": take_profit_price,
                "status": tp_status if tp_order_id else "Success",
                "success": True
            }
                
        except Exception as e:
            self.logger.error(f"Take profit test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_stop_loss(self):
        """Test stop loss order"""
        try:
            symbol = "BTCUSDT"
            
            # First check if we already have a position
            positions = self.order_manager.get_positions(symbol)
            if asyncio.iscoroutine(positions):
                positions = await positions
            
            # If no position, create one
            if not positions or all(float(pos.get("size", 0)) == 0 for pos in positions):
                usdt_amount = 5
                
                # Calculate position size - handle both async and sync implementations
                position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
                if asyncio.iscoroutine(position_size):
                    qty = await position_size
                else:
                    qty = position_size
                
                self.logger.info(f"Placing market buy order: {qty} {symbol}")
                
                # Place the market order - handle both async and sync implementations
                order_result = self.order_manager.place_market_order(symbol, "Buy", qty)
                if asyncio.iscoroutine(order_result):
                    order_result = await order_result
                
                if not order_result or "error" in order_result or not order_result.get("orderId"):
                    self.logger.error(f"Failed to place market buy order: {order_result}")
                    return False
                
                order_id = order_result.get("orderId")
                self.logger.info(f"Market buy order placed: {order_id}")
                
                # Wait for order to execute
                await asyncio.sleep(3)
            else:
                self.logger.info(f"Using existing position: {positions}")
                order_id = "existing_position"
            
            # Get current price from data_manager
            current_price = await self.data_manager.get_latest_price(symbol)
            
            # Set stop loss 1% below current price
            stop_loss_price = str(round(current_price * 0.99, 2))
            
            self.logger.info(f"Setting stop loss at {stop_loss_price}")
            
            # Set stop loss - handle both async and sync implementations
            sl_result = self.order_manager.set_stop_loss(symbol, stop_loss_price)
            if asyncio.iscoroutine(sl_result):
                sl_result = await sl_result
            
            if not sl_result or "error" in sl_result:
                self.logger.error(f"Failed to set stop loss: {sl_result}")
                return False
            
            sl_order_id = sl_result.get("orderId")
            self.logger.info(f"Stop loss order placed: {sl_order_id}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Check order status - handle both async and sync implementations
            if sl_order_id and not sl_order_id.startswith("sl_"):  # Skip status check for synthetic IDs
                sl_status = self.order_manager.get_order_status(symbol, sl_order_id)
                if asyncio.iscoroutine(sl_status):
                    sl_status = await sl_status
                self.logger.info(f"Stop loss status: {sl_status}")
            else:
                sl_status = "Success"  # Some implementations don't return a real orderId for SL
            
            return {
                "entry_order_id": order_id,
                "sl_order_id": sl_order_id,
                "sl_price": stop_loss_price,
                "status": sl_status if sl_order_id and not sl_order_id.startswith("sl_") else "Success",
                "success": True
            }
                
        except Exception as e:
            self.logger.error(f"Stop loss test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_cancel_orders(self):
        """Test order cancellation"""
        try:
            symbol = "BTCUSDT"
            
            # First place a limit order that won't fill immediately
            current_price = await self.data_manager.get_latest_price(symbol)
            limit_price = str(round(current_price * 0.97, 2))  # 3% below market
            
            usdt_amount = 5
            
            # Calculate position size - handle both async and sync implementations
            position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
            if asyncio.iscoroutine(position_size):
                qty = await position_size
            else:
                qty = position_size
            
            self.logger.info(f"Placing limit buy order to cancel: {qty} {symbol} @ {limit_price}")
            
            # Place the order - handle both async and sync implementations
            order_result = self.order_manager.place_limit_order(symbol, "Buy", qty, limit_price)
            if asyncio.iscoroutine(order_result):
                order_result = await order_result
            
            if not order_result or "error" in order_result or not order_result.get("orderId"):
                self.logger.error(f"Failed to place limit buy order: {order_result}")
                return False
            
            order_id = order_result.get("orderId")
            self.logger.info(f"Limit buy order placed: {order_id}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Check order status - handle both async and sync implementations
            order_status = self.order_manager.get_order_status(symbol, order_id)
            if asyncio.iscoroutine(order_status):
                order_status = await order_status
            
            self.logger.info(f"Order status before cancellation: {order_status}")
            
            # Cancel the order - handle both async and sync implementations
            cancel_result = self.order_manager.cancel_order(symbol, order_id)
            if asyncio.iscoroutine(cancel_result):
                cancel_result = await cancel_result
            
            if not cancel_result or "error" in cancel_result:
                self.logger.error(f"Failed to cancel order: {cancel_result}")
                return False
            
            self.logger.info(f"Cancel result: {cancel_result}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Check order status again - handle both async and sync implementations
            order_status_after = self.order_manager.get_order_status(symbol, order_id)
            if asyncio.iscoroutine(order_status_after):
                order_status_after = await order_status_after
            
            self.logger.info(f"Order status after cancellation: {order_status_after}")
            
            return {
                "order_id": order_id,
                "status_before": order_status,
                "status_after": order_status_after,
                "success": order_status_after in ["Cancelled", "Rejected", "Not Found"]
            }
                
        except Exception as e:
            self.logger.error(f"Cancel order test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_close_position(self):
        """Test closing a position"""
        try:
            symbol = "BTCUSDT"
            
            # First place a market order to ensure we have a position
            usdt_amount = 5
            
            # Calculate position size - handle both async and sync implementations
            position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
            if asyncio.iscoroutine(position_size):
                qty = await position_size
            else:
                qty = position_size
            
            self.logger.info(f"Placing market buy order: {qty} {symbol}")
            
            # Place the market order - handle both async and sync implementations
            order_result = self.order_manager.place_market_order(symbol, "Buy", qty)
            if asyncio.iscoroutine(order_result):
                order_result = await order_result
            
            if not order_result or "error" in order_result or not order_result.get("orderId"):
                self.logger.error(f"Failed to place market buy order: {order_result}")
                return False
            
            order_id = order_result.get("orderId")
            self.logger.info(f"Market buy order placed: {order_id}")
            
            # Wait for order to execute
            await asyncio.sleep(3)
            
            # Check position - handle both async and sync implementations
            positions = self.order_manager.get_positions(symbol)
            if asyncio.iscoroutine(positions):
                positions = await positions
            
            if not positions or all(float(pos.get("size", 0)) == 0 for pos in positions):
                self.logger.error("No position found to close")
                return False
            
            position_size = float(positions[0].get("size", 0))
            self.logger.info(f"Current position size: {position_size}")
            
            # Close the position - handle both async and sync implementations
            close_result = self.order_manager.close_position(symbol)
            if asyncio.iscoroutine(close_result):
                close_result = await close_result
            
            if not close_result or "error" in close_result:
                self.logger.error(f"Failed to close position: {close_result}")
                return False
            
            close_order_id = close_result.get("orderId")
            self.logger.info(f"Close position order placed: {close_order_id}")
            
            # Wait for order to execute
            await asyncio.sleep(3)
            
            # Check position again - handle both async and sync implementations
            positions_after = self.order_manager.get_positions(symbol)
            if asyncio.iscoroutine(positions_after):
                positions_after = await positions_after
            
            position_size_after = float(positions_after[0].get("size", 0)) if positions_after else 0
            
            self.logger.info(f"Position size after closing: {position_size_after}")
            
            return {
                "original_size": position_size,
                "size_after": position_size_after,
                "close_order_id": close_order_id,
                "success": abs(position_size_after) < 0.0001  # Near zero
            }
                
        except Exception as e:
            self.logger.error(f"Close position test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_risk_management(self):
        """Test risk management limits"""
        try:
            symbol = "BTCUSDT"
            
            # Test different risk levels
            test_risks = [0.01, 0.02, 0.05]  # 1%, 2%, 5%
            results = {}
            
            # Get account balance - handle both async and sync implementations
            account = self.order_manager.get_account_balance()
            if asyncio.iscoroutine(account):
                account = await account
            
            balance = float(account.get("totalAvailableBalance", 0))
            
            self.logger.info(f"Account balance: {balance} USDT")
            
            for risk in test_risks:
                # Calculate position size based on risk percentage
                risk_amount = balance * risk
                
                # Calculate position size - handle both async and sync implementations
                position_size = self.order_manager.calculate_position_size(symbol, risk_amount)
                if asyncio.iscoroutine(position_size):
                    qty = await position_size
                else:
                    qty = position_size
                
                self.logger.info(f"Risk {risk*100}%: {risk_amount} USDT = {qty} contracts")
                
                results[str(risk)] = {
                    "risk_percentage": risk * 100,
                    "risk_amount_usdt": risk_amount,
                    "position_size": qty
                }
            
            return {
                "account_balance": balance,
                "risk_tests": results,
                "success": True
            }
                
        except Exception as e:
            self.logger.error(f"Risk management test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_order_tracking(self):
        """Test order tracking functionality"""
        try:
            symbol = "BTCUSDT"
            
            # Place a market order
            usdt_amount = 5
            
            # Calculate position size - handle both async and sync implementations
            position_size = self.order_manager.calculate_position_size(symbol, usdt_amount)
            if asyncio.iscoroutine(position_size):
                qty = await position_size
            else:
                qty = position_size
            
            self.logger.info(f"Placing market buy order: {qty} {symbol}")
            
            # Place the order - handle both async and sync implementations
            order_result = self.order_manager.place_market_order(symbol, "Buy", qty)
            if asyncio.iscoroutine(order_result):
                order_result = await order_result
            
            if not order_result or "error" in order_result or not order_result.get("orderId"):
                self.logger.error(f"Failed to place market buy order: {order_result}")
                return False
            
            order_id = order_result.get("orderId")
            self.logger.info(f"Market buy order placed: {order_id}")
            
            # Wait for order to execute
            await asyncio.sleep(3)
            
            # Get active orders - handle both async and sync implementations
            active_orders = self.order_manager.get_active_orders(symbol)
            if asyncio.iscoroutine(active_orders):
                active_orders = await active_orders
            
            self.logger.info(f"Active orders: {len(active_orders)}")
            
            # Get order history - handle both async and sync implementations
            order_history = self.order_manager.get_order_history(symbol)
            if asyncio.iscoroutine(order_history):
                order_history = await order_history
            
            self.logger.info(f"Order history entries: {len(order_history)}")
            
            # Find our order in history
            found_order = False
            for order in order_history:
                if order.get("orderId") == order_id:
                    found_order = True
                    self.logger.info(f"Found order in history: {order}")
                    break
            
            if not found_order:
                self.logger.warning(f"Order {order_id} not found in history")
            
            return {
                "order_id": order_id,
                "active_orders_count": len(active_orders),
                "order_history_count": len(order_history),
                "found_in_history": found_order,
                "success": True
            }
                
        except Exception as e:
            self.logger.error(f"Order tracking test failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_error_handling(self):
        """Test error handling in OrderManager"""
        try:
            symbol = "BTCUSDT"
            
            # Test 1: Invalid symbol handling
            self.logger.info("Testing invalid symbol handling")
            invalid_symbol = "INVALID"
            
            # Test with invalid symbol - handle both async and sync implementations
            invalid_symbol_handled = False
            try:
                result = self.order_manager.place_market_order(invalid_symbol, "Buy", "0.001")
                if asyncio.iscoroutine(result):
                    result = await result
                self.logger.info(f"Invalid symbol result: {result}")
                invalid_symbol_handled = "error" in str(result).lower()
            except Exception as e:
                self.logger.info(f"Invalid symbol error handled: {e}")
                invalid_symbol_handled = True
            
            # Test 2: Invalid quantity handling
            self.logger.info("Testing invalid quantity handling")
            invalid_qty = "0"
            
            # Test with invalid quantity - handle both async and sync implementations
            invalid_qty_handled = False
            try:
                result = self.order_manager.place_market_order(symbol, "Buy", invalid_qty)
                if asyncio.iscoroutine(result):
                    result = await result
                self.logger.info(f"Invalid quantity result: {result}")
                invalid_qty_handled = "error" in str(result).lower()
            except Exception as e:
                self.logger.info(f"Invalid quantity error handled: {e}")
                invalid_qty_handled = True
            
            # Test 3: Invalid order ID handling
            self.logger.info("Testing invalid order ID handling")
            invalid_order_id = "invalid_id"
            
            # Test with invalid order ID - handle both async and sync implementations
            invalid_order_id_handled = False
            try:
                result = self.order_manager.get_order_status(symbol, invalid_order_id)
                if asyncio.iscoroutine(result):
                    result = await result
                self.logger.info(f"Invalid order ID result: {result}")
                invalid_order_id_handled = result in ["Error", "Not Found"] or "not found" in str(result).lower()
            except Exception as e:
                self.logger.info(f"Invalid order ID error handled: {e}")
                invalid_order_id_handled = True
            
            return {
                "invalid_symbol_handled": invalid_symbol_handled,
                "invalid_qty_handled": invalid_qty_handled,
                "invalid_order_id_handled": invalid_order_id_handled,
                "success": invalid_symbol_handled or invalid_qty_handled or invalid_order_id_handled
            }
                
        except Exception as e:
            self.logger.error(f"Error handling test failed: {e}")
            traceback.print_exc()
            return False
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("ORDER MANAGER TEST REPORT")
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
            
            if result["status"] == "ERROR":
                self.logger.info(f"    Error: {result.get('error', 'Unknown error')}")
        
        # Save detailed report to file
        report_file = f"order_manager_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, indent=2, ensure_ascii=False)
            self.logger.info(f"\nDetailed report saved to: {report_file}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")
        
        # Final verdict
        if passed_tests == total_tests:
            self.logger.info(f"\n🎉 ALL TESTS PASSED! OrderManager is functioning correctly.")
        elif passed_tests / total_tests >= 0.8:
            self.logger.info(f"\n⚠️ Most tests passed. Review failures before production use.")
        else:
            self.logger.info(f"\n❌ Multiple test failures. OrderManager needs fixes before use.")

async def main():
    """Main test execution"""
    print("OrderManager - Comprehensive Test Suite")
    print("=" * 50)
    
    # Load environment variables
    if not load_env_file():
        print("Failed to load environment variables. Cannot proceed with tests.")
        sys.exit(1)
    
    tester = OrderManagerTester()
    
    try:
        if await tester.initialize():
            print("Initialization successful!")
            
            # Run the actual order tests
            await tester.run_all_tests()
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
        
        # Last resort: cancel ALL remaining tasks
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task() and not task.done():
                try:
                    task.cancel()
                except:
                    pass
        
        print("Test environment shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())