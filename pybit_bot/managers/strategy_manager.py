"""
Strategy Manager for PyBit Bot

Handles all aspects of trading strategy:
- Indicator data analysis
- Signal generation
- Entry/exit decisions
- Trade management lifecycle
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
import time
import json

from ..utils.logger import Logger
from ..exceptions.errors import StrategyError, OrderError


class StrategyManager:
    """
    Strategy Manager for trading decisions
    
    Analyzes indicator data, generates trade signals,
    and manages the full trade lifecycle.
    """
    
    def __init__(self, order_manager, data_manager, tpsl_manager, config, logger=None):
        """
        Initialize with required dependencies
        
        Args:
            order_manager: OrderManager instance for order execution
            data_manager: DataManager instance for price and indicator data
            tpsl_manager: TPSLManager for managing TP/SL
            config: Configuration object
            logger: Optional custom logger
        """
        self.order_manager = order_manager
        self.data_manager = data_manager
        self.tpsl_manager = tpsl_manager
        self.config = config
        self.logger = logger or Logger("StrategyManager")
        
        # Load indicator config
        self.indicator_config = config.load_indicator_config()
        
        # Load strategy config
        self.strategy_config = self.indicator_config.get("strategy_a", {})
        self.filter_confluence = self.strategy_config.get("filter_confluence", True)
        self.use_limit_entries = self.strategy_config.get("use_limit_entries", True)
        
        # Entry settings
        self.entry_settings = self.strategy_config.get("entry_settings", {})
        self.max_long_trades = self.entry_settings.get("max_long_trades", 1)
        self.max_short_trades = self.entry_settings.get("max_short_trades", 1)
        self.order_timeout_seconds = self.entry_settings.get("order_timeout_seconds", 30)
        
        # Track active orders and positions
        self.pending_orders = {}  # symbol -> order details
        self.active_positions = {}  # symbol -> position details
        
        # Signal processing task
        self._signal_task = None
        self._running = False
        
        # Trading enabled
        self.trading_enabled = self.strategy_config.get("enabled", True)
        
        self.logger.info("StrategyManager initialized")
        
        # Log configuration
        self.logger.info(f"Filter confluence: {self.filter_confluence}")
        self.logger.info(f"Use limit entries: {self.use_limit_entries}")
        self.logger.info(f"Max long trades: {self.max_long_trades}")
        self.logger.info(f"Max short trades: {self.max_short_trades}")
    
    async def start(self):
        """Start the strategy manager and signal processing"""
        if self._running:
            self.logger.warning("StrategyManager already running")
            return
            
        self._running = True
        self._signal_task = asyncio.create_task(self._process_signals())
        self.logger.info("StrategyManager started")
    
    async def stop(self):
        """Stop the strategy manager and signal processing"""
        if not self._running:
            return
            
        self._running = False
        if self._signal_task:
            self._signal_task.cancel()
            try:
                await self._signal_task
            except asyncio.CancelledError:
                pass
            self._signal_task = None
        
        self.logger.info("StrategyManager stopped")
    
    async def _process_signals(self):
        """
        Main signal processing loop
        
        Runs continuously, checking for new signals and managing trades
        """
        self.logger.info("Signal processing started")
        
        while self._running:
            try:
                # Skip if trading is disabled
                if not self.trading_enabled:
                    await asyncio.sleep(5)
                    continue
                
                # Get data for all configured symbols
                symbols = await self.data_manager.get_symbols()
                
                for symbol in symbols:
                    # Skip if we're already processing this symbol
                    if symbol in self.pending_orders:
                        continue
                        
                    # Check if we've reached max positions
                    long_count = sum(1 for pos in self.active_positions.values() if pos.get("side") == "Buy")
                    short_count = sum(1 for pos in self.active_positions.values() if pos.get("side") == "Sell")
                    
                    if long_count >= self.max_long_trades and short_count >= self.max_short_trades:
                        continue
                    
                    # Get latest indicator data
                    try:
                        df = await self.data_manager.get_indicator_data(symbol)
                        if df is None or df.empty or len(df) < 2:
                            continue
                            
                        # Check for signals on the last completed bar
                        signal = self._check_signal(df.iloc[-2], symbol)
                        
                        if signal:
                            # We have a valid signal
                            side = signal["side"]
                            
                            # Check if we've reached max positions for this side
                            if side == "Buy" and long_count >= self.max_long_trades:
                                continue
                            if side == "Sell" and short_count >= self.max_short_trades:
                                continue
                                
                            # Process the signal
                            await self._execute_signal(signal, symbol, df.iloc[-2])
                    
                    except Exception as e:
                        self.logger.error(f"Error processing signals for {symbol}: {str(e)}")
                
                # Check for order timeouts
                await self._check_order_timeouts()
                
                # Sleep to avoid high CPU usage
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                self.logger.info("Signal processing cancelled")
                break
                
            except Exception as e:
                self.logger.error(f"Error in signal processing: {str(e)}")
                await asyncio.sleep(5)  # Longer sleep on error
    
    def _check_signal(self, row, symbol):
        """
        Check if the current bar generates a valid signal
        
        Args:
            row: DataFrame row containing indicator values
            symbol: Trading symbol
            
        Returns:
            Signal dict or None if no signal
        """
        # Get enabled indicators from config
        indicators = self.indicator_config.get("indicators", {})
        
        # Check if indicators are in the row
        cvd_enabled = indicators.get("cvd", {}).get("enabled", True)
        tva_enabled = indicators.get("tva", {}).get("enabled", True)
        vfi_enabled = indicators.get("vfi", {}).get("enabled", True)
        fvg_enabled = indicators.get("luxfvgtrend", {}).get("enabled", True)
        
        # Initialize signal flags
        long_signal = True
        short_signal = True
        
        # Apply indicator filters if confluence is enabled
        if self.filter_confluence:
            # CVD filter
            if cvd_enabled and "cvd" in row:
                cvd_value = row["cvd"]
                if cvd_value <= 0:
                    long_signal = False
                if cvd_value >= 0:
                    short_signal = False
            
            # TVA filter
            if tva_enabled and "rb" in row and "rr" in row:
                rb_value = row["rb"]
                rr_value = row["rr"]
                if rb_value <= 0:
                    long_signal = False
                if rr_value >= 0:
                    short_signal = False
            
            # VFI filter
            if vfi_enabled and "vfi" in row:
                vfi_value = row["vfi"]
                if vfi_value <= 0:
                    long_signal = False
                if vfi_value >= 0:
                    short_signal = False
            
            # FVG filter
            if fvg_enabled and "fvg_signal" in row:
                fvg_value = row["fvg_signal"]
                if fvg_value != 1:
                    long_signal = False
                if fvg_value != -1:
                    short_signal = False
        
        # Determine if we have a valid signal
        if long_signal:
            self.logger.info(f"Long signal generated for {symbol}")
            return {
                "side": "Buy",
                "fvg_midpoint": row.get("fvg_midpoint", 0) if "fvg_midpoint" in row else 0,
                "atr": row.get("atr", 0) if "atr" in row else 0,
                "close": row.get("close", 0)
            }
        elif short_signal:
            self.logger.info(f"Short signal generated for {symbol}")
            return {
                "side": "Sell",
                "fvg_midpoint": row.get("fvg_midpoint", 0) if "fvg_midpoint" in row else 0,
                "atr": row.get("atr", 0) if "atr" in row else 0,
                "close": row.get("close", 0)
            }
        
        return None
    
    async def _execute_signal(self, signal, symbol, row):
        """
        Execute a trading signal
        
        Args:
            signal: Signal dictionary
            symbol: Trading symbol
            row: DataFrame row with indicator data
        """
        side = signal["side"]
        close_price = signal["close"]
        atr = signal["atr"]
        fvg_midpoint = signal["fvg_midpoint"]
        
        # Check if we have opposite pending orders
        if symbol in self.pending_orders:
            pending_order = self.pending_orders[symbol]
            if pending_order["side"] != side:
                # Cancel opposite pending order
                self.logger.info(f"Cancelling opposite pending order for {symbol} due to new signal")
                try:
                    await self.order_manager.cancel_order(symbol, pending_order["order_id"])
                    del self.pending_orders[symbol]
                except Exception as e:
                    self.logger.error(f"Error cancelling opposite order: {str(e)}")
        
        # Check for existing position
        positions = await self.order_manager.get_positions(symbol)
        existing_position = None
        
        for pos in positions:
            if float(pos.get("size", "0")) > 0:
                existing_position = pos
                break
        
        # If we have an existing position on the opposite side, we might want to close it
        if existing_position and existing_position.get("side") != side:
            self.logger.info(f"Existing opposite position found for {symbol}, skipping new signal")
            return
        
        # Calculate position size (fixed USDT amount from config)
        position_size_usdt = self.config.get("trading.position_size_usdt", 50.0)
        qty = await self.order_manager.calculate_position_size(symbol, position_size_usdt)
        
        if not qty or float(qty) <= 0:
            self.logger.error(f"Invalid position size calculated for {symbol}: {qty}")
            return
        
        # Determine entry price
        if self.use_limit_entries and fvg_midpoint > 0:
            # Use FVG midpoint + ATR for limit entry
            if side == "Buy":
                entry_price = fvg_midpoint + atr
            else:
                entry_price = fvg_midpoint - atr
                
            # Round to valid price
            entry_price_str = await self._round_price(symbol, entry_price)
            
            # Place limit order
            try:
                self.logger.info(f"Placing {side} limit order for {symbol} at {entry_price_str}")
                order = await self.order_manager.place_limit_order(symbol, side, qty, entry_price_str)
                
                if "error" in order:
                    self.logger.error(f"Error placing limit order: {order['error']}")
                    return
                
                # Track pending order
                self.pending_orders[symbol] = {
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "price": entry_price,
                    "atr": atr,
                    "order_id": order.get("orderId", ""),
                    "timestamp": time.time()
                }
                
                self.logger.info(f"Limit order placed for {symbol}: {order.get('orderId', '')}")
                
            except Exception as e:
                self.logger.error(f"Error placing limit order: {str(e)}")
        
        else:
            # Use market order at close price
            try:
                self.logger.info(f"Placing {side} market order for {symbol}")
                order = await self.order_manager.place_market_order(symbol, side, qty)
                
                if "error" in order:
                    self.logger.error(f"Error placing market order: {order['error']}")
                    return
                
                # Set TP/SL for the filled market order
                entry_price = close_price  # Use close price as entry for TP/SL
                await self._setup_tpsl(symbol, entry_price, side, atr, order.get("orderId", ""), qty)
                
                # Track active position
                self.active_positions[symbol] = {
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "entry_price": entry_price,
                    "atr": atr,
                    "order_id": order.get("orderId", ""),
                    "timestamp": time.time()
                }
                
                self.logger.info(f"Market order filled for {symbol}: {order.get('orderId', '')}")
                
            except Exception as e:
                self.logger.error(f"Error placing market order: {str(e)}")
    
    async def _setup_tpsl(self, symbol, entry_price, side, atr, order_id, qty):
        """
        Set up TP/SL for a filled order
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            side: "Buy" or "Sell"
            atr: ATR value
            order_id: Filled order ID
            qty: Position size
        """
        try:
            # Use TPSL manager to handle the position
            result = await self.tpsl_manager.manage_position(
                symbol=symbol,
                entry_price=entry_price,
                side=side,
                atr=atr,
                entry_order_id=order_id,
                position_size=qty
            )
            
            self.logger.info(f"TP/SL set for {symbol}: TP={result['tp_price']}, SL={result['sl_price']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error setting up TP/SL: {str(e)}")
            raise OrderError(f"Failed to set TP/SL: {str(e)}")
    
    async def _check_order_timeouts(self):
        """Check for and handle limit order timeouts"""
        current_time = time.time()
        
        # Check each pending order
        for symbol in list(self.pending_orders.keys()):
            order = self.pending_orders[symbol]
            
            # Check if order has timed out
            if current_time - order["timestamp"] > self.order_timeout_seconds:
                self.logger.info(f"Order timeout for {symbol}, cancelling order {order['order_id']}")
                
                try:
                    # Cancel the order
                    await self.order_manager.cancel_order(symbol, order["order_id"])
                    
                    # Remove from pending orders
                    del self.pending_orders[symbol]
                    
                except Exception as e:
                    self.logger.error(f"Error cancelling timed out order: {str(e)}")
    
    async def _round_price(self, symbol: str, price: float) -> str:
        """
        Round price to the correct decimal places for the symbol
        
        Args:
            symbol: Trading symbol
            price: Raw price value
            
        Returns:
            Price as string with correct precision
        """
        # Use OrderManager's built-in rounding if available
        if hasattr(self.order_manager.order_client, "_round_price"):
            return self.order_manager.order_client._round_price(symbol, price)
        
        # Default fallback - round to 2 decimal places
        return "{:.2f}".format(price)
    
    async def handle_order_update(self, symbol: str, order_id: str, status: str):
        """
        Handle order status updates
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            status: New order status
        """
        # Check if this is a pending order that was filled
        if symbol in self.pending_orders and self.pending_orders[symbol]["order_id"] == order_id:
            if status == "Filled":
                self.logger.info(f"Pending order filled for {symbol}: {order_id}")
                
                # Get order details
                pending = self.pending_orders[symbol]
                
                # Set up TP/SL
                await self._setup_tpsl(
                    symbol=symbol,
                    entry_price=pending["price"],
                    side=pending["side"],
                    atr=pending["atr"],
                    order_id=order_id,
                    qty=pending["qty"]
                )
                
                # Move from pending to active
                self.active_positions[symbol] = pending
                del self.pending_orders[symbol]
            
            elif status in ["Cancelled", "Rejected"]:
                self.logger.info(f"Pending order {status.lower()} for {symbol}: {order_id}")
                
                # Remove from pending orders
                if symbol in self.pending_orders:
                    del self.pending_orders[symbol]
        
        # Pass TP/SL updates to TPSL manager
        await self.tpsl_manager.update_trade_status(symbol, order_id, status)
    
    async def handle_position_update(self, symbol: str, side: str, size: float):
        """
        Handle position updates
        
        Args:
            symbol: Trading symbol
            side: Position side
            size: Position size
        """
        # If position size is zero, position was closed
        if size == 0 and symbol in self.active_positions:
            self.logger.info(f"Position closed for {symbol}")
            
            # Cancel any TP/SL orders
            await self.tpsl_manager.cancel_tpsl(symbol)
            
            # Remove from active positions
            del self.active_positions[symbol]