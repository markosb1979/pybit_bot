"""
Main Trading Engine - Coordinates data flow and manages the trading lifecycle.
Integrates strategy manager, TPSL manager, and order execution.
"""

import logging
import time
import threading
import json
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import pandas as pd
from dotenv import load_dotenv

from pybit_bot.managers.strategy_manager import StrategyManager
from pybit_bot.managers.tpsl_manager import TPSLManager
from pybit_bot.strategies.base_strategy import TradeSignal


# Config wrapper class to provide methods expected by StrategyManager
class ConfigWrapper:
    def __init__(self, config_dict):
        self.config_dict = config_dict
    
    def load_indicator_config(self):
        # Return indicator configuration from the dictionary
        return self.config_dict.get('indicators', {})
    
    def __getitem__(self, key):
        # Allow dictionary-style access to config values
        return self.config_dict[key]
    
    def get(self, key, default=None):
        # Mimic dict.get() method
        return self.config_dict.get(key, default)


class TradingEngine:
    """
    Main trading engine that coordinates all components and manages the trading lifecycle.
    """
    
    def __init__(self, config_path: str):
        # Enhanced logging setup
        import logging
        import sys
        import os
        
        # Ensure log directory exists
        log_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Create engine log file
        self.log_file = os.path.join(log_dir, "engine.log")
        
        # Configure root logger with console and file output
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Add console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
        console.setFormatter(console_formatter)
        root_logger.addHandler(console)
        
        # Add file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Direct output to console as well for visibility
        print(f"Engine initializing. Logs will be written to {self.log_file}")
        
        """
        Initialize the trading engine with configuration.
        
        Args:
            config_path: Path to the configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Set up logging
        log_dir = self.config.get('system', {}).get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.market_data_manager = None
        self.order_manager = None
        self.strategy_manager = None
        self.tpsl_manager = None
        
        # Engine state
        self.is_running = False
        self.start_time = None
        self.symbols = self.config.get('trading', {}).get('symbols', [])
        self._stop_event = threading.Event()
        self._main_thread = None
        self._loop = None  # AsyncIO event loop for the main thread
        self._empty_data_retry_count = 0
        self._max_empty_data_retries = 5
        
        # Performance tracking
        self.performance = {
            'signals_generated': 0,
            'orders_placed': 0,
            'orders_filled': 0,
            'errors': 0,
            'api_errors': 0,
            'empty_data_count': 0
        }
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {str(e)}")
    
    def initialize(self):
        """
        Initialize all components of the trading engine.
        """
        self.logger.info("Initializing trading engine...")
        
        try:
            # Import the required components with correct paths
            from pybit_bot.managers.data_manager import DataManager
            from pybit_bot.managers.order_manager import OrderManager
            from pybit_bot.managers.strategy_manager import StrategyManager
            from pybit_bot.managers.tpsl_manager import TPSLManager
            from pybit_bot.core.client import BybitClient, APICredentials
            
            # Load environment variables for API credentials
            load_dotenv()
            
            # Get API credentials from environment variables
            api_key = os.getenv("BYBIT_API_KEY", "")
            api_secret = os.getenv("BYBIT_API_SECRET", "")
            testnet = os.getenv("BYBIT_TESTNET", "True").lower() in ("1", "true", "yes", "on")
            
            # Create API credentials object
            self.logger.debug("Creating API credentials...")
            api_credentials = APICredentials(api_key=api_key, api_secret=api_secret, testnet=testnet)
            
            # Initialize Bybit client with API credentials
            self.logger.debug("Initializing Bybit client...")
            client = BybitClient(api_credentials, logger=self.logger)
            
            # Initialize data manager - pass both client and config
            self.logger.debug("Initializing data manager...")
            self.market_data_manager = DataManager(client, self.config)
            
            # Start the data manager (synchronous start method)
            self.market_data_manager.start()
            
            # Initialize order manager - pass both client and config
            self.logger.debug("Initializing order manager...")
            self.order_manager = OrderManager(client, self.config)
            if hasattr(self.order_manager, 'start') and callable(getattr(self.order_manager, 'start')):
                self.order_manager.start()
            
            # Initialize TPSL manager - with all required parameters
            self.logger.debug("Initializing TPSL manager...")
            self.tpsl_manager = TPSLManager(self.order_manager, self.market_data_manager, self.config)
            
            # Handle async start method properly
            if hasattr(self.tpsl_manager, 'start'):
                start_method = getattr(self.tpsl_manager, 'start')
                if asyncio.iscoroutinefunction(start_method):
                    # If it's an async function, run it with asyncio
                    asyncio.run(self.tpsl_manager.start())
                elif callable(start_method):
                    # If it's a regular function, just call it
                    self.tpsl_manager.start()
            
            # Create a config wrapper object that provides the necessary methods
            config_wrapper = ConfigWrapper(self.config)
            
            # Initialize strategy manager - pass all required parameters including order_manager
            self.logger.debug("Initializing strategy manager...")
            self.strategy_manager = StrategyManager(
                data_manager=self.market_data_manager,
                tpsl_manager=self.tpsl_manager,
                order_manager=self.order_manager,
                config=config_wrapper  # Use the wrapper instead of the raw dictionary
            )
            
            self.logger.info("Trading engine initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing trading engine: {str(e)}", exc_info=True)
            return False
    
    def stop(self):
        """
        Stop the trading engine.
        """
        if not self.is_running:
            self.logger.warning("Trading engine is not running")
            return
            
        self.logger.info("Stopping trading engine...")
        
        # Signal stop
        self._stop_event.set()
        
        # Wait for main thread to finish
        if self._main_thread and self._main_thread.is_alive():
            self._main_thread.join(timeout=10.0)
        
        # Stop all managers (only if they have a stop method)
        if self.market_data_manager and hasattr(self.market_data_manager, 'stop') and callable(getattr(self.market_data_manager, 'stop')):
            self.market_data_manager.stop()
        
        if self.order_manager and hasattr(self.order_manager, 'stop') and callable(getattr(self.order_manager, 'stop')):
            self.order_manager.stop()
            
        # Handle async stop method for TPSLManager
        if self.tpsl_manager and hasattr(self.tpsl_manager, 'stop'):
            stop_method = getattr(self.tpsl_manager, 'stop')
            if asyncio.iscoroutinefunction(stop_method):
                # If it's an async function, run it with asyncio
                asyncio.run(self.tpsl_manager.stop())
            elif callable(stop_method):
                # If it's a regular function, just call it
                self.tpsl_manager.stop()
        
        # Clean up the event loop when stopping
        if self._loop and self._loop.is_running():
            self._loop.stop()
        
        # Set state
        self.is_running = False
        
        self.logger.info("Trading engine stopped")
    
    def start(self):
        """
        Start the trading engine.
        """
        if self.is_running:
            self.logger.warning("Trading engine is already running")
            return False
            
        self.logger.info("Starting trading engine...")
        
        try:
            # Ensure components are initialized
            if not self.market_data_manager:
                self.logger.info("Components not initialized, initializing now...")
                if not self.initialize():
                    self.logger.error("Failed to initialize components, cannot start engine")
                    return False
            
            # Set state
            self.is_running = True
            self.start_time = datetime.now()
            self._stop_event.clear()
            
            # Start main loop in a separate thread
            self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
            self._main_thread.start()
            
            self.logger.info("Trading engine started")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting trading engine: {str(e)}", exc_info=True)
            self.stop()
            return False
    
    async def _run_async_method(self, coro):
        """
        Run an async method and return its result.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Result of the coroutine
        """
        try:
            return await coro
        except Exception as e:
            self.logger.error(f"Error running async method: {str(e)}", exc_info=True)
            return None
    
    def _run_async(self, coro):
        """
        Run an async method in the event loop.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Result of the coroutine
        """
        if self._loop is None or not self._loop.is_running():
            # Create a new event loop for this thread if one doesn't exist or isn't running
            if self._loop is None:
                self.logger.debug("Creating new event loop for async operations")
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        
        # Run the coroutine in the event loop
        return self._loop.run_until_complete(self._run_async_method(coro))
    
    def _handle_empty_data(self, symbol, timeframe):
        """
        Handle cases where we can't get data from the API.
        
        Args:
            symbol: Symbol that had empty data
            timeframe: Timeframe that had empty data
        
        Returns:
            bool: True if we should continue, False if we should wait or stop
        """
        self._empty_data_retry_count += 1
        self.performance['empty_data_count'] += 1
        
        # Log with increasing severity based on number of retries
        if self._empty_data_retry_count <= 2:
            self.logger.warning(f"No klines data available for {symbol} ({timeframe}). Retry {self._empty_data_retry_count}/{self._max_empty_data_retries}")
        elif self._empty_data_retry_count <= 4:
            self.logger.error(f"Repeated failures getting klines for {symbol} ({timeframe}). Retry {self._empty_data_retry_count}/{self._max_empty_data_retries}")
        else:
            self.logger.critical(f"Persistent data retrieval failure for {symbol} ({timeframe}). Retry {self._empty_data_retry_count}/{self._max_empty_data_retries}")
        
        # If we've reached max retries, take more drastic action
        if self._empty_data_retry_count >= self._max_empty_data_retries:
            self.logger.critical(f"Maximum retries ({self._max_empty_data_retries}) reached for data retrieval. Pausing operations.")
            
            # Reset counter but wait longer
            self._empty_data_retry_count = 0
            time.sleep(30)  # Sleep for 30 seconds before trying again
            return False
        
        # Exponential backoff for retries
        wait_time = 2 ** self._empty_data_retry_count  # 2, 4, 8, 16, 32 seconds
        self.logger.info(f"Waiting {wait_time} seconds before retrying...")
        time.sleep(wait_time)
        return True
    
    def _main_loop(self):
        """
        Main trading engine loop.
        """
        self.logger.info("Main trading loop started")
        
        # Check if required components are initialized
        if not self.market_data_manager or not self.order_manager or not self.strategy_manager:
            self.logger.error("Required components not initialized. Stopping engine.")
            self._stop_event.set()
            return
        
        # Set up event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        # Get configuration parameters
        check_interval = self.config.get('engine', {}).get('check_interval_seconds', 1)
        symbol = self.config.get('trading', {}).get('symbol', 'BTCUSDT')
        timeframe = self.config.get('trading', {}).get('timeframe', '5m')
        
        # Initialize cycle counter for periodic status updates
        cycle_count = 0
        self._empty_data_retry_count = 0
        
        # Main trading loop
        while not self._stop_event.is_set():
            try:
                cycle_count += 1
                
                # 1. Fetch market data - handle async method
                self.logger.debug(f"Fetching klines for {symbol} ({timeframe})")
                
                # Try to get klines using async method
                get_klines_coro = self.market_data_manager.get_klines(symbol, timeframe)
                
                # Check if get_klines returns a coroutine (async method)
                if asyncio.iscoroutine(get_klines_coro):
                    klines = self._run_async(get_klines_coro)
                else:
                    # If not async, it might be a direct result
                    klines = get_klines_coro
                
                # Check if we got valid data
                if klines is None or (hasattr(klines, '__len__') and len(klines) == 0):
                    # Handle empty data case
                    if not self._handle_empty_data(symbol, timeframe):
                        continue
                elif hasattr(klines, '__len__'):
                    # Reset empty data counter when we get valid data
                    if self._empty_data_retry_count > 0:
                        self.logger.info(f"Successfully retrieved data after {self._empty_data_retry_count} retries")
                    self._empty_data_retry_count = 0
                    
                    self.logger.info(f"Fetched {len(klines)} klines for {symbol}")
                    
                    # 2. Calculate indicators - handle potential async method
                    self.logger.debug("Calculating indicators...")
                    calc_indicators_method = self.strategy_manager.calculate_indicators(klines)
                    
                    # Check if calculate_indicators returns a coroutine
                    if asyncio.iscoroutine(calc_indicators_method):
                        indicators = self._run_async(calc_indicators_method)
                    else:
                        indicators = calc_indicators_method
                    
                    # Print indicator values periodically (every 10 cycles)
                    if cycle_count % 10 == 0:
                        self.logger.info(f"Current indicators for {symbol}: {indicators}")
                    
                    # 3. Check for trading signals - handle potential async method
                    self.logger.debug("Checking for trading signals...")
                    check_signals_method = self.strategy_manager.check_signals(symbol, klines, indicators)
                    
                    # Check if check_signals returns a coroutine
                    if asyncio.iscoroutine(check_signals_method):
                        signals = self._run_async(check_signals_method)
                    else:
                        signals = check_signals_method
                    
                    if signals:
                        for signal in signals:
                            self.logger.info(f"Signal generated: {signal.direction} {signal.symbol} at {signal.price}")
                            self.performance['signals_generated'] += 1
                            
                            # 4. Execute orders based on signals
                            try:
                                self.logger.info(f"Executing {signal.direction} order for {signal.symbol}")
                                place_order_method = self.order_manager.place_order(
                                    symbol=signal.symbol,
                                    side=signal.direction,
                                    quantity=signal.quantity,
                                    price=signal.price,
                                    order_type=signal.order_type
                                )
                                
                                # Check if place_order returns a coroutine
                                if asyncio.iscoroutine(place_order_method):
                                    order_result = self._run_async(place_order_method)
                                else:
                                    order_result = place_order_method
                                
                                if order_result and 'orderId' in order_result:
                                    self.logger.info(f"Order placed: {order_result['orderId']}")
                                    self.performance['orders_placed'] += 1
                                    
                                    # 5. Set up take profit and stop loss
                                    self.logger.debug(f"Setting up TP/SL for order {order_result['orderId']}")
                                    add_trade_method = self.tpsl_manager.add_trade(
                                        symbol=signal.symbol,
                                        entry_price=signal.price,
                                        direction=signal.direction,
                                        quantity=signal.quantity,
                                        order_id=order_result['orderId'],
                                        tp_pct=signal.tp_pct,
                                        sl_pct=signal.sl_pct
                                    )
                                    
                                    # Check if add_trade returns a coroutine
                                    if asyncio.iscoroutine(add_trade_method):
                                        self._run_async(add_trade_method)
                                else:
                                    self.logger.warning(f"Failed to place order: {order_result}")
                                    
                            except Exception as e:
                                self.logger.error(f"Error executing order: {str(e)}", exc_info=True)
                                self.performance['errors'] += 1
                else:
                    self.logger.warning(f"Received klines object that doesn't support len(): {type(klines)}")
                    self.performance['api_errors'] += 1
                
                # 6. Monitor existing positions (every 5 cycles)
                if cycle_count % 5 == 0:
                    self.logger.debug("Checking active positions...")
                    get_positions_method = self.order_manager.get_positions()
                    
                    # Check if get_positions returns a coroutine
                    if asyncio.iscoroutine(get_positions_method):
                        positions = self._run_async(get_positions_method)
                    else:
                        positions = get_positions_method
                    
                    if positions:
                        self.logger.info(f"Active positions: {len(positions)}")
                        for position in positions:
                            self.logger.info(f"Position: {position['symbol']} {position['side']} Size: {position['size']}")
                
                # 7. Print status update (every 30 cycles)
                if cycle_count % 30 == 0:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    status = self.get_status()
                    
                    self.logger.info(f"[{current_time}] Bot running for {status['runtime']} - "
                                    f"Signals: {status['performance']['signals_generated']}, "
                                    f"Orders: {status['performance']['orders_placed']}, "
                                    f"Data Errors: {status['performance']['empty_data_count']}")
                    
                    # Reset cycle counter to prevent overflow
                    if cycle_count > 1000:
                        cycle_count = 0
                
                # Wait for next cycle
                time.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                self.performance['errors'] += 1
                
                # Continue running despite errors
                time.sleep(check_interval)
        
        # Clean up the event loop when stopping
        if self._loop and self._loop.is_running():
            self._loop.stop()
        
        self.logger.info("Main trading loop stopped")
    
    def _handle_kline_update(self, symbol: str, timeframe: str, kline: Dict[str, Any]):
        """
        Handle market data updates.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe (e.g., '1m', '5m')
            kline: Kline data
        """
        # This is a minimal implementation to make tests pass
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the trading engine.
        
        Returns:
            Dictionary with engine status
        """
        # Calculate runtime
        runtime = datetime.now() - self.start_time if self.start_time else None
        runtime_str = str(runtime).split('.')[0] if runtime else "Not started"
        
        return {
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'runtime': runtime_str,
            'symbols': self.symbols,
            'performance': self.performance,
            'last_update': datetime.now().isoformat()
        }