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
    
    def __init__(self, order_manager, data_manager, config, logger=None):
        """
        Initialize with required dependencies
        
        Args:
            order_manager: OrderManager instance for order execution
            data_manager: DataManager instance for price data
            config: Configuration object
            logger: Optional custom logger
        """
        self.order_manager = order_manager
        self.data_manager = data_manager
        self.config = config
        self.logger = logger or Logger("TPSLManager")
        
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
            # Calculate TP/SL levels
            tp_price, sl_price = self._calculate_tp_sl(entry_price, side, atr)
            
            # Round prices properly
            tp_price_str = await self._round_price(symbol, tp_price)
            sl_price_str = await self._round_price(symbol, sl_price)
            
            self.logger.info(f"Managing {side} position for {symbol} entered at {entry_price} with ATR {atr}")
            self.logger.info(f"Setting TP: {tp_price_str}, SL: {sl_price_str}")
            
            # Place TP order
            tp_order = await self.order_manager.set_take_profit(symbol, tp_price_str)
            
            # Place SL order
            sl_order = await self.order_manager.set_stop_loss(symbol, sl_price_str)
            
            # Track the position for monitoring
            self.active_trades[symbol] = {
                "symbol": symbol,
                "entry_price": float(entry_price),
                "side": side,
                "atr": float(atr),
                "position_size": float(position_size),
                "entry_order_id": entry_order_id,
                "tp_order_id": tp_order.get("orderId", ""),
                "sl_order_id": sl_order.get("orderId", ""),
                "tp_price": float(tp_price),
                "sl_price": float(sl_price),
                "initial_sl_price": float(sl_price),
                "initial_tp_price": float(tp_price),
                "trailing_active": False,
                "best_price": float(entry_price),
                "timestamp": time.time()
            }
            
            return {
                "tp_order": tp_order,
                "sl_order": sl_order,
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
    
    async def _update_trailing_stop(self, symbol: str, current_price: float):
        """
        Update trailing stop based on current price movement
        
        Args:
            symbol: Trading symbol
            current_price: Current price for evaluation
            
        Returns:
            Boolean indicating if stop was updated
        """
        if symbol not in self.active_trades:
            return False
            
        trade = self.active_trades[symbol]
        side = trade["side"]
        entry_price = trade["entry_price"]
        atr = trade["atr"]
        initial_sl = trade["initial_sl_price"]
        initial_tp = trade["initial_tp_price"]
        best_price = trade["best_price"]
        
        # Check if trailing stop should be activated (50% to TP by default)
        if not trade["trailing_active"]:
            # For long positions
            if side == "Buy":
                # Calculate halfway point to TP
                activation_point = entry_price + (initial_tp - entry_price) * self.activation_threshold
                
                # If price has reached activation point
                if current_price >= activation_point:
                    trade["trailing_active"] = True
                    self.logger.info(f"Trailing stop activated for {symbol} at {current_price}")
                else:
                    # Not yet activated
                    return False
            
            # For short positions
            else:
                # Calculate halfway point to TP (price decreases in short)
                activation_point = entry_price - (entry_price - initial_tp) * self.activation_threshold
                
                # If price has reached activation point
                if current_price <= activation_point:
                    trade["trailing_active"] = True
                    self.logger.info(f"Trailing stop activated for {symbol} at {current_price}")
                else:
                    # Not yet activated
                    return False
        
        # Trailing stop is active, update if needed
        if side == "Buy":
            # Update best price if current price is better
            if current_price > best_price:
                trade["best_price"] = current_price
                
                # Calculate new stop price based on trail ATR multiple
                new_sl = current_price - (atr * self.trail_atr_mult)
                
                # Only move stop up, never down
                if new_sl > trade["sl_price"]:
                    old_sl = trade["sl_price"]
                    trade["sl_price"] = new_sl
                    
                    # Update stop loss order
                    try:
                        sl_price_str = await self._round_price(symbol, new_sl)
                        result = await self.order_manager.set_stop_loss(symbol, sl_price_str)
                        self.logger.info(f"Updated trailing stop for {symbol} from {old_sl} to {new_sl}")
                        return True
                    except Exception as e:
                        self.logger.error(f"Error updating trailing stop: {str(e)}")
                        return False
        
        else:  # Short position
            # Update best price if current price is better (lower for shorts)
            if current_price < best_price:
                trade["best_price"] = current_price
                
                # Calculate new stop price based on trail ATR multiple
                new_sl = current_price + (atr * self.trail_atr_mult)
                
                # Only move stop down, never up
                if new_sl < trade["sl_price"]:
                    old_sl = trade["sl_price"]
                    trade["sl_price"] = new_sl
                    
                    # Update stop loss order
                    try:
                        sl_price_str = await self._round_price(symbol, new_sl)
                        result = await self.order_manager.set_stop_loss(symbol, sl_price_str)
                        self.logger.info(f"Updated trailing stop for {symbol} from {old_sl} to {new_sl}")
                        return True
                    except Exception as e:
                        self.logger.error(f"Error updating trailing stop: {str(e)}")
                        return False
        
        return False
    
    async def _monitor_positions(self):
        """
        Continuously monitor positions and update trailing stops
        """
        self.logger.info("Position monitoring started")
        
        while self._running:
            try:
                # Process each active trade
                for symbol in list(self.active_trades.keys()):
                    # Skip if trailing stops are not enabled
                    if not self.trailing_enabled:
                        continue
                        
                    # Get current price
                    try:
                        current_price = await self.data_manager.get_latest_price(symbol)
                        if current_price:
                            self.last_prices[symbol] = current_price
                            
                            # Check if position still exists
                            positions = await self.order_manager.get_positions(symbol)
                            if not positions or float(positions[0].get("size", "0")) == 0:
                                self.logger.info(f"Position closed for {symbol}, removing from active trades")
                                if symbol in self.active_trades:
                                    del self.active_trades[symbol]
                                continue
                            
                            # Update trailing stop if needed
                            await self._update_trailing_stop(symbol, current_price)
                    
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
        Update the status of TP/SL orders when they fill or cancel
        
        Args:
            symbol: Trading symbol
            order_id: Order ID that was updated
            status: New status of the order
        """
        if symbol not in self.active_trades:
            return
            
        trade = self.active_trades[symbol]
        
        # If this is a TP order
        if order_id == trade.get("tp_order_id") and status == "Filled":
            self.logger.info(f"Take profit hit for {symbol} at {trade.get('tp_price')}")
            
            # Cancel the corresponding SL order
            if trade.get("sl_order_id"):
                try:
                    await self.order_manager.cancel_order(symbol, trade["sl_order_id"])
                    self.logger.info(f"Cancelled stop loss after TP hit for {symbol}")
                except Exception as e:
                    self.logger.error(f"Error cancelling SL after TP hit: {str(e)}")
            
            # Remove from active trades
            del self.active_trades[symbol]
        
        # If this is an SL order
        elif order_id == trade.get("sl_order_id") and status == "Filled":
            self.logger.info(f"Stop loss hit for {symbol} at {trade.get('sl_price')}")
            
            # Cancel the corresponding TP order
            if trade.get("tp_order_id"):
                try:
                    await self.order_manager.cancel_order(symbol, trade["tp_order_id"])
                    self.logger.info(f"Cancelled take profit after SL hit for {symbol}")
                except Exception as e:
                    self.logger.error(f"Error cancelling TP after SL hit: {str(e)}")
            
            # Remove from active trades
            del self.active_trades[symbol]