"""
Order Manager - Handles order placement, tracking, and management

This module provides the high-level interface for trading operations,
using the OrderManagerClient for API communication and adding business
logic on top for order decision making and tracking.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from ..utils.logger import Logger
from ..core.order_manager_client import OrderManagerClient


class OrderManager:
    """
    Order management system for trading operations
    
    Uses OrderManagerClient for API communication and adds business logic
    """
    
    def __init__(self, client, config, logger=None):
        """
        Initialize with client and configuration
        
        Args:
            client: BybitClientTransport instance
            config: Configuration dictionary
            logger: Optional Logger instance
        """
        self.logger = logger or Logger("OrderManager")
        self.logger.debug(f"→ __init__(client={client}, config_id={id(config)}, logger={logger})")
        
        self.client = client
        self.config = config
        
        # Initialize order client
        self.order_client = OrderManagerClient(self.client, self.logger, self.config)
        
        # Get configuration settings
        self.default_symbol = self.config.get('general', {}).get('trading', {}).get('default_symbol', "BTCUSDT")
        self.order_retry_count = self.config.get('execution', {}).get('order_retry_count', 3)
        self.order_retry_delay = self.config.get('execution', {}).get('order_retry_delay', 1.0)
        
        # Order tracking
        self.order_history = {}
        self.active_orders = {}
        self.order_updates = {}
        self.order_cache = {}
        
        # Maximum number of orders to track in history per symbol
        self.max_orders_per_symbol = 100
        
        self.logger.info(f"OrderManager initialized")
        self.logger.debug(f"← __init__ completed")
    
    def get_client(self) -> OrderManagerClient:
        """
        Get the underlying OrderManagerClient
        
        Returns:
            OrderManagerClient instance
        """
        self.logger.debug(f"→ get_client()")
        self.logger.debug(f"← get_client returned OrderManagerClient instance")
        return self.order_client
    
    async def place_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool = False, 
                           tp_price: Optional[float] = None, sl_price: Optional[float] = None) -> Dict:
        """
        Place a market order with TP/SL
        
        Args:
            symbol: Trading symbol
            side: 'Buy' or 'Sell'
            qty: Order quantity
            reduce_only: If True, order will only reduce position
            tp_price: Optional take profit price
            sl_price: Optional stop loss price
            
        Returns:
            Dictionary with order result
        """
        self.logger.debug(f"→ place_market_order(symbol={symbol}, side={side}, qty={qty}, reduce_only={reduce_only}, tp_price={tp_price}, sl_price={sl_price})")
        
        try:
            # Format quantity based on symbol
            qty_str = str(qty)
            
            # Apply retry logic for network reliability
            for attempt in range(self.order_retry_count):
                try:
                    self.logger.info(f"Placing {side} market order for {symbol}, qty={qty_str} (attempt {attempt+1}/{self.order_retry_count})")
                    
                    # Set up order parameters
                    order_params = {
                        "symbol": symbol,
                        "side": side,
                        "order_type": "Market",
                        "qty": qty_str,
                        "reduce_only": reduce_only
                    }
                    
                    # Add TP/SL if provided
                    if tp_price is not None:
                        order_params["take_profit"] = str(tp_price)
                    if sl_price is not None:
                        order_params["stop_loss"] = str(sl_price)
                    
                    # Place the order
                    result = self.order_client.place_active_order(**order_params)
                    
                    # Check for error
                    if "error" in result:
                        self.logger.error(f"Error placing order (attempt {attempt+1}): {result['error']}")
                        if attempt < self.order_retry_count - 1:
                            self.logger.info(f"Retrying order in {self.order_retry_delay}s...")
                            await asyncio.sleep(self.order_retry_delay)
                            continue
                    else:
                        # Order placed successfully
                        order_id = result.get("orderId")
                        self.logger.info(f"Order placed successfully: {order_id}")
                        
                        # Track order
                        if order_id:
                            self._track_order(symbol, order_id, side, qty_str, "Market", result)
                        
                        self.logger.debug(f"← place_market_order returned result with orderId={order_id}")
                        return result
                
                except Exception as e:
                    self.logger.error(f"Exception placing order (attempt {attempt+1}): {str(e)}")
                    if attempt < self.order_retry_count - 1:
                        await asyncio.sleep(self.order_retry_delay)
            
            # If we get here, all attempts failed
            error_result = {"error": f"Failed to place order after {self.order_retry_count} attempts"}
            self.logger.error(f"Failed to place order after {self.order_retry_count} attempts")
            self.logger.debug(f"← place_market_order returned error: {error_result}")
            return error_result
            
        except Exception as e:
            self.logger.error(f"Error placing market order: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← place_market_order returned error: {error_result}")
            return error_result
    
    async def place_limit_order(self, symbol: str, side: str, qty: float, price: float, 
                          time_in_force: str = "GoodTillCancel", reduce_only: bool = False,
                          tp_price: Optional[float] = None, sl_price: Optional[float] = None) -> Dict:
        """
        Place a limit order with TP/SL
        
        Args:
            symbol: Trading symbol
            side: 'Buy' or 'Sell'
            qty: Order quantity
            price: Limit price
            time_in_force: Order time in force
            reduce_only: If True, order will only reduce position
            tp_price: Optional take profit price
            sl_price: Optional stop loss price
            
        Returns:
            Dictionary with order result
        """
        self.logger.debug(f"→ place_limit_order(symbol={symbol}, side={side}, qty={qty}, price={price}, time_in_force={time_in_force}, reduce_only={reduce_only}, tp_price={tp_price}, sl_price={sl_price})")
        
        try:
            # Format quantity and price based on symbol
            qty_str = str(qty)
            price_str = str(price)
            
            # Apply retry logic for network reliability
            for attempt in range(self.order_retry_count):
                try:
                    self.logger.info(f"Placing {side} limit order for {symbol}, qty={qty_str}, price={price_str} (attempt {attempt+1}/{self.order_retry_count})")
                    
                    # Set up order parameters
                    order_params = {
                        "symbol": symbol,
                        "side": side,
                        "order_type": "Limit",
                        "qty": qty_str,
                        "price": price_str,
                        "time_in_force": time_in_force,
                        "reduce_only": reduce_only
                    }
                    
                    # Add TP/SL if provided
                    if tp_price is not None:
                        order_params["take_profit"] = str(tp_price)
                    if sl_price is not None:
                        order_params["stop_loss"] = str(sl_price)
                    
                    # Place the order
                    result = self.order_client.place_active_order(**order_params)
                    
                    # Check for error
                    if "error" in result:
                        self.logger.error(f"Error placing limit order (attempt {attempt+1}): {result['error']}")
                        if attempt < self.order_retry_count - 1:
                            self.logger.info(f"Retrying order in {self.order_retry_delay}s...")
                            await asyncio.sleep(self.order_retry_delay)
                            continue
                    else:
                        # Order placed successfully
                        order_id = result.get("orderId")
                        self.logger.info(f"Limit order placed successfully: {order_id}")
                        
                        # Track order
                        if order_id:
                            self._track_order(symbol, order_id, side, qty_str, "Limit", result, price_str)
                        
                        self.logger.debug(f"← place_limit_order returned result with orderId={order_id}")
                        return result
                
                except Exception as e:
                    self.logger.error(f"Exception placing limit order (attempt {attempt+1}): {str(e)}")
                    if attempt < self.order_retry_count - 1:
                        await asyncio.sleep(self.order_retry_delay)
            
            # If we get here, all attempts failed
            error_result = {"error": f"Failed to place limit order after {self.order_retry_count} attempts"}
            self.logger.error(f"Failed to place limit order after {self.order_retry_count} attempts")
            self.logger.debug(f"← place_limit_order returned error: {error_result}")
            return error_result
            
        except Exception as e:
            self.logger.error(f"Error placing limit order: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← place_limit_order returned error: {error_result}")
            return error_result
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """
        Cancel an active order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            Dictionary with cancel result
        """
        self.logger.debug(f"→ cancel_order(symbol={symbol}, order_id={order_id})")
        
        try:
            # Apply retry logic for network reliability
            for attempt in range(self.order_retry_count):
                try:
                    self.logger.info(f"Cancelling order {order_id} for {symbol} (attempt {attempt+1}/{self.order_retry_count})")
                    
                    # Cancel the order
                    result = self.order_client.cancel_order(symbol, order_id)
                    
                    # Check for error
                    if "error" in result:
                        self.logger.error(f"Error cancelling order (attempt {attempt+1}): {result['error']}")
                        if attempt < self.order_retry_count - 1:
                            self.logger.info(f"Retrying cancel in {self.order_retry_delay}s...")
                            await asyncio.sleep(self.order_retry_delay)
                            continue
                    else:
                        # Order cancelled successfully
                        self.logger.info(f"Order {order_id} cancelled successfully")
                        
                        # Update order tracking
                        if symbol in self.active_orders and order_id in self.active_orders[symbol]:
                            # Move to order history
                            self._move_to_history(symbol, order_id, "Cancelled")
                        
                        self.logger.debug(f"← cancel_order returned: {result}")
                        return result
                
                except Exception as e:
                    self.logger.error(f"Exception cancelling order (attempt {attempt+1}): {str(e)}")
                    if attempt < self.order_retry_count - 1:
                        await asyncio.sleep(self.order_retry_delay)
            
            # If we get here, all attempts failed
            error_result = {"error": f"Failed to cancel order after {self.order_retry_count} attempts"}
            self.logger.error(f"Failed to cancel order after {self.order_retry_count} attempts")
            self.logger.debug(f"← cancel_order returned error: {error_result}")
            return error_result
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← cancel_order returned error: {error_result}")
            return error_result
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get all open orders
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            List of open orders
        """
        self.logger.debug(f"→ get_open_orders(symbol={symbol})")
        
        try:
            # Use the order client to get open orders
            open_orders = self.order_client.get_open_orders(symbol)
            
            # Update active orders tracking
            for order in open_orders:
                order_symbol = order.get("symbol")
                order_id = order.get("orderId")
                
                if order_symbol and order_id:
                    # Add to active orders if not already tracked
                    if order_symbol not in self.active_orders:
                        self.active_orders[order_symbol] = {}
                    
                    if order_id not in self.active_orders[order_symbol]:
                        self.active_orders[order_symbol][order_id] = {
                            "order": order,
                            "timestamp": time.time(),
                            "status": order.get("orderStatus")
                        }
                    else:
                        # Update existing entry
                        self.active_orders[order_symbol][order_id]["order"] = order
                        self.active_orders[order_symbol][order_id]["status"] = order.get("orderStatus")
            
            self.logger.debug(f"← get_open_orders returned {len(open_orders)} orders")
            return open_orders
            
        except Exception as e:
            self.logger.error(f"Error getting open orders: {str(e)}")
            self.logger.debug(f"← get_open_orders returned empty list (error)")
            return []
    
    async def get_order_status(self, symbol: str, order_id: str) -> Dict:
        """
        Get detailed order status
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to query
            
        Returns:
            Dictionary with order status
        """
        self.logger.debug(f"→ get_order_status(symbol={symbol}, order_id={order_id})")
        
        try:
            # Check cache first for efficiency
            if symbol in self.order_cache and order_id in self.order_cache[symbol]:
                cache_entry = self.order_cache[symbol][order_id]
                cache_age = time.time() - cache_entry.get("timestamp", 0)
                
                # Use cache if recent enough
                if cache_age < 5.0:  # 5 second cache TTL
                    self.logger.debug(f"Using cached order status for {order_id}")
                    self.logger.debug(f"← get_order_status returned cached status")
                    return cache_entry.get("order", {})
            
            # Get fresh order status
            order_info = self.order_client.get_order(symbol, order_id)
            
            # Update cache
            if not self.order_cache.get(symbol):
                self.order_cache[symbol] = {}
            
            self.order_cache[symbol][order_id] = {
                "order": order_info,
                "timestamp": time.time()
            }
            
            # Update tracking if needed
            order_status = order_info.get("orderStatus")
            if order_status in ["Filled", "Cancelled", "Rejected"]:
                # Move to history if this is a final state
                self._move_to_history(symbol, order_id, order_status)
            
            self.logger.debug(f"← get_order_status returned fresh status: {order_status}")
            return order_info
            
        except Exception as e:
            self.logger.error(f"Error getting order status: {str(e)}")
            error_result = {"error": str(e), "status": "Error"}
            self.logger.debug(f"← get_order_status returned error: {error_result}")
            return error_result
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get all open positions
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            List of positions
        """
        self.logger.debug(f"→ get_positions(symbol={symbol})")
        
        try:
            # Get positions from order client
            positions = self.order_client.get_positions(symbol)
            
            self.logger.debug(f"← get_positions returned {len(positions)} positions")
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            self.logger.debug(f"← get_positions returned empty list (error)")
            return []
    
    async def close_position(self, symbol: str) -> Dict:
        """
        Close an entire position
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with close result
        """
        self.logger.debug(f"→ close_position(symbol={symbol})")
        
        try:
            # Apply retry logic for network reliability
            for attempt in range(self.order_retry_count):
                try:
                    self.logger.info(f"Closing position for {symbol} (attempt {attempt+1}/{self.order_retry_count})")
                    
                    # Close the position
                    result = self.order_client.close_position(symbol)
                    
                    # Check for error
                    if "error" in result:
                        self.logger.error(f"Error closing position (attempt {attempt+1}): {result['error']}")
                        if attempt < self.order_retry_count - 1:
                            self.logger.info(f"Retrying close in {self.order_retry_delay}s...")
                            await asyncio.sleep(self.order_retry_delay)
                            continue
                    else:
                        # Position closed successfully or no position to close
                        if "info" in result and "No position to close" in result["info"]:
                            self.logger.info(f"No position to close for {symbol}")
                        else:
                            self.logger.info(f"Position closed successfully for {symbol}")
                        
                        self.logger.debug(f"← close_position returned: {result}")
                        return result
                
                except Exception as e:
                    self.logger.error(f"Exception closing position (attempt {attempt+1}): {str(e)}")
                    if attempt < self.order_retry_count - 1:
                        await asyncio.sleep(self.order_retry_delay)
            
            # If we get here, all attempts failed
            error_result = {"error": f"Failed to close position after {self.order_retry_count} attempts"}
            self.logger.error(f"Failed to close position after {self.order_retry_count} attempts")
            self.logger.debug(f"← close_position returned error: {error_result}")
            return error_result
            
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← close_position returned error: {error_result}")
            return error_result
    
    async def set_position_tpsl(self, symbol: str, tp_price: Optional[float] = None, sl_price: Optional[float] = None) -> Dict:
        """
        Set take profit and stop loss for an open position
        
        Args:
            symbol: Trading symbol
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with TP/SL result
        """
        self.logger.debug(f"→ set_position_tpsl(symbol={symbol}, tp_price={tp_price}, sl_price={sl_price})")
        
        try:
            # Get current position to check if it exists
            positions = self.order_client.get_positions(symbol)
            
            if not positions or float(positions[0].get("size", "0")) == 0:
                self.logger.warning(f"No position found for {symbol}, cannot set TP/SL")
                result = {"error": "No position found"}
                self.logger.debug(f"← set_position_tpsl returned error: {result}")
                return result
            
            # Get position index (0 for one-way mode)
            position = positions[0]
            position_idx = int(position.get("positionIdx", 0))
            
            # Apply retry logic for network reliability
            for attempt in range(self.order_retry_count):
                try:
                    self.logger.info(f"Setting TP/SL for {symbol} (attempt {attempt+1}/{self.order_retry_count})")
                    
                    # Format TP/SL prices
                    tp_price_str = str(tp_price) if tp_price is not None else None
                    sl_price_str = str(sl_price) if sl_price is not None else None
                    
                    # Set TP/SL
                    result = self.order_client.set_position_tpsl(
                        symbol=symbol,
                        position_idx=position_idx,
                        tp_price=tp_price_str,
                        sl_price=sl_price_str
                    )
                    
                    # Check for error
                    if "error" in result:
                        self.logger.error(f"Error setting TP/SL (attempt {attempt+1}): {result['error']}")
                        if attempt < self.order_retry_count - 1:
                            self.logger.info(f"Retrying in {self.order_retry_delay}s...")
                            await asyncio.sleep(self.order_retry_delay)
                            continue
                    else:
                        # TP/SL set successfully
                        self.logger.info(f"TP/SL set successfully for {symbol}")
                        self.logger.debug(f"← set_position_tpsl returned: {result}")
                        return result
                
                except Exception as e:
                    self.logger.error(f"Exception setting TP/SL (attempt {attempt+1}): {str(e)}")
                    if attempt < self.order_retry_count - 1:
                        await asyncio.sleep(self.order_retry_delay)
            
            # If we get here, all attempts failed
            error_result = {"error": f"Failed to set TP/SL after {self.order_retry_count} attempts"}
            self.logger.error(f"Failed to set TP/SL after {self.order_retry_count} attempts")
            self.logger.debug(f"← set_position_tpsl returned error: {error_result}")
            return error_result
            
        except Exception as e:
            self.logger.error(f"Error setting position TP/SL: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← set_position_tpsl returned error: {error_result}")
            return error_result
    
    def _track_order(self, symbol: str, order_id: str, side: str, qty: str, order_type: str, 
                    order_data: Dict, price: Optional[str] = None) -> None:
        """
        Track a new order in the active orders list
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            side: Order side
            qty: Order quantity
            order_type: Order type
            order_data: Full order data
            price: Optional price for limit orders
        """
        self.logger.debug(f"→ _track_order(symbol={symbol}, order_id={order_id}, side={side}, qty={qty}, order_type={order_type}, price={price})")
        
        # Create order tracking entry
        order_entry = {
            "symbol": symbol,
            "orderId": order_id,
            "side": side,
            "qty": qty,
            "orderType": order_type,
            "price": price,
            "timestamp": time.time(),
            "status": "Created",
            "order_data": order_data
        }
        
        # Add to active orders
        if symbol not in self.active_orders:
            self.active_orders[symbol] = {}
            
        self.active_orders[symbol][order_id] = order_entry
        
        self.logger.debug(f"Order {order_id} added to tracking")
        self.logger.debug(f"← _track_order completed")
    
    def _move_to_history(self, symbol: str, order_id: str, final_status: str) -> None:
        """
        Move an order from active to history
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            final_status: Final order status
        """
        self.logger.debug(f"→ _move_to_history(symbol={symbol}, order_id={order_id}, final_status={final_status})")
        
        # Check if order is in active orders
        if symbol in self.active_orders and order_id in self.active_orders[symbol]:
            # Get order data
            order_data = self.active_orders[symbol][order_id]
            
            # Update status
            order_data["status"] = final_status
            order_data["final_timestamp"] = time.time()
            
            # Add to history
            if symbol not in self.order_history:
                self.order_history[symbol] = []
                
            self.order_history[symbol].append(order_data)
            
            # Limit history size
            if len(self.order_history[symbol]) > self.max_orders_per_symbol:
                self.order_history[symbol] = self.order_history[symbol][-self.max_orders_per_symbol:]
                
            # Remove from active orders
            del self.active_orders[symbol][order_id]
            
            self.logger.debug(f"Order {order_id} moved to history with status {final_status}")
        
        self.logger.debug(f"← _move_to_history completed")
    
    async def sync_order_status(self) -> None:
        """
        Synchronize the status of all active orders
        """
        self.logger.debug(f"→ sync_order_status()")
        
        try:
            # Get all open orders
            open_orders = await self.get_open_orders()
            
            # Create mapping of open orders
            open_order_map = {}
            for order in open_orders:
                order_symbol = order.get("symbol")
                order_id = order.get("orderId")
                
                if order_symbol and order_id:
                    if order_symbol not in open_order_map:
                        open_order_map[order_symbol] = {}
                    open_order_map[order_symbol][order_id] = order
            
            # Check each tracked active order
            for symbol in list(self.active_orders.keys()):
                for order_id in list(self.active_orders[symbol].keys()):
                    # Check if order is still open
                    if (symbol in open_order_map and 
                        order_id in open_order_map[symbol]):
                        # Update status
                        order_status = open_order_map[symbol][order_id].get("orderStatus")
                        self.active_orders[symbol][order_id]["status"] = order_status
                        self.active_orders[symbol][order_id]["order_data"] = open_order_map[symbol][order_id]
                    else:
                        # Order not found in open orders, check final status
                        order_info = await self.get_order_status(symbol, order_id)
                        order_status = order_info.get("orderStatus")
                        
                        if order_status in ["Filled", "Cancelled", "Rejected"]:
                            # Move to history if this is a final state
                            self._move_to_history(symbol, order_id, order_status)
                        elif order_status == "NotFound":
                            # Order not found, assume cancelled
                            self._move_to_history(symbol, order_id, "Cancelled")
            
            self.logger.debug(f"← sync_order_status completed")
            
        except Exception as e:
            self.logger.error(f"Error synchronizing order status: {str(e)}")
            self.logger.debug(f"← sync_order_status exited with error")
    
    def get_active_orders_count(self, symbol: Optional[str] = None) -> int:
        """
        Get count of active orders
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            Count of active orders
        """
        self.logger.debug(f"→ get_active_orders_count(symbol={symbol})")
        
        count = 0
        
        if symbol:
            # Count only for specified symbol
            if symbol in self.active_orders:
                count = len(self.active_orders[symbol])
        else:
            # Count all active orders
            for symbol_orders in self.active_orders.values():
                count += len(symbol_orders)
        
        self.logger.debug(f"← get_active_orders_count returned {count}")
        return count
    
    async def create_tp_sl_orders(self, symbol: str, entry_price: float, position_side: str, 
                           tp_percent: float = 0.03, sl_percent: float = 0.02) -> Dict:
        """
        Create TP/SL for a position using percentage
        
        Args:
            symbol: Trading symbol
            entry_price: Position entry price
            position_side: Position side (Buy/Sell)
            tp_percent: Take profit percentage
            sl_percent: Stop loss percentage
            
        Returns:
            Dictionary with TP/SL result
        """
        self.logger.debug(f"→ create_tp_sl_orders(symbol={symbol}, entry_price={entry_price}, position_side={position_side}, tp_percent={tp_percent}, sl_percent={sl_percent})")
        
        try:
            # Calculate TP/SL prices
            if position_side == "Buy":
                tp_price = entry_price * (1 + tp_percent)
                sl_price = entry_price * (1 - sl_percent)
            else:
                tp_price = entry_price * (1 - tp_percent)
                sl_price = entry_price * (1 + sl_percent)
            
            self.logger.info(f"Setting TP at {tp_price}, SL at {sl_price} for {symbol}")
            
            # Set TP/SL
            result = await self.set_position_tpsl(symbol, tp_price, sl_price)
            
            self.logger.debug(f"← create_tp_sl_orders returned: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error creating TP/SL orders: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← create_tp_sl_orders returned error: {error_result}")
            return error_result