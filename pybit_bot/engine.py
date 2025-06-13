"""
Main Trading Engine - Coordinates data flow and manages the trading lifecycle.
Integrates strategy manager, TPSL manager, and order execution.
"""

import logging
import time
import threading
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import pandas as pd

from pybit_bot.managers.strategy_manager import StrategyManager
from pybit_bot.managers.tpsl_manager import TPSLManager
from pybit_bot.strategies.base_strategy import TradeSignal
from pybit_bot.bybit.market_data import MarketDataManager
from pybit_bot.bybit.order_manager import OrderManager
from pybit_bot.utils.logger import setup_logger


class TradingEngine:
    """
    Main trading engine that coordinates all components and manages the trading lifecycle.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the trading engine with configuration.
        
        Args:
            config_path: Path to the configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Set up logging
        log_dir = self.config.get('logging', {}).get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        self.logger = setup_logger('trading_engine', log_dir, log_level)
        
        # Initialize components
        self.market_data_manager = None
        self.order_manager = None
        self.strategy_manager = None
        self.tpsl_manager = None
        
        # Engine state
        self.is_running = False
        self.start_time = None
        self.last_data_update = {}
        self.symbols = self.config.get('trading', {}).get('symbols', [])
        self._stop_event = threading.Event()
        self._main_thread = None
        
        # Performance tracking
        self.performance = {
            'signals_generated': 0,
            'orders_placed': 0,
            'orders_filled': 0,
            'errors': 0,
            'latency_ms': []
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
            # Initialize API clients
            api_config = self.config.get('api', {})
            testnet = api_config.get('testnet', True)
            
            # Initialize market data manager
            self.market_data_manager = MarketDataManager(
                api_key=api_config.get('key'),
                api_secret=api_config.get('secret'),
                testnet=testnet,
                symbols=self.symbols
            )
            
            # Initialize order manager
            self.order_manager = OrderManager(
                api_key=api_config.get('key'),
                api_secret=api_config.get('secret'),
                testnet=testnet
            )
            
            # Initialize strategy manager
            self.strategy_manager = StrategyManager(self.config)
            
            # Initialize TPSL manager
            self.tpsl_manager = TPSLManager(self.config, self.order_manager)
            
            # Subscribe to order updates
            self.order_manager.add_fill_callback(self._handle_order_fill)
            
            # Get required timeframes from strategy manager
            timeframes = set()
            for symbol in self.symbols:
                symbol_timeframes = self.strategy_manager.get_required_timeframes(symbol)
                timeframes.update(symbol_timeframes)
                
                # Initialize last data update tracker
                self.last_data_update[symbol] = {}
                for tf in symbol_timeframes:
                    self.last_data_update[symbol][tf] = 0
            
            # Subscribe to market data
            for symbol in self.symbols:
                for timeframe in timeframes:
                    self.market_data_manager.subscribe_kline(symbol, timeframe)
            
            # Set up market data callback
            self.market_data_manager.add_kline_callback(self._handle_kline_update)
            
            self.logger.info("Trading engine initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing trading engine: {str(e)}", exc_info=True)
            return False
    
    def start(self):
        """
        Start the trading engine.
        """
        if self.is_running:
            self.logger.warning("Trading engine is already running")
            return False
            
        self.logger.info("Starting trading engine...")
        
        try:
            # Start all components
            self.market_data_manager.start()
            self.order_manager.start()
            self.tpsl_manager.start()
            
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
        
        # Stop all components
        if self.market_data_manager:
            self.market_data_manager.stop()
            
        if self.order_manager:
            self.order_manager.stop()
            
        if self.tpsl_manager:
            self.tpsl_manager.stop()
        
        # Set state
        self.is_running = False
        
        self.logger.info("Trading engine stopped")
    
    def _main_loop(self):
        """
        Main trading engine loop.
        """
        self.logger.info("Main trading loop started")
        
        # Check interval (in seconds)
        check_interval = self.config.get('engine', {}).get('check_interval_seconds', 1)
        
        while not self._stop_event.is_set():
            try:
                # Perform periodic tasks
                self._check_connection_status()
                self._check_account_status()
                
                # Process any pending actions
                
                # Wait for next iteration
                time.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                self.performance['errors'] += 1
                
                # If too many errors, consider stopping
                max_errors = self.config.get('engine', {}).get('max_errors_before_shutdown', 10)
                if self.performance['errors'] >= max_errors:
                    self.logger.error(f"Reached maximum error count ({max_errors}), stopping engine")
                    self.stop()
                    break
                    
                # Wait before retrying
                time.sleep(5)
        
        self.logger.info("Main trading loop stopped")
    
    def _check_connection_status(self):
        """
        Check if all components are connected.
        """
        if not self.market_data_manager.is_connected():
            self.logger.warning("Market data manager is not connected, attempting to reconnect")
            self.market_data_manager.reconnect()
            
        if not self.order_manager.is_connected():
            self.logger.warning("Order manager is not connected, attempting to reconnect")
            self.order_manager.reconnect()
    
    def _check_account_status(self):
        """
        Check account status and balance.
        """
        # This would be implemented to check for sufficient margin, etc.
        pass
    
    def _handle_kline_update(self, symbol: str, timeframe: str, kline: Dict[str, Any]):
        """
        Handle market data updates.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe (e.g., '1m', '5m')
            kline: Kline data
        """
        try:
            # Check if this is a new kline
            start_time = kline.get('start_time', 0)
            if start_time <= self.last_data_update[symbol].get(timeframe, 0):
                return
                
            # Update last data time
            self.last_data_update[symbol][timeframe] = start_time
            
            # Get all market data for this symbol
            market_data = self.market_data_manager.get_klines(symbol)
            
            # Process through strategy manager
            start_time_ms = time.time() * 1000
            signals = self.strategy_manager.process_market_data(symbol, market_data)
            end_time_ms = time.time() * 1000
            
            # Track latency
            latency_ms = end_time_ms - start_time_ms
            self.performance['latency_ms'].append(latency_ms)
            
            # Process signals
            if signals:
                self.logger.info(f"Generated {len(signals)} signals for {symbol}")
                self.performance['signals_generated'] += len(signals)
                
                for signal in signals:
                    self._process_trade_signal(signal)
                    
            # Update TPSL manager with current price
            current_price = kline.get('close', 0)
            atr_value = None
            
            # Try to get ATR value from market data
            if '1m' in market_data and 'atr' in market_data['1m'].columns:
                atr_value = market_data['1m']['atr'].iloc[-1]
            
            # Update TPSL manager
            tpsl_actions = self.tpsl_manager.update_market_data(symbol, current_price, atr_value)
            
            # Process TPSL actions if needed
            if tpsl_actions:
                self.logger.info(f"TPSL manager generated {len(tpsl_actions)} actions for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Error handling kline update: {str(e)}", exc_info=True)
            self.performance['errors'] += 1
    
    def _process_trade_signal(self, signal: TradeSignal):
        """
        Process a trade signal from a strategy.
        
        Args:
            signal: Trade signal to process
        """
        try:
            # Check if we should execute this signal
            if not self._should_execute_signal(signal):
                return
                
            # Determine order parameters
            symbol = signal.symbol
            side = "Buy" if signal.signal_type.name == "BUY" else "Sell"
            order_type = signal.order_type.name
            
            # Calculate position size
            size = self._calculate_position_size(signal)
            
            # Place the order
            order_result = self.order_manager.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                qty=size,
                price=signal.price if order_type == "LIMIT" else None,
                reduce_only=False,
                time_in_force="GTC",
                close_on_trigger=False,
                position_idx=0  # One-way mode
            )
            
            # Track the order
            if order_result and 'order_id' in order_result:
                order_id = order_result['order_id']
                self.logger.info(f"Placed order {order_id} for {symbol}: {side} {size} @ {signal.price}")
                self.performance['orders_placed'] += 1
                
                # Create a position ID for tracking
                position_id = f"{symbol}_{side.lower()}_{int(time.time())}"
                
                # Add position to TPSL manager
                self.tpsl_manager.add_position(
                    symbol=symbol,
                    side=side.upper(),
                    entry_price=signal.price,
                    quantity=size,
                    timestamp=int(time.time() * 1000),
                    position_id=position_id,
                    sl_price=signal.sl_price,
                    tp_price=signal.tp_price,
                    stop_type="TRAILING",
                    trail_config={
                        'activation_pct': 0.5,
                        'callback_rate': 0.3,
                        'atr_multiplier': 2.0,
                        'current_atr': signal.indicator_values.get('atr', 100.0)
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Error processing trade signal: {str(e)}", exc_info=True)
            self.performance['errors'] += 1
    
    def _should_execute_signal(self, signal: TradeSignal) -> bool:
        """
        Determine if a signal should be executed based on various checks.
        
        Args:
            signal: Trade signal to check
            
        Returns:
            True if the signal should be executed, False otherwise
        """
        # Check if trading is enabled for this symbol
        symbol_config = self.config.get('trading', {}).get('symbol_settings', {}).get(signal.symbol, {})
        if not symbol_config.get('enabled', True):
            self.logger.info(f"Trading disabled for {signal.symbol}, ignoring signal")
            return False
            
        # Check time-based restrictions
        if not self._is_valid_trading_time():
            return False
            
        # Check risk limits
        # - Max open positions per symbol
        active_positions = self.tpsl_manager.get_active_positions(signal.symbol)
        max_positions = self.config.get('risk_management', {}).get('max_positions_per_symbol', 1)
        
        if len(active_positions) >= max_positions:
            self.logger.info(
                f"Maximum positions ({max_positions}) reached for {signal.symbol}, "
                f"ignoring signal"
            )
            return False
            
        # - Daily loss limit
        if self._has_reached_daily_loss_limit():
            return False
            
        return True
    
    def _is_valid_trading_time(self) -> bool:
        """
        Check if current time is within allowed trading hours.
        
        Returns:
            True if trading is allowed at the current time, False otherwise
        """
        # This would check trading hours restrictions if configured
        return True
    
    def _has_reached_daily_loss_limit(self) -> bool:
        """
        Check if the daily loss limit has been reached.
        
        Returns:
            True if the daily loss limit has been reached, False otherwise
        """
        # This would check daily loss limits if configured
        return False
    
    def _calculate_position_size(self, signal: TradeSignal) -> float:
        """
        Calculate position size based on risk management rules.
        
        Args:
            signal: Trade signal
            
        Returns:
            Position size
        """
        # Get risk settings
        risk_settings = self.config.get('risk_management', {})
        
        # Fixed size or % of balance
        if risk_settings.get('position_sizing', 'fixed') == 'fixed':
            # Use fixed size from config
            size = risk_settings.get('fixed_size', 0.01)
            
        else:
            # Risk % of balance
            # In a real implementation, we would get the account balance
            # and calculate based on risk percentage and stop distance
            account_balance = 10000.0  # Placeholder
            risk_pct = risk_settings.get('risk_per_trade_pct', 1.0) / 100.0
            
            # Calculate distance to stop loss
            entry_price = signal.price
            sl_price = signal.sl_price
            
            if sl_price and sl_price > 0:
                if signal.signal_type.name == "BUY":
                    risk_distance_pct = (entry_price - sl_price) / entry_price
                else:
                    risk_distance_pct = (sl_price - entry_price) / entry_price
                    
                # Calculate size based on risk
                risk_amount = account_balance * risk_pct
                position_value = risk_amount / risk_distance_pct
                size = position_value / entry_price
            else:
                # Default to fixed size if no stop loss
                size = risk_settings.get('fixed_size', 0.01)
        
        # Apply min/max constraints
        min_size = risk_settings.get('min_position_size', 0.001)
        max_size = risk_settings.get('max_position_size', 1.0)
        
        size = max(min_size, min(size, max_size))
        
        return size
    
    def _handle_order_fill(self, order_data: Dict[str, Any]):
        """
        Handle order fill notifications.
        
        Args:
            order_data: Order fill data
        """
        try:
            # Extract order details
            order_id = order_data.get('order_id')
            symbol = order_data.get('symbol')
            side = order_data.get('side')
            qty = float(order_data.get('exec_qty', 0))
            price = float(order_data.get('exec_price', 0))
            
            self.logger.info(f"Order filled: {order_id} for {symbol}: {side} {qty} @ {price}")
            
            # Update performance tracking
            self.performance['orders_filled'] += 1
            
            # Additional handling as needed
            # ...
            
        except Exception as e:
            self.logger.error(f"Error handling order fill: {str(e)}", exc_info=True)
            self.performance['errors'] += 1
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the trading engine.
        
        Returns:
            Dictionary with engine status
        """
        # Calculate runtime
        runtime = datetime.now() - self.start_time if self.start_time else None
        runtime_str = str(runtime).split('.')[0] if runtime else "Not started"
        
        # Calculate average latency
        avg_latency = sum(self.performance['latency_ms']) / len(self.performance['latency_ms']) if self.performance['latency_ms'] else 0
        
        # Get positions
        active_positions = []
        if self.tpsl_manager:
            active_positions = self.tpsl_manager.get_active_positions()
        
        return {
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'runtime': runtime_str,
            'symbols': self.symbols,
            'performance': {
                'signals_generated': self.performance['signals_generated'],
                'orders_placed': self.performance['orders_placed'],
                'orders_filled': self.performance['orders_filled'],
                'errors': self.performance['errors'],
                'avg_latency_ms': avg_latency
            },
            'connections': {
                'market_data': self.market_data_manager.is_connected() if self.market_data_manager else False,
                'order_manager': self.order_manager.is_connected() if self.order_manager else False
            },
            'active_positions': len(active_positions),
            'last_update': datetime.now().isoformat()
        }
    
    def export_performance(self, filepath: str) -> bool:
        """
        Export performance metrics to a CSV file.
        
        Args:
            filepath: Path to output file
            
        Returns:
            True if export was successful, False otherwise
        """
        try:
            # Get position history
            position_history = self.tpsl_manager.get_closed_positions() if self.tpsl_manager else []
            
            # Export to CSV
            if position_history:
                df = pd.DataFrame(position_history)
                df.to_csv(filepath, index=False)
                self.logger.info(f"Exported performance data to {filepath}")
                return True
            else:
                self.logger.warning("No position history to export")
                return False
                
        except Exception as e:
            self.logger.error(f"Error exporting performance data: {str(e)}", exc_info=True)
            return False