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
from typing import Dict, List, Any, Optional, Set
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
            self.order_manager = OrderManager(self.client, self.config['execution'], logger=self.logger)
            
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
        Main trading engine loop.
        """
        self.logger.info("Main trading loop started")
        print("Main trading loop started")
        
        # Check interval (in seconds)
        data_update_interval = self.config.get('general', {}).get('system', {}).get('data_update_interval', 60)
        print(f"Update interval: {data_update_interval} seconds")
        
        while not self._stop_event.is_set():
            try:
                # Process each symbol
                for symbol in self.symbols:
                    print(f"Processing symbol: {symbol}")
                    await self._process_symbol(symbol)
                
                # Check TP/SL conditions
                print("Checking TP/SL conditions")
                await self.tpsl_manager.check_positions()
                
                # Update position cache
                print("Updating position cache")
                await self._update_position_cache()
                
                # Wait for next check
                print(f"Waiting {data_update_interval} seconds until next update")
                await asyncio.sleep(data_update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                print(f"ERROR in main loop: {str(e)}")
                traceback.print_exc()
                self.performance['errors'] += 1
                await asyncio.sleep(1)  # Brief pause on error
        
        self.logger.info("Main trading loop stopped")
        print("Main trading loop stopped")
    
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
                    if old_data.iloc[-1]['timestamp'] >= df.iloc[-1]['timestamp']:
                        # No new data
                        print(f"No new data for {symbol} {timeframe}")
                        return None
            
            # Store updated data
            self.market_data_cache[symbol][timeframe] = df
            print(f"Updated data cache for {symbol} {timeframe}")
            
            # Handle new kline for UI or other updates
            if not df.empty:
                self._handle_kline_update(symbol, timeframe, df.iloc[-1].to_dict())
            
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
                if not self._can_take_trade(symbol, signal):
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
    
    def _can_take_trade(self, symbol: str, signal: TradeSignal) -> bool:
        """
        Check if we can take a trade based on risk management rules.
        
        Args:
            symbol: Trading symbol
            signal: Trade signal
            
        Returns:
            True if trade can be taken, False otherwise
        """
        print(f"Validating trade for {symbol}...")
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
        min_balance = risk_config.get('min_balance_threshold', 100.0)
        current_balance = self._get_account_balance()
        if current_balance < min_balance:
            print(f"REJECT: Balance ({current_balance}) below minimum threshold ({min_balance})")
            return False
        
        print(f"ACCEPT: Trade validated for {symbol} {direction}")
        return True
    
    async def _execute_signal(self, symbol: str, signal: TradeSignal):
        """
        Execute a trading signal.
        
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
            
            # Get stop loss and take profit from signal or calculate
            sl_price = signal.sl_price
            tp_price = signal.tp_price
            
            # If signal doesn't have TP/SL, calculate from config
            if not sl_price or not tp_price:
                risk_config = self.config.get('execution', {}).get('risk_management', {})
                sl_pct = risk_config.get('stop_loss_pct', 0.02)
                tp_pct = risk_config.get('take_profit_pct', 0.04)
                
                if not sl_price:
                    sl_price = price * (1 - sl_pct) if side == "Buy" else price * (1 + sl_pct)
                    print(f"Calculated SL price: {sl_price}")
                
                if not tp_price:
                    tp_price = price * (1 + tp_pct) if side == "Buy" else price * (1 - tp_pct)
                    print(f"Calculated TP price: {tp_price}")
            
            print(f"Placing {side} order for {symbol} at {price}, SL: {sl_price}, TP: {tp_price}")
            # Execute the trade with TP/SL
            if side == "Buy":
                result = await self.order_manager.enter_long_with_tp_sl(
                    symbol=symbol,
                    qty=position_size,
                    tp_price=str(tp_price),
                    sl_price=str(sl_price)
                )
            else:
                result = await self.order_manager.enter_short_with_tp_sl(
                    symbol=symbol,
                    qty=position_size,
                    tp_price=str(tp_price),
                    sl_price=str(sl_price)
                )
            
            # Check for errors
            if "error" in result.get("entry_order", {}):
                self.logger.error(f"Error placing order: {result['entry_order']['error']}")
                print(f"ERROR placing order: {result['entry_order']['error']}")
                return
            
            # Track the order
            self.performance['orders_placed'] += 1
            
            # Get order ID
            order_id = result["entry_order"].get("orderId", "")
            if not order_id:
                self.logger.warning(f"No order ID returned for {symbol} {side} order")
                print(f"WARNING: No order ID returned for {symbol} {side} order")
                return
            
            # Add to TPSL manager
            position_id = f"{symbol}_{order_id}"
            print(f"Adding position to TPSL manager: {position_id}")
            self.tpsl_manager.add_position(
                symbol=symbol,
                side=direction,
                entry_price=price,
                quantity=float(position_size),
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
                'entry_price': price,
                'quantity': float(position_size),
                'timestamp': int(time.time() * 1000),
                'order_id': order_id,
                'sl_price': sl_price,
                'tp_price': tp_price
            }
            
            self.logger.info(f"Order executed for {symbol} {side}: {order_id}")
            print(f"SUCCESS: Order executed for {symbol} {side}: {order_id}")
            
        except Exception as e:
            self.logger.error(f"Error executing signal for {symbol}: {str(e)}")
            print(f"ERROR executing signal for {symbol}: {str(e)}")
            traceback.print_exc()
    
    def _get_account_balance(self) -> float:
        """
        Get the available account balance.
        
        Returns:
            Available balance in USDT
        """
        try:
            balance_data = self.order_manager.get_account_balance()
            available_balance = float(balance_data.get("totalAvailableBalance", "0"))
            print(f"Account balance: {available_balance} USDT")
            return available_balance
        except Exception as e:
            self.logger.error(f"Error getting account balance: {str(e)}")
            print(f"ERROR getting account balance: {str(e)}")
            return 0.0
    
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
                open_orders = self.order_manager.get_open_orders_sync()
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