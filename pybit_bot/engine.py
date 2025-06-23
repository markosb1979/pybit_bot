"""
Trading Engine - Main trading loop and execution flow.

This module connects all components of the trading system:
- Market data handling
- Strategy execution
- Order management
- Risk management
- TP/SL execution
"""

import os
import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dotenv import load_dotenv

from .core.client import BybitClientTransport, APICredentials
from .utils.credentials import load_credentials
from .core.order_manager_client import OrderManagerClient

from .managers.data_manager import DataManager
from .managers.order_manager import OrderManager
from .managers.strategy_manager import StrategyManager
from .managers.tpsl_manager import TPSLManager

from .utils.logger import Logger
from .utils.config_loader import ConfigLoader
from .strategies.base_strategy import SignalType, TradeSignal


class TradingEngine:
    """
    Main trading engine handling the trading loop and execution flow.
    
    Connects all components of the trading system and maintains state.
    """
    
    def __init__(self, config_dir: str):
        """
        Initialize the trading engine with configuration directory.
        
        Args:
            config_dir: Path to the configuration directory
        """
        # Set up logging first
        self.logger = Logger("TradingEngine")
        self.logger.debug(f"→ __init__(config_dir={config_dir})")
        self.logger.info("Initializing Trading Engine...")
        
        # Load environment variables
        load_dotenv()
        
        # Load configurations using the centralized loader
        # Make sure we're passing a directory, not a file
        if config_dir and (os.path.isfile(config_dir) or config_dir.endswith('.json')):
            config_dir = os.path.dirname(config_dir)
            self.logger.info(f"Config path appears to be a file, using directory instead: {config_dir}")
        
        # Use our fixed ConfigLoader with the correct directory path
        config_loader = ConfigLoader(config_dir, logger=self.logger)
        self.config = config_loader.load_configs()
        
        # Load API credentials
        try:
            self.credentials = load_credentials(logger=self.logger)
            self.logger.info("API credentials loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load API credentials: {str(e)}")
            raise RuntimeError(f"Failed to load API credentials: {str(e)}")
        
        # Set up logging directory
        log_dir = self.config.get('general', {}).get('system', {}).get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Engine state
        self.is_running = False
        self.start_time = None
        
        # Get configuration values directly from loaded config
        trading_config = self.config.get('general', {}).get('trading', {})
        self.symbols = trading_config.get('symbols', [])
        self.timeframes = trading_config.get('timeframes', [])
        self.default_timeframe = trading_config.get('default_timeframe', "")
        
        # Log loaded configuration
        self.logger.debug(f"Loaded symbols: {self.symbols}")
        self.logger.debug(f"Loaded timeframes: {self.timeframes}")
        self.logger.debug(f"Loaded default timeframe: {self.default_timeframe}")
        
        self._stop_event = threading.Event()
        self._main_thread = None
        self._event_loop = None
        
        # Initialize clients and managers to None initially
        self.client = None
        self.order_client = None
        self.market_data_manager = None
        self.order_manager = None
        self.strategy_manager = None
        self.tpsl_manager = None
        
        # Active positions and signals
        self.active_positions = {}
        self.recent_signals = {}
        self.pending_tpsl_orders = {}
        
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
        self.logger.debug(f"← __init__ completed")
    
    def initialize(self) -> bool:
        """
        Initialize all components and connections
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.debug(f"→ initialize()")
        
        try:
            # Initialize Bybit client with credentials
            self.logger.info("Initializing Bybit client")
            
            # Check if we have valid credentials
            if not self.credentials:
                self.logger.error("No valid API credentials found")
                return False
                
            # Create client instance
            self.client = BybitClientTransport(
                self.credentials.api_key,
                self.credentials.api_secret,
                self.credentials.testnet
            )
            
            # Set up OrderManagerClient
            self.order_client = OrderManagerClient(self.client, logger=self.logger)
            
            # Initialize market data manager
            self.logger.info("Initializing market data manager")
            self.market_data_manager = DataManager(
                self.client, 
                self.config, 
                logger=self.logger
            )
            
            # Initialize order manager
            self.logger.info("Initializing order manager")
            self.order_manager = OrderManager(
                self.client,
                self.config,
                logger=self.logger
            )
            
            # Initialize strategy manager
            self.logger.info("Initializing strategy manager")
            self.strategy_manager = StrategyManager(
                self.market_data_manager,
                self.config,
                logger=self.logger
            )
            
            # Initialize TP/SL manager
            self.logger.info("Initializing TP/SL manager")
            self.tpsl_manager = TPSLManager(
                self.order_manager,
                self.config,
                logger=self.logger
            )
            
            # Initialize data subscriptions
            for symbol in self.symbols:
                self.logger.info(f"Setting up data for {symbol}")
                for timeframe in self.timeframes:
                    self.market_data_manager.subscribe_klines(symbol, timeframe)
                    
            # Warm up indicators and load initial data
            self.logger.info("Loading initial market data")
            asyncio.run(self.market_data_manager.load_initial_data())
            
            self.logger.debug(f"← initialize returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}")
            self.logger.debug(f"← initialize returned False (error)")
            return False
    
    def start(self) -> bool:
        """
        Start the trading engine
        
        Returns:
            True if engine was started successfully, False otherwise
        """
        self.logger.debug(f"→ start()")
        
        if self.is_running:
            self.logger.warning("Engine is already running")
            self.logger.debug(f"← start returned False (already running)")
            return False
            
        try:
            # Create event loop
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            
            # Start the main thread
            self._stop_event.clear()
            self._main_thread = threading.Thread(
                target=self._run_main_loop,
                daemon=True
            )
            self._main_thread.start()
            
            self.is_running = True
            self.start_time = datetime.now()
            
            self.logger.info(f"Trading engine started at {self.start_time}")
            self.logger.debug(f"← start returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting engine: {str(e)}")
            self.logger.debug(f"← start returned False (error)")
            return False
    
    def stop(self) -> bool:
        """
        Stop the trading engine
        
        Returns:
            True if engine was stopped successfully, False otherwise
        """
        self.logger.debug(f"→ stop()")
        
        if not self.is_running:
            self.logger.warning("Engine is not running")
            self.logger.debug(f"← stop returned False (not running)")
            return False
            
        try:
            # Signal the main loop to stop
            self._stop_event.set()
            
            # Wait for the main thread to finish
            if self._main_thread and self._main_thread.is_alive():
                self._main_thread.join(timeout=10)
                
            # Close the event loop
            if self._event_loop and self._event_loop.is_running():
                self._event_loop.stop()
                
            # Set state
            self.is_running = False
            
            # Log runtime
            runtime = datetime.now() - self.start_time if self.start_time else timedelta(0)
            self.logger.info(f"Trading engine stopped. Total runtime: {runtime}")
            
            # Close client connections
            if self.client:
                asyncio.run(self.client.close())
                
            self.logger.debug(f"← stop returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping engine: {str(e)}")
            self.logger.debug(f"← stop returned False (error)")
            return False
    
    def _run_main_loop(self) -> None:
        """
        Main trading loop
        """
        self.logger.debug(f"→ _run_main_loop()")
        
        try:
            # Set up the asyncio event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Start the main async loop
            loop.run_until_complete(self._main_loop())
            
        except Exception as e:
            self.logger.error(f"Error in main loop: {str(e)}")
            
        finally:
            self.logger.debug(f"← _run_main_loop completed")
    
    async def _main_loop(self) -> None:
        """
        Main async trading loop
        """
        self.logger.debug(f"→ _main_loop()")
        
        try:
            # Initial update of market data
            await self.market_data_manager.update_market_data()
            
            # Main trading loop
            while not self._stop_event.is_set():
                # Process market data updates
                await self.market_data_manager.update_market_data()
                
                # Check for signals
                await self._check_for_signals()
                
                # Process pending signals
                await self._process_signals()
                
                # Update position tracking
                await self._update_positions()
                
                # Update TP/SL orders
                await self.tpsl_manager.update()
                
                # Sleep to avoid excessive CPU usage
                await asyncio.sleep(0.1)
                
            self.logger.info("Main loop stopped")
            
        except Exception as e:
            self.logger.error(f"Error in main async loop: {str(e)}")
            
        finally:
            self.logger.debug(f"← _main_loop completed")
    
    async def _check_for_signals(self) -> None:
        """
        Check for trading signals from strategies
        """
        self.logger.debug(f"→ _check_for_signals()")
        
        try:
            # Get current market data
            for symbol in self.symbols:
                # Get the latest data for the default timeframe
                market_data = self.market_data_manager.get_klines(
                    symbol, 
                    self.default_timeframe
                )
                
                if not market_data or len(market_data) < 10:
                    self.logger.warning(f"Insufficient data for {symbol}, skipping signal check")
                    continue
                
                # Run strategy evaluation
                signals = await self.strategy_manager.evaluate(symbol, market_data)
                
                # Process signals
                for signal in signals:
                    self._add_signal(signal)
                    
        except Exception as e:
            self.logger.error(f"Error checking for signals: {str(e)}")
            
        finally:
            self.logger.debug(f"← _check_for_signals completed")
    
    def _add_signal(self, signal: TradeSignal) -> None:
        """
        Add a new signal to the processing queue
        
        Args:
            signal: TradeSignal object
        """
        self.logger.debug(f"→ _add_signal(signal={signal})")
        
        symbol = signal.symbol if hasattr(signal, 'symbol') else self.symbol
        
        # Create symbol entry if it doesn't exist
        if symbol not in self.recent_signals:
            self.recent_signals[symbol] = []
            
        # Add the signal
        self.recent_signals[symbol].append(signal)
        
        # Update performance tracking
        self.performance['signals_generated'] += 1
        
        self.logger.info(f"New {signal.signal_type.name} signal for {symbol} at {signal.price}")
        self.logger.debug(f"← _add_signal completed")
    
    async def _process_signals(self) -> None:
        """
        Process pending signals and execute trades
        """
        self.logger.debug(f"→ _process_signals()")
        
        try:
            for symbol, signals in list(self.recent_signals.items()):
                if not signals:
                    continue
                    
                # Process each signal
                for signal in signals:
                    # Check if signal is still valid
                    if await self._validate_signal(signal):
                        # Execute the signal
                        await self._execute_signal(signal)
                        
                # Clear processed signals
                self.recent_signals[symbol] = []
                
        except Exception as e:
            self.logger.error(f"Error processing signals: {str(e)}")
            
        finally:
            self.logger.debug(f"← _process_signals completed")
    
    async def _validate_signal(self, signal: TradeSignal) -> bool:
        """
        Validate if a signal is still valid to execute
        
        Args:
            signal: TradeSignal object
            
        Returns:
            True if signal is valid, False otherwise
        """
        self.logger.debug(f"→ _validate_signal(signal={signal})")
        
        try:
            # Get symbol from signal
            symbol = signal.symbol if hasattr(signal, 'symbol') else self.symbol
            
            # Check if signal is expired (if it has timestamp and expiry)
            if hasattr(signal, 'timestamp') and hasattr(signal, 'metadata') and 'expiry' in signal.metadata:
                expiry = signal.metadata['expiry']
                current_time = int(datetime.now().timestamp() * 1000)
                if current_time > expiry:
                    self.logger.info(f"Signal expired for {symbol}")
                    self.logger.debug(f"← _validate_signal returned False (expired)")
                    return False
                
            # Check current positions
            positions = await self.order_manager.get_positions(symbol)
            
            # If we have an existing position
            if positions and float(positions[0].get("size", "0")) != 0:
                position = positions[0]
                position_side = position.get("side")
                
                # Check if signal conflicts with current position
                if signal.signal_type == SignalType.BUY and position_side == "Sell":
                    self.logger.info(f"Signal conflicts with existing {position_side} position for {symbol}")
                    self.logger.debug(f"← _validate_signal returned False (position conflict)")
                    return False
                    
                if signal.signal_type == SignalType.SELL and position_side == "Buy":
                    self.logger.info(f"Signal conflicts with existing {position_side} position for {symbol}")
                    self.logger.debug(f"← _validate_signal returned False (position conflict)")
                    return False
            
            # Get risk management settings
            risk_config = self.config.get('execution', {}).get('risk_management', {})
            max_positions = risk_config.get('max_open_positions', 1)
            
            # Check if we've hit the maximum positions limit
            total_positions = sum(1 for pos in await self.order_manager.get_positions() if float(pos.get("size", "0")) != 0)
            if total_positions >= max_positions:
                self.logger.info(f"Maximum positions limit reached ({max_positions})")
                self.logger.debug(f"← _validate_signal returned False (max positions)")
                return False
            
            self.logger.debug(f"← _validate_signal returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating signal: {str(e)}")
            self.logger.debug(f"← _validate_signal returned False (error)")
            return False
    
    async def _execute_signal(self, signal: TradeSignal) -> None:
        """
        Execute a trading signal
        
        Args:
            signal: TradeSignal object
        """
        self.logger.debug(f"→ _execute_signal(signal={signal})")
        
        try:
            # Get symbol from signal or use default
            symbol = signal.symbol if hasattr(signal, 'symbol') else self.symbol
            
            # Get position sizing
            size = self._calculate_position_size(symbol)
            
            # Determine order side based on signal type
            if signal.signal_type == SignalType.BUY:
                side = "Buy"
            elif signal.signal_type == SignalType.SELL:
                side = "Sell"
            else:
                self.logger.warning(f"Unsupported signal type: {signal.signal_type}")
                return
            
            # Get current price
            ticker = self.market_data_manager.get_ticker(symbol)
            current_price = float(ticker.get("last_price", signal.price))
            
            # Get stop loss and take profit prices from signal
            sl_price = signal.sl_price
            tp_price = signal.tp_price
            
            # Place the order
            self.logger.info(f"Executing {side} order for {symbol} at {current_price} (qty={size})")
            
            # Get order execution settings
            execution_config = self.config.get('execution', {}).get('order_execution', {})
            
            # Use order type from signal if available, otherwise use config
            if hasattr(signal, 'order_type') and signal.order_type:
                order_type = signal.order_type.value
            else:
                order_type = execution_config.get('default_order_type', "MARKET")
            
            if order_type == "MARKET":
                # Place market order
                result = await self.order_manager.place_market_order(
                    symbol=symbol,
                    side=side,
                    qty=size,
                    reduce_only=False,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
            else:
                # Place limit order slightly away from current price
                limit_price = current_price * 0.999 if side == "Buy" else current_price * 1.001
                
                result = await self.order_manager.place_limit_order(
                    symbol=symbol,
                    side=side,
                    qty=size,
                    price=limit_price,
                    reduce_only=False,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
            
            # Check for errors
            if "error" in result:
                self.logger.error(f"Order execution failed: {result['error']}")
                self.performance['errors'] += 1
            else:
                self.logger.info(f"Order placed successfully: {result.get('orderId', 'unknown')}")
                self.performance['orders_placed'] += 1
                
                # Add to TP/SL tracking
                if tp_price or sl_price:
                    self.tpsl_manager.add_tpsl_order(
                        symbol=symbol,
                        order_id=result.get("orderId"),
                        side=side,
                        entry_price=current_price,
                        tp_price=tp_price,
                        sl_price=sl_price
                    )
            
        except Exception as e:
            self.logger.error(f"Error executing signal: {str(e)}")
            self.performance['errors'] += 1
            
        finally:
            self.logger.debug(f"← _execute_signal completed")
    
    def _calculate_position_size(self, symbol: str) -> float:
        """
        Calculate the position size based on configuration
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position size
        """
        self.logger.debug(f"→ _calculate_position_size(symbol={symbol})")
        
        try:
            # Get position sizing configuration
            sizing_config = self.config.get('execution', {}).get('position_sizing', {})
            default_size = sizing_config.get('default_size', 0.01)
            max_size = sizing_config.get('max_size', 0.1)
            position_size_usdt = sizing_config.get('position_size_usdt', 100.0)
            sizing_method = sizing_config.get('sizing_method', 'fixed')
            
            if sizing_method == 'fixed':
                # Use fixed size
                size = default_size
            elif sizing_method == 'usd':
                # Calculate size based on USD value
                ticker = self.market_data_manager.get_ticker(symbol)
                if not ticker:
                    self.logger.warning(f"No ticker data for {symbol}, using default size")
                    size = default_size
                else:
                    price = float(ticker.get('last_price', 0))
                    if price <= 0:
                        self.logger.warning(f"Invalid price for {symbol}, using default size")
                        size = default_size
                    else:
                        size = position_size_usdt / price
            else:
                # Unknown method, use default
                self.logger.warning(f"Unknown sizing method '{sizing_method}', using default size")
                size = default_size
                
            # Ensure size is within limits
            size = min(max(size, 0.001), max_size)
            
            self.logger.debug(f"← _calculate_position_size returned {size}")
            return size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            self.logger.debug(f"← _calculate_position_size returned default 0.01 (error)")
            return 0.01
    
    async def _update_positions(self) -> None:
        """
        Update the tracking of open positions
        """
        self.logger.debug(f"→ _update_positions()")
        
        try:
            # Get all current positions
            positions = await self.order_manager.get_positions()
            
            # Update the position cache
            self.position_cache = {}
            
            for position in positions:
                symbol = position.get("symbol")
                size = float(position.get("size", "0"))
                
                if symbol and size != 0:
                    self.position_cache[symbol] = position
                    
            # Update order status
            await self.order_manager.sync_order_status()
            
        except Exception as e:
            self.logger.error(f"Error updating positions: {str(e)}")
            
        finally:
            self.logger.debug(f"← _update_positions completed")
    
    def get_status(self) -> Dict:
        """
        Get the current status of the trading engine
        
        Returns:
            Dictionary with engine status
        """
        self.logger.debug(f"→ get_status()")
        
        status = {
            "running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime": str(datetime.now() - self.start_time) if self.start_time else "0",
            "symbols": self.symbols,
            "positions": len(self.position_cache),
            "performance": self.performance
        }
        
        self.logger.debug(f"← get_status returned status")
        return status