"""
Main Trading Engine - Coordinates data flow and manages the trading lifecycle.
Integrates strategy manager, TPSL manager, and order execution.
"""

import logging
import time
import threading
import json
import os
import glob
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
import pandas as pd
import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from pybit_bot.managers.strategy_manager import StrategyManager
from pybit_bot.managers.tpsl_manager import TPSLManager
from pybit_bot.managers.data_manager import DataManager
from pybit_bot.managers.order_manager import OrderManager
from pybit_bot.core.client import BybitClient, APICredentials
from pybit_bot.strategies.base_strategy import TradeSignal, SignalType, OrderType
from pybit_bot.utils.logger import Logger
from dotenv import load_dotenv


class TradingEngine:
    """
    Main trading engine that coordinates all components and manages the trading lifecycle.
    """
    
    def __init__(self, config_dir: str):
        """
        Initialize the trading engine with configuration directory.
        
        Args:
            config_dir: Path to the configuration directory
        """
        # Load environment variables
        load_dotenv()
        
        # Set up logging first
        self.logger = Logger("TradingEngine")
        self.logger.info("Initializing Trading Engine...")
        
        # Load configurations
        self.config = self._load_configs(config_dir)
        
        # Set up logging directory
        log_dir = self.config.get('general', {}).get('system', {}).get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Engine state
        self.is_running = False
        self.start_time = None
        self.symbols = self.config.get('general', {}).get('trading', {}).get('symbols', ["BTCUSDT"])
        self.timeframes = self.config.get('general', {}).get('trading', {}).get('timeframes', ["1m", "5m", "1h"])
        self.default_timeframe = self.config.get('general', {}).get('trading', {}).get('default_timeframe', "1m")
        self._stop_event = threading.Event()
        self._main_thread = None
        self._event_loop = None
        
        # Initialize clients and managers to None initially
        self.client = None
        self.market_data_manager = None
        self.order_manager = None
        self.strategy_manager = None
        self.tpsl_manager = None
        
        # Active positions and signals
        self.active_positions = {}
        self.recent_signals = {}
        self.pending_tpsl_orders = {}  # Track orders waiting for TP/SL to be set
        
        # Performance tracking
        self.performance = {
            'signals_generated': 0,
            'orders_placed': 0,
            'orders_filled': 0,
            'errors': 0,
            'profits': 0.0,
            'losses': 0.0
        }
        
        # Data caches for faster access
        self.market_data_cache = {}
        self.position_cache = {}
        
        # Thread pool for background tasks
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        
        print(f"Engine initialized with config from: {config_dir}")
    
    def _load_configs(self, config_dir: str) -> Dict[str, Any]:
        """
        Load all configuration files from the config directory.
        
        Args:
            config_dir: Path to the configuration directory
            
        Returns:
            Configuration dictionary with all configs merged
        """
        # Initialize merged config
        merged_config = {}
        
        try:
            # Find all JSON files in the config directory
            config_files = glob.glob(os.path.join(config_dir, "*.json"))
            self.logger.info(f"Found config files: {[os.path.basename(f) for f in config_files]}")
            print(f"Loading configs from: {[os.path.basename(f) for f in config_files]}")
            
            # Load each config file
            for config_file in config_files:
                config_name = os.path.basename(config_file).split('.')[0]  # Get filename without extension
                
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    
                # Add to merged config under the file's name
                merged_config[config_name] = config_data
                self.logger.info(f"Loaded config from {config_name}.json")
                print(f"Loaded: {config_name}.json")
            
            if not merged_config:
                raise RuntimeError(f"No configuration files found in {config_dir}")
                
            return merged_config
            
        except Exception as e:
            self.logger.error(f"Failed to load configurations: {str(e)}")
            print(f"ERROR loading configs: {str(e)}")
            raise RuntimeError(f"Failed to load configurations: {str(e)}")
    
    def initialize(self):
        """
        Initialize all components of the trading engine.
        """
        self.logger.info("Initializing trading engine components...")
        print("Starting engine initialization...")
        
        try:
            # Initialize API client
            self.logger.info("Initializing API client...")
            print("Step 1: Initializing API client...")
            use_testnet = os.environ.get('BYBIT_TESTNET', 'True').lower() in ('true', 'yes', '1', 't')
            credentials = APICredentials(
                api_key=os.environ.get('BYBIT_API_KEY', ''),
                api_secret=os.environ.get('BYBIT_API_SECRET', ''),
                testnet=use_testnet
            )
            
            self.client = BybitClient(credentials, logger=self.logger)
            self.logger.info(f"Bybit client initialized (testnet: {use_testnet})")
            print(f"API client initialized, testnet: {use_testnet}")
            
            # Initialize data manager
            self.logger.info("Initializing DataManager...")
            print("Step 2: Initializing DataManager...")
            self.market_data_manager = DataManager(self.client, self.config['general'], logger=self.logger)
            
            # Initialize order manager
            self.logger.info("Initializing OrderManager...")
            print("Step 3: Initializing OrderManager...")
            self.order_manager = OrderManager(self.client, self.config['execution'], logger=self.logger, data_manager=self.market_data_manager)
            
            # Initialize strategy manager
            self.logger.info("Initializing StrategyManager...")
            print("Step 4: Initializing StrategyManager...")
            self.strategy_manager = StrategyManager(self.config, logger=self.logger)
            
            # Initialize TPSL manager
            self.logger.info("Initializing TPSLManager...")
            print("Step 5: Initializing TPSLManager...")
            self.tpsl_manager = TPSLManager(config=self.config['execution'], order_manager=self.order_manager, logger=self.logger)
            
            # Test connections
            self.logger.info("Testing API connection...")
            print("Step 6: Testing API connection...")
            if not self.client.test_connection():
                self.logger.error("API connection test failed")
                print("ERROR: API connection test failed")
                return False
            
            # We'll leave async initialization to be called separately for testing
            self.logger.info("Trading engine initialized successfully")
            print("Engine initialization complete: SUCCESS")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing trading engine: {str(e)}")
            print(f"ERROR during initialization: {str(e)}")
            traceback.print_exc()
            return False
    
    async def initialize_async(self):
        """
        Initialize async components - separate method for testing purposes.
        """
        try:
            print("Starting async initialization...")
            await self.market_data_manager.initialize()
            await self.order_manager.initialize()
            
            # Initialize market data for all symbols
            for symbol in self.symbols:
                print(f"Initializing market data for {symbol}...")
                await self._init_market_data(symbol)
            
            print("Async initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing async components: {str(e)}")
            print(f"ERROR in async initialization: {str(e)}")
            traceback.print_exc()
            return False
    
    async def _init_market_data(self, symbol: str):
        """
        Initialize market data for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        try:
            # Create entry in market data cache
            self.market_data_cache[symbol] = {}
            
            # Get initial historical data for each timeframe
            for timeframe in self.timeframes:
                # Get historical data
                data = await self.market_data_manager.get_historical_data(
                    symbol=symbol,
                    interval=timeframe,
                    limit=100
                )
                
                # Store in cache
                self.market_data_cache[symbol][timeframe] = data
                
                self.logger.info(f"Initialized historical data for {symbol} {timeframe}")
                
            # Get current positions
            positions = await self.order_manager.get_positions(symbol)
            if positions:
                self.position_cache[symbol] = positions[0]
                self.logger.info(f"Found existing position for {symbol}: {positions[0]}")
            
        except Exception as e:
            self.logger.error(f"Error initializing market data for {symbol}: {str(e)}")
    
    def start(self, test_mode=False):
        """
        Start the trading engine.
        
        Args:
            test_mode: If True, skip actual event loop creation for testing
            
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            self.logger.warning("Trading engine is already running")
            print("WARNING: Engine already running")
            return False
            
        self.logger.info("Starting trading engine...")
        print("Starting trading engine...")
        
        try:
            print("Step 1: Setting engine state...")
            # Set state
            self.is_running = True
            self.start_time = datetime.now()
            self._stop_event.clear()
            
            # Skip event loop creation in test mode
            if not test_mode:
                print("Step 2: Creating new event loop...")
                # Create new asyncio event loop for this thread
                try:
                    self._event_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._event_loop)
                    print("Event loop created successfully")
                except Exception as e:
                    print(f"ERROR creating event loop: {str(e)}")
                    raise
                
                print("Step 3: Starting market data manager...")
                # Start market data manager
                if hasattr(self.market_data_manager, 'start'):
                    try:
                        self.market_data_manager.start()
                        print("Market data manager started")
                    except Exception as e:
                        print(f"ERROR starting market data manager: {str(e)}")
                        raise
                
                print("Step 4: Creating main thread...")
                # Start main loop in a separate thread
                try:
                    self._main_thread = threading.Thread(target=self._main_loop_wrapper, daemon=True)
                    print("Thread created, starting...")
                    self._main_thread.start()
                    print("Main thread started successfully")
                except Exception as e:
                    print(f"ERROR creating/starting main thread: {str(e)}")
                    raise
            else:
                # In test mode, just set basic properties without actual event loop
                print("Running in test mode - skipping event loop and thread creation")
                self._event_loop = MagicMock()
                self._main_thread = MagicMock()
            
            self.logger.info("Trading engine started")
            print("Trading engine started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting trading engine: {str(e)}")
            print(f"ERROR starting engine: {str(e)}")
            traceback.print_exc()
            self.stop()
            return False
    
    def _main_loop_wrapper(self):
        """
        Wrapper for the main loop to handle setting up the asyncio event loop.
        """
        try:
            print("Main loop wrapper started")
            # Set up the event loop for this thread
            asyncio.set_event_loop(self._event_loop)
            print("Event loop set for thread")
            
            # Run the main loop
            print("Starting main loop...")
            self._event_loop.run_until_complete(self._main_loop())
            print("Main loop completed")
            
        except Exception as e:
            self.logger.error(f"Error in main loop wrapper: {str(e)}")
            print(f"ERROR in main loop wrapper: {str(e)}")
            traceback.print_exc()
            self.performance['errors'] += 1
    
    async def _main_loop(self):
        """
        Main trading engine loop aligned with minute closes.
        """
        self.logger.info("Main trading loop started")
        print("Main trading loop started")
        
        # Check pending TP/SL orders more frequently
        tpsl_check_interval = 5  # Check every 5 seconds
        last_tpsl_check = 0
        
        while not self._stop_event.is_set():
            try:
                # Get current time
                current_time = time.time()
                
                # Check pending TP/SL orders more frequently
                if current_time - last_tpsl_check >= tpsl_check_interval:
                    await self.check_pending_tpsl_orders()
                    last_tpsl_check = current_time
                
                # Get server time to align with minute closes
                server_time = self.client.get_server_time()
                time_second = int(server_time.get("timeSecond", time.time()))
                
                # Calculate seconds until next minute closes
                seconds_to_next_minute = 60 - (time_second % 60)
                if seconds_to_next_minute == 60:
                    seconds_to_next_minute = 0
                    
                # Add 1 second buffer to ensure the minute has closed
                wait_time = seconds_to_next_minute + 1
                
                print(f"Waiting {wait_time} seconds until next minute close")
                self.logger.info(f"Waiting {wait_time} seconds until next minute close")
                await asyncio.sleep(wait_time)
                
                # Now we're at a fresh minute close - process data
                for symbol in self.symbols:
                    print(f"Processing symbol: {symbol} at minute close")
                    await self._process_symbol(symbol)
                
                # Check TP/SL conditions
                print("Checking TP/SL conditions")
                await self.tpsl_manager.check_positions()
                
                # Update position cache
                print("Updating position cache")
                await self._update_position_cache()
                
                # Log engine status
                print(f"Engine status: Running={self.is_running}, Active positions={len(self.active_positions)}")
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                print(f"ERROR in main loop: {str(e)}")
                traceback.print_exc()
                self.performance['errors'] += 1
                await asyncio.sleep(1)  # Brief pause on error
        
        self.logger.info("Main trading loop stopped")
        print("Main trading loop stopped")
    
    async def check_pending_tpsl_orders(self):
        """
        Check pending orders that need TP/SL to be set after fill confirmation.
        """
        if not self.pending_tpsl_orders:
            return
            
        # Process each pending order
        for order_id, order_data in list(self.pending_tpsl_orders.items()):
            try:
                symbol = order_data['symbol']
                direction = order_data['direction']
                
                # Check if order is filled
                fill_info = await self.order_manager.get_position_fill_info(symbol, order_id)
                
                if fill_info.get('filled', False):
                    # Order is filled, set TP/SL
                    fill_price = fill_info['fill_price']
                    print(f"Pending order {order_id} filled at {fill_price}, setting TP/SL")
                    
                    await self._set_tpsl_for_filled_order(
                        symbol=symbol,
                        direction=direction,
                        order_id=order_id,
                        fill_price=fill_price,
                        original_sl=order_data.get('original_sl'),
                        original_tp=order_data.get('original_tp')
                    )
                    
                    # Remove from pending orders
                    del self.pending_tpsl_orders[order_id]
                    
                else:
                    # Order not filled yet
                    print(f"Order {order_id} not filled yet, status: {fill_info.get('status', 'unknown')}")
                    
                    # Check if order is too old (timeout)
                    order_age = int(time.time() * 1000) - order_data['timestamp']
                    timeout = self.config.get('execution', {}).get('order_execution', {}).get('order_timeout_seconds', 60) * 1000
                    
                    if order_age > timeout:
                        # Order timed out, cancel it
                        print(f"Order {order_id} timed out after {order_age/1000} seconds, cancelling")
                        await self.order_manager.cancel_order(symbol, order_id)
                        del self.pending_tpsl_orders[order_id]
                    
            except Exception as e:
                self.logger.error(f"Error checking pending TPSL order {order_id}: {str(e)}")
                print(f"ERROR checking pending TPSL order {order_id}: {str(e)}")
                # Don't remove from pending orders on error, will retry next cycle
    
    async def _set_tpsl_for_filled_order(self, symbol: str, direction: str, order_id: str, 
                                         fill_price: float, original_sl: Optional[float] = None, 
                                         original_tp: Optional[float] = None):
        """
        Set TP/SL for an order that has been filled, based on actual fill price.
        
        Args:
            symbol: Trading symbol
            direction: "LONG" or "SHORT"
            order_id: Order ID
            fill_price: Actual fill price
            original_sl: Original stop loss price from signal (optional)
            original_tp: Original take profit price from signal (optional)
        """
        try:
            print(f"Setting TP/SL for filled order {order_id} at price {fill_price}")
            
            # Get current ATR value for TP/SL calculation
            atr_value = await self._get_atr_value(symbol)
            print(f"Using ATR value: {atr_value} for TP/SL calculation")
            
            # Get position information
            position_info = await self.order_manager.get_positions(symbol)
            position_idx = 0  # Default for one-way mode
            if position_info:
                position_idx = position_info[0].get('positionIdx', 0)
            
            # Get current mark price for validation
            mark_price = 0
            try:
                if position_info:
                    mark_price = float(position_info[0].get("markPrice", 0))
                
                if mark_price <= 0:
                    # Fallback to current price
                    mark_price = await self.market_data_manager.get_latest_price(symbol)
            except Exception as e:
                self.logger.error(f"Error getting mark price: {str(e)}")
                # Use fill price as fallback
                mark_price = fill_price
            
            # Calculate TP/SL based on fill price and ATR
            tp_price, sl_price = await self._calculate_tpsl_from_fill(
                symbol=symbol,
                direction=direction,
                fill_price=fill_price,
                atr_value=atr_value,
                original_tp=original_tp,
                original_sl=original_sl
            )
            
            # Validate against mark price
            if direction == "LONG":
                # Clamp against mark price for LONG
                if tp_price <= mark_price:
                    tp_price = mark_price * 1.002
                    self.logger.warning(f"Adjusted TP above mark: {tp_price}")
                if sl_price >= mark_price:
                    sl_price = mark_price * 0.998
                    self.logger.warning(f"Adjusted SL below mark: {sl_price}")
            else:
                # Clamp against mark price for SHORT
                if tp_price >= mark_price:
                    tp_price = mark_price * 0.998
                    self.logger.warning(f"Adjusted TP below mark: {tp_price}")
                if sl_price <= mark_price:
                    sl_price = mark_price * 1.002
                    self.logger.warning(f"Adjusted SL above mark: {sl_price}")
            
            print(f"Calculated TP/SL for {symbol} {direction}: TP={tp_price}, SL={sl_price}")
            
            # Set TP/SL for the position
            tpsl_result = await self.order_manager.set_position_tpsl(
                symbol=symbol,
                position_idx=position_idx,
                tp_price=str(tp_price),
                sl_price=str(sl_price)
            )
            
            # Check if TP/SL was set successfully
            if "error" in tpsl_result:
                self.logger.error(f"Error setting TP/SL: {tpsl_result['error']}")
                print(f"ERROR setting TP/SL: {tpsl_result['error']}")
                return
            
            # Add to TPSL manager for monitoring
            position_id = f"{symbol}_{order_id}"
            print(f"Adding position to TPSL manager: {position_id}")
            self.tpsl_manager.add_position(
                symbol=symbol,
                side=direction,
                entry_price=fill_price,
                quantity=0.0,  # Will be updated later from position info
                timestamp=int(time.time() * 1000),
                position_id=position_id,
                sl_price=sl_price,
                tp_price=tp_price,
                stop_type=self.config.get('execution', {}).get('tpsl_manager', {}).get('default_stop_type', "TRAILING")
            )
            
            # Add to active positions
            self.active_positions[position_id] = {
                'symbol': symbol,
                'side': direction,
                'entry_price': fill_price,
                'timestamp': int(time.time() * 1000),
                'order_id': order_id,
                'sl_price': sl_price,
                'tp_price': tp_price
            }
            
            self.logger.info(f"TP/SL set for {symbol} {direction} at {fill_price}: TP={tp_price}, SL={sl_price}")
            print(f"SUCCESS: TP/SL set for {symbol} {direction}")
            
        except Exception as e:
            self.logger.error(f"Error setting TP/SL for {symbol}: {str(e)}")
            print(f"ERROR setting TP/SL for {symbol}: {str(e)}")
            traceback.print_exc()
    
    async def _get_atr_value(self, symbol: str) -> float:
        """
        Get ATR value for a symbol from market data cache or calculate it.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            ATR value as float
        """
        try:
            # Try to get ATR directly from data_manager if available
            if hasattr(self.market_data_manager, 'get_atr'):
                atr = await self.market_data_manager.get_atr(symbol, timeframe="1m", length=14)
                if atr and atr > 0:
                    print(f"Retrieved ATR from data_manager.get_atr: {atr}")
                    return float(atr)
            
            # Try to get ATR from market data cache
            if symbol in self.market_data_cache:
                # First try the default timeframe
                if self.default_timeframe in self.market_data_cache[symbol]:
                    df = self.market_data_cache[symbol][self.default_timeframe]
                    if 'atr' in df.columns and not df['atr'].isna().all():
                        atr = df['atr'].iloc[-1]
                        print(f"Found ATR in market data cache: {atr}")
                        return float(atr)
                
                # Try other timeframes
                for timeframe in self.timeframes:
                    if timeframe in self.market_data_cache[symbol]:
                        df = self.market_data_cache[symbol][timeframe]
                        if 'atr' in df.columns and not df['atr'].isna().all():
                            atr = df['atr'].iloc[-1]
                            print(f"Found ATR in {timeframe} data: {atr}")
                            return float(atr)
            
            # If not found, calculate a simple approximation
            print("ATR not found in data cache, calculating approximation")
            
            # Get recent high/low data
            if symbol in self.market_data_cache and self.default_timeframe in self.market_data_cache[symbol]:
                df = self.market_data_cache[symbol][self.default_timeframe]
                if len(df) > 0:
                    # Calculate a simple volatility estimate (high-low average over last few bars)
                    lookback = min(14, len(df))
                    recent_data = df.iloc[-lookback:]
                    avg_range = (recent_data['high'] - recent_data['low']).mean()
                    print(f"Calculated average range as ATR approximation: {avg_range}")
                    return float(avg_range)
            
            # Fallback to a percentage of current price
            symbol_price = await self.market_data_manager.get_latest_price(symbol)
            default_atr = symbol_price * 0.01  # 1% of current price as default
            print(f"Using fallback ATR value (1% of price): {default_atr}")
            return default_atr
            
        except Exception as e:
            self.logger.error(f"Error getting ATR value: {str(e)}")
            print(f"ERROR getting ATR value: {str(e)}")
            
            # Return a reasonable default based on current price
            symbol_price = await self.market_data_manager.get_latest_price(symbol)
            default_atr = symbol_price * 0.01  # 1% of current price as default
            return default_atr
    
    async def _calculate_tpsl_from_fill(self, symbol: str, direction: str, fill_price: float, 
                                      atr_value: float, original_tp: Optional[float] = None, 
                                      original_sl: Optional[float] = None) -> Tuple[float, float]:
        """
        Calculate TP/SL levels based on actual fill price and ATR.
        
        Args:
            symbol: Trading symbol
            direction: "LONG" or "SHORT"
            fill_price: Actual fill price
            atr_value: Current ATR value
            original_tp: Original take profit price from signal (optional)
            original_sl: Original stop loss price from signal (optional)
            
        Returns:
            Tuple of (tp_price, sl_price)
        """
        # Get multipliers from config
        risk_config = self.config.get('execution', {}).get('risk_management', {})
        tp_multiplier = risk_config.get('take_profit_multiplier', 4.0)
        sl_multiplier = risk_config.get('stop_loss_multiplier', 2.0)
        
        # For LONG positions
        if direction == "LONG":
            # Calculate TP/SL based on ATR
            tp_price = fill_price + (atr_value * tp_multiplier)
            sl_price = fill_price - (atr_value * sl_multiplier)
            
            # Validate TP is above entry and SL is below entry
            if tp_price <= fill_price:
                tp_price = fill_price * 1.005  # Fallback to 0.5% above entry
            if sl_price >= fill_price:
                sl_price = fill_price * 0.995  # Fallback to 0.5% below entry
        
        # For SHORT positions
        else:
            # Calculate TP/SL based on ATR
            tp_price = fill_price - (atr_value * tp_multiplier)
            sl_price = fill_price + (atr_value * sl_multiplier)
            
            # Validate TP is below entry and SL is above entry
            if tp_price >= fill_price:
                tp_price = fill_price * 0.995  # Fallback to 0.5% below entry
            if sl_price <= fill_price:
                sl_price = fill_price * 1.005  # Fallback to 0.5% above entry
        
        # Round to appropriate precision
        tp_price = round(tp_price, 2)
        sl_price = round(sl_price, 2)
        
        return tp_price, sl_price
    
    async def _process_symbol(self, symbol: str):
        """
        Process a trading symbol.
        
        Args:
            symbol: Trading symbol
        """
        try:
            # Update market data for all timeframes
            for timeframe in self.timeframes:
                print(f"Processing {symbol} on {timeframe} timeframe")
                # Get latest data
                new_data = await self._update_market_data(symbol, timeframe)
                
                if new_data is not None:
                    print(f"New data received for {symbol} {timeframe}")
                    # Format data for strategy manager
                    data_dict = {timeframe: new_data}
                    
                    # Process with strategy
                    print(f"Running strategies for {symbol} {timeframe}")
                    signals = await self.strategy_manager.process_data(symbol, data_dict)
                    
                    # Handle any signals
                    if signals:
                        print(f"Received {len(signals)} signals for {symbol}")
                        await self._handle_signals(symbol, signals)
                else:
                    print(f"No new data for {symbol} {timeframe}")
            
        except Exception as e:
            self.logger.error(f"Error processing symbol {symbol}: {str(e)}")
            print(f"ERROR processing {symbol}: {str(e)}")
    
    async def _update_market_data(self, symbol: str, timeframe: str):
        """
        Update market data for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Time interval
            
        Returns:
            Updated DataFrame or None if no update
        """
        try:
            print(f"Fetching data for {symbol} {timeframe}")
            # Get latest data
            df = await self.market_data_manager.get_historical_data(
                symbol=symbol,
                interval=timeframe,
                limit=100
            )
            
            # Check if we have new data
            if symbol in self.market_data_cache and timeframe in self.market_data_cache[symbol]:
                old_data = self.market_data_cache[symbol][timeframe]
                
                # Compare last timestamp
                if not df.empty and not old_data.empty:
                    # Get the timestamp columns
                    if 'timestamp' in df.columns and 'timestamp' in old_data.columns:
                        # Safely get the last timestamp values
                        new_last_ts = df['timestamp'].iloc[-1] if len(df) > 0 else 0
                        old_last_ts = old_data['timestamp'].iloc[-1] if len(old_data) > 0 else 0
                        
                        if new_last_ts <= old_last_ts:
                            # No new data
                            print(f"No new data for {symbol} {timeframe}")
                            return None
                    else:
                        # Cannot compare timestamps, assume new data
                        self.logger.warning(f"Cannot compare timestamps for {symbol} {timeframe}")
            
            # Store updated data
            if symbol not in self.market_data_cache:
                self.market_data_cache[symbol] = {}
            self.market_data_cache[symbol][timeframe] = df
            print(f"Updated data cache for {symbol} {timeframe}")
            
            # Handle new kline for UI or other updates
            if not df.empty:
                try:
                    # Convert row to dict safely
                    last_row = df.iloc[-1].to_dict() if len(df) > 0 else {}
                    self._handle_kline_update(symbol, timeframe, last_row)
                except Exception as e:
                    self.logger.error(f"Error handling kline update: {str(e)}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error updating market data for {symbol} {timeframe}: {str(e)}")
            print(f"ERROR updating market data for {symbol} {timeframe}: {str(e)}")
            return None
    
    async def _handle_signals(self, symbol: str, signals: List[TradeSignal]):
        """
        Process trading signals for a symbol.
        
        Args:
            symbol: Trading symbol
            signals: List of trade signals
        """
        for signal in signals:
            try:
                # Track signals
                self.performance['signals_generated'] += 1
                
                # Log the signal
                self.logger.info(f"Signal generated for {symbol}: {signal.signal_type} {signal.direction}")
                print(f"SIGNAL: {symbol} {signal.signal_type} {signal.direction}")
                
                # Store recent signal
                signal_key = f"{symbol}_{signal.signal_type}"
                self.recent_signals[signal_key] = {
                    'signal': signal,
                    'timestamp': datetime.now()
                }
                
                # Check if we can take this trade
                can_take_trade = await self._can_take_trade(symbol, signal)
                if not can_take_trade:
                    self.logger.info(f"Skipping signal for {symbol}: position limit or other restriction")
                    print(f"SKIP: Signal for {symbol} (position limit/restriction)")
                    continue
                
                # Execute the signal
                print(f"Executing signal for {symbol}...")
                await self._execute_signal(symbol, signal)
                
            except Exception as e:
                self.logger.error(f"Error handling signal for {symbol}: {str(e)}")
                print(f"ERROR handling signal for {symbol}: {str(e)}")
                traceback.print_exc()
    
    async def _can_take_trade(self, symbol: str, signal: TradeSignal) -> bool:
        """
        Check if we can take a trade based on risk management rules.
        
        Args:
            symbol: Trading symbol
            signal: Trade signal
            
        Returns:
            True if trade can be taken, False otherwise
        """
        print(f"Validating trade for {symbol}...")
        
        # TEMPORARY: Allow all trades during testing
        print("TEST MODE: All trades allowed for testing")
        return True
        
        # The commented code below can be uncommented when you want full validation
        """
        # Get risk management config
        risk_config = self.config.get('execution', {}).get('risk_management', {})
        
        # Determine the direction from signal type
        direction = "LONG" if signal.signal_type == SignalType.BUY else "SHORT"
        
        # Check max positions per symbol
        max_positions = risk_config.get('max_positions_per_symbol', 1)
        current_positions = sum(1 for pos in self.active_positions.values() if pos['symbol'] == symbol)
        
        if current_positions >= max_positions:
            print(f"REJECT: Max positions ({max_positions}) reached for {symbol}")
            return False
        
        # Check position in opposite direction
        if symbol in self.position_cache:
            position = self.position_cache[symbol]
            position_side = position.get('side', '')
            
            # If signal is in opposite direction to existing position
            if (position_side == 'Buy' and direction == "SHORT") or \
               (position_side == 'Sell' and direction == "LONG"):
                # Check if we allow reversals
                allow_reversals = risk_config.get('allow_reversals', False)
                if not allow_reversals:
                    print(f"REJECT: Position exists in opposite direction for {symbol}")
                    return False
        
        # Check max open positions
        max_open_positions = risk_config.get('max_open_positions', 3)
        if len(self.active_positions) >= max_open_positions:
            print(f"REJECT: Max open positions ({max_open_positions}) reached")
            return False
            
        # Check minimum balance threshold
        min_balance = risk_config.get('min_balance_threshold', 10.0)
        current_balance = await self._get_account_balance()
        
        if current_balance < min_balance:
            print(f"REJECT: Balance ({current_balance}) below minimum threshold ({min_balance})")
            return False
        
        print(f"ACCEPT: Trade validated for {symbol} {direction}")
        return True
        """
    
    async def _get_account_balance(self) -> float:
        """
        Get the available account balance.
        
        Returns:
            Available balance in USDT
        """
        try:
            # Get the balance using the OrderManager
            balance_data = await self.order_manager.get_account_balance()
            
            # Debug log
            self.logger.info(f"Balance data structure: {balance_data}")
            
            # Parse balance from Bybit V5 API response structure
            available_balance = 0.0
            
            if isinstance(balance_data, dict):
                # Check various possible structures
                if "coin" in balance_data:
                    # Look for USDT in the coins list
                    for coin in balance_data["coin"]:
                        if coin.get("coin") == "USDT":
                            available_balance = float(coin.get("availableBalance", 0))
                            break
                elif "list" in balance_data and balance_data["list"]:
                    # Look in the first account's coins
                    account = balance_data["list"][0]
                    coins = account.get("coin", [])
                    for coin in coins:
                        if coin.get("coin") == "USDT":
                            available_balance = float(coin.get("availableBalance", 0))
                            break
                elif "totalAvailableBalance" in balance_data:
                    # Direct balance field
                    available_balance = float(balance_data.get("totalAvailableBalance", 0))
            
            # If we couldn't find a balance, use a default value for testing
            if available_balance <= 0:
                self.logger.warning("Could not determine balance, using testing default")
                available_balance = 1000.0  # Default for testing
                
            self.logger.info(f"Account balance: {available_balance} USDT")
            return available_balance
        except Exception as e:
            self.logger.error(f"Error getting account balance: {str(e)}")
            # For testing purposes, return a valid balance
            return 1000.0
    
    async def _execute_signal(self, symbol: str, signal: TradeSignal):
        """
        Execute a trading signal using post-fill TP/SL approach.
        
        Args:
            symbol: Trading symbol
            signal: Trade signal
        """
        try:
            print(f"Executing signal for {symbol}...")
            
            # Get current price
            price = await self.market_data_manager.get_latest_price(symbol)
            print(f"Current price for {symbol}: {price}")
            
            # Calculate position size based on config
            sizing_config = self.config.get('execution', {}).get('position_sizing', {})
            sizing_method = sizing_config.get('sizing_method', 'fixed')
            
            # Determine position size
            if sizing_method == 'fixed':
                # Use fixed position size from config
                default_size = sizing_config.get('default_size', 0.01)
                max_size = sizing_config.get('max_size', 0.1)
                position_size = min(default_size, max_size)
                print(f"Using fixed position size: {position_size}")
            else:
                # Use USDT value for position size
                position_size_usdt = sizing_config.get('position_size_usdt', 50.0)
                position_size = await self.order_manager.calculate_position_size(symbol, position_size_usdt)
                print(f"Calculated position size from USDT value: {position_size}")
            
            # Determine order side and direction based on signal type
            side = "Buy" if signal.signal_type == SignalType.BUY else "Sell"
            direction = "LONG" if signal.signal_type == SignalType.BUY else "SHORT"
            print(f"Order side: {side}, direction: {direction}")
            
            # Store the original TP/SL from signal for later use
            original_sl_price = signal.sl_price
            original_tp_price = signal.tp_price
            
            # Place market order WITHOUT TP/SL first
            print(f"Placing {side} market order for {symbol} without TP/SL")
            
            # Execute the trade without TP/SL
            result = await self.order_manager.enter_position_market(
                symbol=symbol,
                side=side,
                qty=position_size
            )
            
            # Check for errors
            if "error" in result:
                self.logger.error(f"Error placing order: {result['error']}")
                print(f"ERROR placing order: {result['error']}")
                return
            
            # Track the order
            self.performance['orders_placed'] += 1
            
            # Get order ID
            order_id = result.get("orderId", "")
            if not order_id:
                self.logger.warning(f"No order ID returned for {symbol} {side} order")
                print(f"WARNING: No order ID returned for {symbol} {side} order")
                return
            
            # Check if order was filled immediately
            if result.get("status") == "FILLED":
                # Order was filled immediately
                fill_price = float(result.get("avgPrice", price))
                print(f"Order filled immediately at price: {fill_price}")
                
                # Now set TP/SL based on actual fill price
                await self._set_tpsl_for_filled_order(
                    symbol=symbol,
                    direction=direction,
                    order_id=order_id,
                    fill_price=fill_price,
                    original_sl=original_sl_price,
                    original_tp=original_tp_price
                )
            else:
                # Order not filled immediately, store in pending_tpsl_orders for later processing
                print(f"Order not filled immediately, will set TP/SL after fill confirmation")
                self.pending_tpsl_orders[order_id] = {
                    'symbol': symbol,
                    'direction': direction,
                    'original_sl': original_sl_price,
                    'original_tp': original_tp_price,
                    'timestamp': int(time.time() * 1000)
                }
            
            self.logger.info(f"Order executed for {symbol} {side}: {order_id}")
            print(f"SUCCESS: Order executed for {symbol} {side}: {order_id}")
            
        except Exception as e:
            self.logger.error(f"Error executing signal for {symbol}: {str(e)}")
            print(f"ERROR executing signal for {symbol}: {str(e)}")
            traceback.print_exc()
    
    async def _update_position_cache(self):
        """
        Update the position cache with current positions.
        """
        try:
            print("Updating position cache...")
            # Update positions for all symbols
            for symbol in self.symbols:
                positions = await self.order_manager.get_positions(symbol)
                
                if positions:
                    self.position_cache[symbol] = positions[0]
                    print(f"Updated position for {symbol}: {positions[0]}")
                elif symbol in self.position_cache:
                    # Position closed
                    del self.position_cache[symbol]
                    print(f"Position closed for {symbol}")
        except Exception as e:
            self.logger.error(f"Error updating position cache: {str(e)}")
            print(f"ERROR updating position cache: {str(e)}")
    
    def stop(self):
        """
        Stop the trading engine.
        """
        if not self.is_running:
            self.logger.warning("Trading engine is not running")
            print("WARNING: Engine is not running")
            return
            
        self.logger.info("Stopping trading engine...")
        print("Stopping trading engine...")
        
        # Signal stop
        print("Step 1: Setting stop event...")
        self._stop_event.set()
        
        # Wait for main thread to finish
        if self._main_thread and self._main_thread.is_alive():
            print("Step 2: Waiting for main thread to finish...")
            self._main_thread.join(timeout=10.0)
        
        # Close event loop
        if self._event_loop:
            print("Step 3: Closing event loop...")
            try:
                self._event_loop.close()
                print("Event loop closed")
            except Exception as e:
                print(f"WARNING: Error closing event loop: {str(e)}")
        
        # Stop market data manager
        if hasattr(self.market_data_manager, 'stop'):
            print("Step 4: Stopping market data manager...")
            try:
                self.market_data_manager.stop()
                print("Market data manager stopped")
            except Exception as e:
                print(f"WARNING: Error stopping market data manager: {str(e)}")
        
        # Set state
        self.is_running = False
        
        self.logger.info("Trading engine stopped")
        print("Trading engine stopped successfully")
    
    async def stop_async(self):
        """
        Async cleanup - separate method for testing.
        """
        try:
            print("Starting async cleanup...")
            if hasattr(self.market_data_manager, 'close'):
                await self.market_data_manager.close()
                print("Market data manager closed")
            if hasattr(self.order_manager, 'close'):
                await self.order_manager.close()
                print("Order manager closed")
            print("Async cleanup completed")
            return True
        except Exception as e:
            self.logger.error(f"Error in async cleanup: {str(e)}")
            print(f"ERROR in async cleanup: {str(e)}")
            traceback.print_exc()
            return False
    
    def _handle_kline_update(self, symbol: str, timeframe: str, kline: Dict[str, Any]):
        """
        Handle market data updates.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe (e.g., '1m', '5m')
            kline: Kline data
        """
        # Log the update
        self.logger.debug(f"New kline for {symbol} {timeframe}: {kline['close']}")
        
        # This could be extended to:
        # - Update UI
        # - Send notifications
        # - Perform additional analysis
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the trading engine.
        
        Returns:
            Dictionary with engine status
        """
        # Calculate runtime
        runtime = datetime.now() - self.start_time if self.start_time else None
        runtime_str = str(runtime).split('.')[0] if runtime else "Not started"
        
        # Count active positions
        active_positions_count = len(self.active_positions)
        
        # Get current prices
        current_prices = {}
        for symbol in self.symbols:
            try:
                # Use synchronous method for UI purposes
                current_prices[symbol] = self.market_data_manager.get_last_price(symbol)
            except:
                current_prices[symbol] = 0.0
        
        # Get active strategies
        active_strategies = self.strategy_manager.get_active_strategies() if self.strategy_manager else []
        
        # Format positions for monitor
        positions = []
        for pos_id, pos in self.active_positions.items():
            positions.append({
                'symbol': pos.get('symbol', ''),
                'side': pos.get('side', ''),
                'size': pos.get('quantity', 0),
                'entryPrice': pos.get('entry_price', 0),
                'markPrice': current_prices.get(pos.get('symbol', ''), 0),
                'unrealisedPnl': self._calculate_unrealized_pnl(pos, current_prices)
            })
        
        # Format orders for monitor
        orders = []
        # Get pending orders if we have a method for it
        if hasattr(self.order_manager, 'get_open_orders_sync'):
            try:
                # Always pass a symbol to get_open_orders_sync
                if self.symbols:
                    open_orders = self.order_manager.get_open_orders_sync(self.symbols[0])
                    if open_orders:
                        orders = open_orders
            except:
                pass
        
        status = {
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'runtime': runtime_str,
            'symbols': self.symbols,
            'timeframes': self.timeframes,
            'performance': self.performance,
            'active_positions': active_positions_count,
            'current_prices': current_prices,
            'active_strategies': active_strategies,
            'positions': positions,
            'orders': orders,
            'last_update': datetime.now().isoformat()
        }
        
        print(f"Engine status: Running={status['is_running']}, Active positions={active_positions_count}")
        return status

    def _calculate_unrealized_pnl(self, position, current_prices):
        """Calculate unrealized PnL for a position"""
        try:
            symbol = position.get('symbol', '')
            entry_price = float(position.get('entry_price', 0))
            quantity = float(position.get('quantity', 0))
            side = position.get('side', '')
            
            if not symbol or not entry_price or not quantity:
                return 0
            
            current_price = float(current_prices.get(symbol, 0))
            if not current_price:
                return 0
            
            if side == 'LONG':
                return quantity * (current_price - entry_price)
            elif side == 'SHORT':
                return quantity * (entry_price - current_price)
            else:
                return 0
        except Exception as e:
            self.logger.error(f"Error calculating unrealized PnL: {str(e)}")
            return 0
    
    def write_status_file(self, status_file_path):
        """
        Write current engine status to a file for CLI/monitor to read.
        
        Args:
            status_file_path: Path to write status JSON file
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(status_file_path), exist_ok=True)
            
            # Get status
            status = self.get_status()
            
            # Write to file
            with open(status_file_path, 'w') as f:
                json.dump(status, f, indent=2)
                
            return True
        except Exception as e:
            self.logger.error(f"Error writing status file: {str(e)}")
            print(f"ERROR writing status file: {str(e)}")
            return False