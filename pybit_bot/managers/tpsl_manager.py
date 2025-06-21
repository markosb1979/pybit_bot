"""
TP/SL Manager for PyBit Bot

Handles all aspects of take profit and stop loss management:
- Calculating TP/SL levels based on ATR
- Managing OCO (one-cancels-other) orders
- Implementing trailing stop logic
- Monitoring positions and updating stops
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from decimal import Decimal
import json
import time

from ..utils.logger import Logger
from ..exceptions.errors import OrderError, PositionError


class TPSLManager:
    """
    Take Profit and Stop Loss Manager
    
    Handles post-entry risk management including:
    - TP/SL placement after entry fill
    - OCO (one-cancels-other) order management
    - Trailing stop implementation
    - Position monitoring
    """
    
    def __init__(self, config, order_manager, logger=None, data_manager=None):
        """
        Initialize with required dependencies
        
        Args:
            config: Configuration object
            order_manager: OrderManager instance for order execution
            logger: Optional custom logger
            data_manager: DataManager instance for price data
        """
        self.order_manager = order_manager
        self.data_manager = data_manager
        self.config = config
        self.logger = logger or Logger("TPSLManager")
        
        # Access the OrderManagerClient from OrderManager
        self.order_client = order_manager.order_client if hasattr(order_manager, 'order_client') else None
        
        # Active trades being managed (symbol -> trade_details)
        self.active_trades = {}
        
        # Last known price by symbol
        self.last_prices = {}
        
        # Trailing stop status by symbol
        self.trailing_stops = {}
        
        # Load strategy settings
        self.strategy_config = config.get("strategy_a", {})
        self.risk_settings = self.strategy_config.get("risk_settings", {})
        self.trailing_enabled = self.risk_settings.get("trailing_stop", {}).get("enabled", False)
        self.activation_threshold = self.risk_settings.get("trailing_stop", {}).get("activation_threshold", 0.5)
        self.trail_atr_mult = self.risk_settings.get("trailing_stop", {}).get("atr_multiplier", 2.0)
        self.sl_multiplier = self.risk_settings.get("stop_loss_multiplier", 2.0)
        self.tp_multiplier = self.risk_settings.get("take_profit_multiplier", 4.0)
        
        # Initialize monitoring task
        self._monitor_task = None
        self._running = False
        
        self.logger.info("TPSLManager initialized")
    
    async def check_positions(self):
        """Alias used by the engine to trigger TP/SL checks."""
        await self.check_pending_tpsl_orders()
    
    async def start(self):
        """Start the TP/SL manager and its monitoring task"""
        if self._running:
            self.logger.warning("TPSLManager already running")
            return
            
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_positions())
        self.logger.info("TPSLManager started")
    
    async def stop(self):
        """Stop the TP/SL manager and its monitoring task"""
        if not self._running:
            return
            
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        self.logger.info("TPSLManager stopped")

    def add_position(self, symbol, side, entry_price, quantity, timestamp, position_id, sl_price, tp_price, stop_type="FIXED"):
        """
        Add a position to be managed by the TPSL manager
        
        Args:
            symbol: Trading symbol
            side: Position side (LONG or SHORT)
            entry_price: Entry price
            quantity: Position size
            timestamp: Entry timestamp
            position_id: Unique ID for the position
            sl_price: Stop loss price
            tp_price: Take profit price
            stop_type: Type of stop loss (FIXED, TRAILING)
            
        Returns:
            True if position was added, False otherwise
        """
        try:
            self.active_trades[position_id] = {
                "symbol": symbol,
                "side": side,
                "entry_price": float(entry_price),
                "position_size": float(quantity),
                "timestamp": timestamp,
                "sl_price": float(sl_price),
                "tp_price": float(tp_price),
                "initial_sl_price": float(sl_price),
                "initial_tp_price": float(tp_price),
                "trailing_active": stop_type == "TRAILING",
                "best_price": float(entry_price),
                "stop_type": stop_type
            }
            
            self.logger.info(f"Added position to TPSL manager: {position_id} ({symbol} {side})")
            return True
        except Exception as e:
            self.logger.error(f"Error adding position to TPSL manager: {str(e)}")
            return False
    
    async def check_pending_tpsl_orders(self):
        """
        Check for orders that need TP/SL set after being filled
        """
        # First check if OrderManager has pending orders to process
        if hasattr(self.order_manager, 'check_pending_tpsl_orders'):
            await self.order_manager.check_pending_tpsl_orders()
        
        # Also check active trades for TP/SL hits
        if not self.active_trades:
            return
            
        for position_id, trade in list(self.active_trades.items()):
            symbol = trade.get("symbol")
            
            try:
                # Check if position still exists
                positions = self.order_client.get_positions(symbol) if self.order_client else await self.order_manager.get_positions(symbol)
                if not positions or float(positions[0].get("size", "0")) == 0:
                    self.logger.info(f"Position closed for {symbol}, removing from active trades")
                    if position_id in self.active_trades:
                        del self.active_trades[position_id]
                    continue
                
                # Get current price
                if self.data_manager:
                    current_price = await self.data_manager.get_latest_price(symbol)
                else:
                    # If data_manager is not available, try to get price from order_manager
                    current_price = await self.order_manager.get_current_price(symbol)
                
                if current_price:
                    self.last_prices[symbol] = current_price
                    
                    # Check for TP/SL triggers
                    side = trade.get("side")
                    sl_price = trade.get("sl_price")
                    tp_price = trade.get("tp_price")
                    
                    # For long positions
                    if side == "LONG":
                        # Check if SL was hit
                        if current_price <= sl_price:
                            await self._handle_stop_loss_hit(position_id, trade, current_price)
                            continue
                            
                        # Check if TP was hit
                        if current_price >= tp_price:
                            await self._handle_take_profit_hit(position_id, trade, current_price)
                            continue
                            
                    # For short positions
                    elif side == "SHORT":
                        # Check if SL was hit
                        if current_price >= sl_price:
                            await self._handle_stop_loss_hit(position_id, trade, current_price)
                            continue
                            
                        # Check if TP was hit
                        if current_price <= tp_price:
                            await self._handle_take_profit_hit(position_id, trade, current_price)
                            continue
                    
                    # Update trailing stop if enabled
                    if trade.get("stop_type") == "TRAILING":
                        await self._update_trailing_stop(position_id, trade, current_price)
            
            except Exception as e:
                self.logger.error(f"Error checking position {position_id}: {str(e)}")
    
    async def manage_position(self, symbol: str, entry_price: float, side: str, atr: float, 
                             entry_order_id: str, position_size: float):
        """
        Set up TP/SL management for a new position
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price of the position
            side: "Buy" or "Sell"
            atr: Current ATR value used for calculations
            entry_order_id: ID of the filled entry order
            position_size: Size of the position in contracts
        
        Returns:
            Dict containing TP and SL orders information
        """
        try:
            # Verify position exists
            positions = self.order_client.get_positions(symbol) if self.order_client else await self.order_manager.get_positions(symbol)
            if not positions or float(positions[0].get("size", "0")) == 0:
                self.logger.warning(f"No open position for {symbol}, skipping TP/SL")
                return {"error": "No position found"}
            
            # If atr is not provided or invalid, try to get it from data_manager
            if not atr or atr <= 0:
                try:
                    if self.data_manager and hasattr(self.data_manager, 'get_atr'):
                        atr = await self.data_manager.get_atr(symbol, timeframe="1m", length=14)
                        self.logger.info(f"Retrieved ATR from data_manager: {atr}")
                    else:
                        # Try to get ATR from historical data
                        if self.data_manager and hasattr(self.data_manager, 'get_historical_data'):
                            hist_data = await self.data_manager.get_historical_data(symbol, interval="1m", limit=20)
                            if not hist_data.empty and len(hist_data) > 14:
                                # Calculate ATR from recent price data
                                tr_values = []
                                for i in range(1, len(hist_data)):
                                    high = hist_data['high'].iloc[i]
                                    low = hist_data['low'].iloc[i]
                                    prev_close = hist_data['close'].iloc[i-1]
                                    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                                    tr_values.append(tr)
                                atr = sum(tr_values[-14:]) / 14
                                self.logger.info(f"Calculated ATR from historical data: {atr}")
                except Exception as e:
                    self.logger.error(f"Error retrieving ATR: {str(e)}")
                    # We'll validate against mark price below even without ATR
            
            # Get mark price for validation
            mark_price = float(positions[0].get("markPrice", entry_price))
            
            # Calculate TP/SL levels
            tp_price, sl_price = self._calculate_tp_sl(entry_price, side, atr)
            
            # Validate against mark price
            direction = "LONG" if side == "Buy" else "SHORT"
            if direction == "LONG":
                # Clamp against mark price
                if tp_price <= mark_price:
                    tp_price = mark_price * 1.002
                    self.logger.warning(f"Adjusted TP above mark: {tp_price}")
                if sl_price >= mark_price:
                    sl_price = mark_price * 0.998
                    self.logger.warning(f"Adjusted SL below mark: {sl_price}")
            else:
                # Clamp against mark price
                if tp_price >= mark_price:
                    tp_price = mark_price * 0.998
                    self.logger.warning(f"Adjusted TP below mark: {tp_price}")
                if sl_price <= mark_price:
                    sl_price = mark_price * 1.002
                    self.logger.warning(f"Adjusted SL above mark: {sl_price}")
            
            # Round prices properly
            tp_price_str = await self._round_price(symbol, tp_price)
            sl_price_str = await self._round_price(symbol, sl_price)
            
            self.logger.info(f"Managing {side} position for {symbol} entered at {entry_price} with ATR {atr}")
            self.logger.info(f"Final TP/SL for {symbol} {direction}: TP={tp_price_str}, SL={sl_price_str}, Mark Price={mark_price}")
            
            # Set TP/SL using order_client's amend_order if we have order_id, otherwise use set_position_tpsl
            if self.order_client:
                # Try to use amend_order if entry_order_id is valid
                try:
                    # First check if the order exists and can be amended
                    order_info = self.order_client.get_order(symbol, entry_order_id)
                    if order_info and order_info.get("orderId") == entry_order_id:
                        # Use amend_order to set TP/SL
                        result = self.order_client.amend_order(
                            symbol=symbol,
                            order_id=entry_order_id,
                            take_profit=tp_price_str,
                            stop_loss=sl_price_str,
                            tp_trigger_by="MarkPrice",
                            sl_trigger_by="MarkPrice"
                        )
                        self.logger.info(f"Amended order {entry_order_id} to set TP/SL")
                    else:
                        # Order not amendable, use set_position_tpsl
                        result = self.order_client.set_position_tpsl(
                            symbol=symbol,
                            position_idx=0,  # One-way mode
                            tp_price=tp_price_str,
                            sl_price=sl_price_str
                        )
                        self.logger.info(f"Used set_position_tpsl to set TP/SL")
                except Exception as e:
                    self.logger.warning(f"Error using amend_order, falling back to set_position_tpsl: {str(e)}")
                    # Fall back to set_position_tpsl
                    result = self.order_client.set_position_tpsl(
                        symbol=symbol,
                        position_idx=0,  # One-way mode
                        tp_price=tp_price_str,
                        sl_price=sl_price_str
                    )
            else:
                # Fallback to old method via order_manager
                tp_order = await self.order_manager.set_position_tpsl(
                    symbol=symbol, 
                    position_idx=0, 
                    tp_price=tp_price_str, 
                    sl_price=sl_price_str
                )
                result = tp_order
            
            # Track the position for monitoring
            position_id = f"{symbol}_{entry_order_id}"
            self.active_trades[position_id] = {
                "symbol": symbol,
                "entry_price": float(entry_price),
                "side": direction,
                "atr": float(atr),
                "position_size": float(position_size),
                "entry_order_id": entry_order_id,
                "tp_price": float(tp_price),
                "sl_price": float(sl_price),
                "initial_sl_price": float(sl_price),
                "initial_tp_price": float(tp_price),
                "trailing_active": False,
                "best_price": float(entry_price),
                "timestamp": time.time()
            }
            
            return {
                "result": result,
                "tp_price": tp_price,
                "sl_price": sl_price
            }
            
        except Exception as e:
            self.logger.error(f"Error setting TP/SL for {symbol}: {str(e)}")
            raise OrderError(f"Failed to set TP/SL: {str(e)}")
    
    async def cancel_tpsl(self, symbol: str):
        """
        Cancel TP/SL orders for a position
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict with results of cancel operations
        """
        if symbol not in self.active_trades:
            self.logger.warning(f"No active TP/SL orders found for {symbol}")
            return {"status": "No active orders"}
            
        trade = self.active_trades[symbol]
        results = {"tp_cancel": None, "sl_cancel": None}
        
        # Cancel TP order if exists
        if trade.get("tp_order_id"):
            try:
                tp_cancel = await self.order_manager.cancel_order(symbol, trade["tp_order_id"])
                results["tp_cancel"] = tp_cancel
                self.logger.info(f"Cancelled TP order for {symbol}: {trade['tp_order_id']}")
            except Exception as e:
                self.logger.error(f"Error cancelling TP order: {str(e)}")
                results["tp_cancel"] = {"error": str(e)}
        
        # Cancel SL order if exists
        if trade.get("sl_order_id"):
            try:
                sl_cancel = await self.order_manager.cancel_order(symbol, trade["sl_order_id"])
                results["sl_cancel"] = sl_cancel
                self.logger.info(f"Cancelled SL order for {symbol}: {trade['sl_order_id']}")
            except Exception as e:
                self.logger.error(f"Error cancelling SL order: {str(e)}")
                results["sl_cancel"] = {"error": str(e)}
        
        # Remove from active trades
        if symbol in self.active_trades:
            del self.active_trades[symbol]
            
        return results
    
    def _calculate_tp_sl(self, entry_price: float, side: str, atr: float) -> Tuple[float, float]:
        """
        Calculate TP and SL levels based on entry price, side, and ATR
        
        Args:
            entry_price: Entry price of position
            side: "Buy" or "Sell"
            atr: Current ATR value
            
        Returns:
            Tuple of (tp_price, sl_price)
        """
        entry_price = float(entry_price)
        atr = float(atr)
        
        if side == "Buy":
            # Long position
            tp_price = entry_price + (atr * self.tp_multiplier)
            sl_price = entry_price - (atr * self.sl_multiplier)
        else:
            # Short position
            tp_price = entry_price - (atr * self.tp_multiplier)
            sl_price = entry_price + (atr * self.sl_multiplier)
            
        return tp_price, sl_price
    
    async def _update_trailing_stop(self, position_id: str, trade: dict, current_price: float):
        """
        Update trailing stop based on current price movement
        
        Args:
            position_id: Position identifier
            trade: Trade details
            current_price: Current price for evaluation
            
        Returns:
            Boolean indicating if stop was updated
        """
        symbol = trade["symbol"]
        side = trade["side"]
        entry_price = trade["entry_price"]
        best_price = trade["best_price"]
        sl_price = trade["sl_price"]
        
        # If trailing is not active yet, check if we should activate it
        if not trade.get("trailing_active"):
            # For long positions
            if side == "LONG":
                # Calculate activation threshold (% to TP)
                tp_price = trade["tp_price"]
                profit_range = tp_price - entry_price
                activation_point = entry_price + (profit_range * self.activation_threshold)
                
                # Activate if price reached the threshold
                if current_price >= activation_point:
                    trade["trailing_active"] = True
                    self.logger.info(f"Trailing stop activated for {symbol} at {current_price}")
                else:
                    return False
            
            # For short positions
            elif side == "SHORT":
                # Calculate activation threshold (% to TP)
                tp_price = trade["tp_price"]
                profit_range = entry_price - tp_price
                activation_point = entry_price - (profit_range * self.activation_threshold)
                
                # Activate if price reached the threshold
                if current_price <= activation_point:
                    trade["trailing_active"] = True
                    self.logger.info(f"Trailing stop activated for {symbol} at {current_price}")
                else:
                    return False
        
        # Update trailing stop if active
        if trade.get("trailing_active"):
            # For long positions
            if side == "LONG":
                # Track new high price
                if current_price > best_price:
                    trade["best_price"] = current_price
                    
                    # Calculate new SL based on current price
                    # Use ATR if available, otherwise use a percentage of current price
                    if "atr" in trade:
                        new_sl = current_price - (trade["atr"] * self.trail_atr_mult)
                    else:
                        # Default to 2% below current price
                        new_sl = current_price * 0.98
                    
                    # Only move SL up, never down
                    if new_sl > sl_price:
                        trade["sl_price"] = new_sl
                        self.logger.info(f"Updated trailing stop for {symbol} to {new_sl}")
                        
                        # Use amend_order or set_position_tpsl to update the stop loss
                        if self.order_client:
                            # Round price for API
                            sl_price_str = self.order_client._round_price(symbol, new_sl)
                            
                            # Update stop loss using OrderManagerClient
                            try:
                                result = self.order_client.set_position_tpsl(
                                    symbol=symbol,
                                    position_idx=0,  # One-way mode
                                    tp_price=self.order_client._round_price(symbol, trade["tp_price"]),
                                    sl_price=sl_price_str
                                )
                                self.logger.info(f"Updated trailing stop via API: {result}")
                            except Exception as e:
                                self.logger.error(f"Error updating trailing stop via API: {str(e)}")
                        
                        return True
            
            # For short positions
            elif side == "SHORT":
                # Track new low price
                if current_price < best_price:
                    trade["best_price"] = current_price
                    
                    # Calculate new SL based on current price
                    if "atr" in trade:
                        new_sl = current_price + (trade["atr"] * self.trail_atr_mult)
                    else:
                        # Default to 2% above current price
                        new_sl = current_price * 1.02
                    
                    # Only move SL down, never up
                    if new_sl < sl_price:
                        trade["sl_price"] = new_sl
                        self.logger.info(f"Updated trailing stop for {symbol} to {new_sl}")
                        
                        # Update stop loss using OrderManagerClient
                        if self.order_client:
                            # Round price for API
                            sl_price_str = self.order_client._round_price(symbol, new_sl)
                            
                            # Update stop loss using OrderManagerClient
                            try:
                                result = self.order_client.set_position_tpsl(
                                    symbol=symbol,
                                    position_idx=0,  # One-way mode
                                    tp_price=self.order_client._round_price(symbol, trade["tp_price"]),
                                    sl_price=sl_price_str
                                )
                                self.logger.info(f"Updated trailing stop via API: {result}")
                            except Exception as e:
                                self.logger.error(f"Error updating trailing stop via API: {str(e)}")
                                
                        return True
        
        return False

    async def _handle_stop_loss_hit(self, position_id, trade, current_price):
        """Handle a stop loss being triggered"""
        symbol = trade.get("symbol")
        side = trade.get("side")
        sl_price = trade.get("sl_price")
        
        self.logger.info(f"Stop loss triggered for {symbol} {side} at {sl_price}")
        
        # Close the position if not already closed
        try:
            # Check if position still exists
            positions = self.order_client.get_positions(symbol) if self.order_client else await self.order_manager.get_positions(symbol)
            if positions and float(positions[0].get("size", "0")) > 0:
                # Close the position
                close_result = await self.order_manager.close_position(symbol)
                self.logger.info(f"Closed position for {symbol} due to stop loss: {close_result}")
        except Exception as e:
            self.logger.error(f"Error closing position on stop loss: {str(e)}")
        
        # Remove from active trades
        if position_id in self.active_trades:
            del self.active_trades[position_id]

    async def _handle_take_profit_hit(self, position_id, trade, current_price):
        """Handle a take profit being triggered"""
        symbol = trade.get("symbol")
        side = trade.get("side")
        tp_price = trade.get("tp_price")
        
        self.logger.info(f"Take profit triggered for {symbol} {side} at {tp_price}")
        
        # Close the position if not already closed
        try:
            # Check if position still exists
            positions = self.order_client.get_positions(symbol) if self.order_client else await self.order_manager.get_positions(symbol)
            if positions and float(positions[0].get("size", "0")) > 0:
                # Close the position
                close_result = await self.order_manager.close_position(symbol)
                self.logger.info(f"Closed position for {symbol} due to take profit: {close_result}")
        except Exception as e:
            self.logger.error(f"Error closing position on take profit: {str(e)}")
        
        # Remove from active trades
        if position_id in self.active_trades:
            del self.active_trades[position_id]
    
    async def _monitor_positions(self):
        """
        Continuously monitor positions and update trailing stops
        """
        self.logger.info("Position monitoring started")
        
        while self._running:
            try:
                # Process each active trade
                for position_id in list(self.active_trades.keys()):
                    if position_id not in self.active_trades:
                        continue  # Position might have been removed by another process
                    
                    trade = self.active_trades[position_id]
                    symbol = trade.get("symbol")
                    
                    # Skip if trailing stops are not enabled
                    if not self.trailing_enabled:
                        continue
                        
                    # Get current price
                    try:
                        if self.data_manager:
                            current_price = await self.data_manager.get_latest_price(symbol)
                        else:
                            current_price = await self.order_manager.get_current_price(symbol)
                            
                        if current_price:
                            self.last_prices[symbol] = current_price
                            
                            # Check if position still exists
                            positions = self.order_client.get_positions(symbol) if self.order_client else await self.order_manager.get_positions(symbol)
                            if not positions or float(positions[0].get("size", "0")) == 0:
                                self.logger.info(f"Position closed for {symbol}, removing from active trades")
                                if position_id in self.active_trades:
                                    del self.active_trades[position_id]
                                continue
                            
                            # Update trailing stop if needed
                            await self._update_trailing_stop(position_id, trade, current_price)
                    
                    except Exception as e:
                        self.logger.error(f"Error monitoring position for {symbol}: {str(e)}")
                
                # Sleep to avoid high CPU usage
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                self.logger.info("Position monitoring cancelled")
                break
                
            except Exception as e:
                self.logger.error(f"Error in position monitoring: {str(e)}")
                await asyncio.sleep(5)  # Longer sleep on error
    
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

    async def update_trade_status(self, symbol: str, order_id: str, status: str):
        """
        Update the status of TP/SL orders when they fill or cancel.
        """
        # Find the position_id for this symbol
        position_id = None
        for pid, trade in self.active_trades.items():
            if trade.get("symbol") == symbol:
                position_id = pid
                break
        
        if not position_id:
            return
            
        trade = self.active_trades[position_id]
        
        # Handle order status updates
        if order_id == trade.get("tp_order_id") and status == "Filled":
            self.logger.info(f"Take profit hit for {symbol} at {trade.get('tp_price')}")
            await self._handle_take_profit_hit(position_id, trade, trade.get("tp_price"))
            
        elif order_id == trade.get("sl_order_id") and status == "Filled":
            self.logger.info(f"Stop loss hit for {symbol} at {trade.get('sl_price')}")
            await self._handle_stop_loss_hit(position_id, trade, trade.get("sl_price"))
            
        # Handle cancellations
        elif status in ["Cancelled", "Rejected"]:
            self.logger.info(f"Order {order_id} for {symbol} was {status.lower()}")
            
            # If it was a TP or SL order, clear the reference
            if order_id == trade.get("tp_order_id"):
                trade["tp_order_id"] = None
            elif order_id == trade.get("sl_order_id"):
                trade["sl_order_id"] = None