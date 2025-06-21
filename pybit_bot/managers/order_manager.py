"""
Order Manager - Handles order creation, tracking, and execution
"""

import logging
import time
import uuid
import json
import asyncio
import os
import csv
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from pybit_bot.core.client import BybitClient
from pybit_bot.core.order_manager_client import OrderManagerClient
from pybit_bot.utils.logger import Logger
from pybit_bot.exceptions import InvalidOrderError  # Remove OrderExecutionError

# Define OrderExecutionError locally
class OrderExecutionError(Exception):
    """Exception raised when an order fails to execute"""
    pass


class OrderManager:
    """
    OrderManager handles all trading execution, order placement,
    and position tracking
    """
    
    def __init__(self, client: BybitClient, config: Dict, logger=None, data_manager=None):
        """
        Initialize the order manager.
        
        Args:
            client: BybitClient instance
            config: Configuration dictionary for execution settings
            logger: Optional logger instance
            data_manager: DataManager instance for market data
        """
        self.client = client
        self.config = config
        self.logger = logger or Logger("OrderManager")
        self.data_manager = data_manager  # Store the data_manager for ATR calculations
        
        # Initialize OrderManagerClient
        self.order_client = OrderManagerClient(client, logger, config)
        
        self.active_orders = {}  # Track active orders
        self.order_history = {}  # Track order history
        self.positions = {}      # Track current positions
        self.pending_tpsl = {}   # Track orders waiting for TP/SL to be set
        self.processed_order_ids = set()  # Track already processed orders
        
        # Extract configuration
        self.position_config = config.get('position_sizing', {})
        self.risk_config = config.get('risk_management', {})
        self.order_config = config.get('order_execution', {})
        
        # Settings for post-order delay to avoid race conditions
        self.post_order_delay = 0.5  # seconds
        
        # Track last synchronization time
        self.last_sync_time = 0
        self.sync_interval = 5  # seconds
        
        self.logger.info("OrderManager initialized")
    
    async def initialize(self):
        """
        Initialize order manager, load existing positions and orders.
        """
        try:
            # Synchronize positions immediately on startup
            await self.synchronize_positions()
            
            # Log loaded state
            self.logger.info(f"Loaded {len(self.positions)} active positions")
            
            return True
        except Exception as e:
            self.logger.error(f"Error initializing OrderManager: {str(e)}")
            return False
    
    async def close(self):
        """
        Clean shutdown of order manager.
        """
        self.logger.info("Shutting down OrderManager")
        return True
    
    async def synchronize_positions(self):
        """
        Synchronize internal position state with exchange data.
        Should be called periodically and before critical operations.
        """
        try:
            current_time = time.time()
            
            # Only synchronize if enough time has passed since last sync
            if current_time - self.last_sync_time < self.sync_interval:
                return self.positions
            
            self.logger.info("Synchronizing positions with exchange...")
            
            # Use OrderManagerClient to get current positions
            active_positions = self.order_client.synchronize_positions()
            
            # Update internal state
            old_positions = set(self.positions.keys())
            new_positions = set(active_positions.keys())
            
            # Log closed positions
            for symbol in old_positions - new_positions:
                self.logger.info(f"Position closed for {symbol}, removing from active trades")
                
            # Update internal positions dictionary
            self.positions = active_positions
            self.last_sync_time = current_time
            
            return self.positions
            
        except Exception as e:
            self.logger.error(f"Error synchronizing positions: {str(e)}")
            return self.positions
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get current positions from exchange with synchronization.
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            List of position dictionaries
        """
        try:
            # Synchronize positions first
            await self.synchronize_positions()
            
            # Return positions for specific symbol if requested
            if symbol:
                if symbol in self.positions:
                    return [self.positions[symbol]]
                return []
            
            # Return all positions
            return list(self.positions.values())
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            return []
    
    async def position_exists(self, symbol: str) -> bool:
        """
        Check if an active position exists for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if position exists with non-zero size, False otherwise
        """
        try:
            # Synchronize positions first
            await self.synchronize_positions()
            
            # Check if position exists with non-zero size
            return symbol in self.positions
            
        except Exception as e:
            self.logger.error(f"Error checking position existence: {str(e)}")
            return False
    
    async def get_account_balance(self) -> Dict:
        """
        Get account balance from exchange.
        
        Returns:
            Dictionary with balance information
        """
        try:
            # Use OrderManagerClient to get account balance
            balance = self.order_client.get_account_balance()
            return balance
            
        except Exception as e:
            self.logger.error(f"Error getting account balance: {str(e)}")
            return {"totalAvailableBalance": "0"}
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open orders from exchange.
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            List of open orders
        """
        try:
            # Use OrderManagerClient to get open orders
            orders = self.order_client.get_open_orders(symbol)
            
            # Update internal state
            for order in orders:
                order_id = order.get("orderId")
                if order_id:
                    self.active_orders[order_id] = order
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Error getting open orders: {str(e)}")
            return []
    
    def get_open_orders_sync(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Synchronous version of get_open_orders for UI purposes.
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            List of open orders
        """
        try:
            # Use OrderManagerClient to get open orders
            return self.order_client.get_open_orders(symbol)
            
        except Exception as e:
            self.logger.error(f"Error getting open orders (sync): {str(e)}")
            return []
    
    async def calculate_position_size(self, symbol: str, usdt_amount: float, price: Optional[float] = None) -> str:
        """
        Calculate position size based on USDT amount.
        
        Args:
            symbol: Trading symbol
            usdt_amount: Amount in USDT to use for position
            price: Optional price to use (if None, gets latest price)
            
        Returns:
            Quantity as string
        """
        try:
            # Use OrderManagerClient to calculate position size
            return self.order_client.calculate_position_size(symbol, usdt_amount, price)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            return "0.01"  # Default fallback
    
    async def get_position_fill_info(self, symbol: str, order_id: str) -> Dict:
        """
        Get fill information for a position.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            
        Returns:
            Dictionary with fill information
        """
        try:
            # Use OrderManagerClient to get order fill info
            fill_info = self.order_client.get_order_fill_info(symbol, order_id)
            
            # Log the fill info
            self.logger.info(f"Fill info for {order_id}: {fill_info}")
            
            return fill_info
            
        except Exception as e:
            self.logger.error(f"Error getting position fill info: {str(e)}")
            return {"filled": False, "error": str(e)}
    
    async def enter_position_market(self, symbol: str, side: str, qty: float, tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Enter a position with a market order, optionally with TP/SL.
        
        Args:
            symbol: Trading symbol
            side: "Buy" or "Sell"
            qty: Position size
            tp_price: Optional take profit price
            sl_price: Optional stop loss price
            
        Returns:
            Dictionary with order results
        """
        try:
            # Log the entry
            direction = "LONG" if side == "Buy" else "SHORT"
            self.logger.info(f"Entering {direction} position for {symbol}, qty={qty}")
            
            # Check if we should place a market order with embedded TP/SL
            use_oco = self.order_config.get("use_oco_orders", True)
            
            if use_oco and tp_price and sl_price:
                # Use the enhanced OCO order method for atomic TP/SL
                result = self.order_client.place_oco_order(
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
            else:
                # Place a regular market order without TP/SL
                result = self.order_client.enter_position_market(
                    symbol=symbol,
                    side=side,
                    qty=qty
                )
            
            # Check for errors
            if "error" in result:
                self.logger.error(f"Error placing {direction} order for {symbol}: {result['error']}")
                return {"error": result["error"]}
            
            # Log the order result
            self.logger.info(f"Order placed: {side} Market for {symbol}")
            self.logger.info(f"{direction} order result: {result}")
            
            # Small delay to allow order to process
            await asyncio.sleep(self.post_order_delay)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error entering position: {str(e)}")
            return {"error": str(e)}
    
    async def set_position_tpsl(self, symbol: str, position_idx: int, tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Set TP/SL for an existing position.
        
        Args:
            symbol: Trading symbol
            position_idx: Position index (0 for one-way mode)
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with TP/SL setting result
        """
        try:
            self.logger.info(f"Setting TP/SL for {symbol} position: TP={tp_price}, SL={sl_price}")
            
            # First check if position exists
            if not await self.position_exists(symbol):
                self.logger.warning(f"No active position for {symbol}, cannot set TP/SL")
                return {"error": "No active position", "symbol": symbol}
            
            # Use the safe TP/SL method from OrderManagerClient
            result = self.order_client.set_position_tpsl_safe(symbol, tp_price, sl_price)
            
            if result.get("status") == "skipped":
                self.logger.info(f"TP/SL already set to requested values for {symbol}")
                return {"success": True, "message": "No changes needed", "symbol": symbol}
            
            # Check for errors
            if "error" in result:
                self.logger.error(f"Error setting TP/SL: {result['error']}")
                return {"error": result["error"]}
            
            self.logger.info(f"TP/SL set successfully for {symbol}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error setting position TP/SL: {str(e)}")
            return {"error": str(e)}
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """
        Cancel an order.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            Dictionary with cancel result
        """
        try:
            # Use OrderManagerClient to cancel order
            result = self.order_client.cancel_order(symbol, order_id)
            
            # Check for errors
            if "error" in result:
                self.logger.error(f"Error cancelling order: {result['error']}")
                return {"error": result["error"]}
            
            # Remove from active orders
            if order_id in self.active_orders:
                del self.active_orders[order_id]
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return {"error": str(e)}
    
    async def close_position(self, symbol: str) -> Dict:
        """
        Close an entire position with a market order.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with close result
        """
        try:
            # First check if position exists
            if not await self.position_exists(symbol):
                self.logger.info(f"No position to close for {symbol}")
                return {"info": "No position to close"}
            
            # Use OrderManagerClient to close position
            result = self.order_client.close_position(symbol)
            
            # Wait for position to close
            await asyncio.sleep(1.0)
            
            # Synchronize positions to update internal state
            await self.synchronize_positions()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            return {"error": str(e)}
    
    async def handle_filled_order(self, symbol: str, order_id: str, fill_info: Dict) -> Dict:
        """
        Handle a filled order - setting TP/SL and updating position tracking.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            fill_info: Fill information dictionary
            
        Returns:
            Dictionary with handling result
        """
        try:
            # Check if we've already processed this order
            if order_id in self.processed_order_ids:
                self.logger.info(f"Order {order_id} already processed, skipping")
                return {"status": "already_processed"}
            
            # Mark as processed
            self.processed_order_ids.add(order_id)
            
            # Get fill details
            fill_price = fill_info.get("fill_price", 0)
            side = fill_info.get("side", "")
            direction = "LONG" if side == "Buy" else "SHORT"
            
            self.logger.info(f"Handling filled {direction} order {order_id} at price {fill_price}")
            
            # Check if position exists
            position_exists = await self.position_exists(symbol)
            if not position_exists:
                self.logger.warning(f"Position for {symbol} no longer exists, skipping TP/SL")
                return {"status": "position_closed"}
            
            # If TP/SL needs to be set, do it here
            # This would be needed if we didn't use OCO orders
            # For now, we'll skip this as we're using OCO orders
            
            return {"status": "success", "message": "Order handled successfully"}
            
        except Exception as e:
            self.logger.error(f"Error handling filled order: {str(e)}")
            return {"error": str(e)}
    
    async def execute_signal(self, symbol: str, side: str, qty: float, tp_price: Optional[float] = None, sl_price: Optional[float] = None) -> Dict:
        """
        Execute a trading signal with full TP/SL handling.
        
        Args:
            symbol: Trading symbol
            side: "Buy" or "Sell"
            qty: Position size
            tp_price: Optional take profit price
            sl_price: Optional stop loss price
            
        Returns:
            Dictionary with execution result
        """
        try:
            # Check if symbol already has a position
            has_position = await self.position_exists(symbol)
            if has_position:
                # Close existing position first
                self.logger.info(f"Closing existing position for {symbol} before new entry")
                close_result = await self.close_position(symbol)
                
                # Add delay to ensure position is closed
                await asyncio.sleep(2.0)
                
                # Re-check position existence
                still_has_position = await self.position_exists(symbol)
                if still_has_position:
                    self.logger.warning(f"Failed to close existing position for {symbol}, cannot enter new position")
                    return {"error": "Failed to close existing position"}
            
            # Format TP/SL prices if provided
            tp_price_str = None
            sl_price_str = None
            
            if tp_price:
                tp_price_str = self.order_client._round_price(symbol, tp_price)
            
            if sl_price:
                sl_price_str = self.order_client._round_price(symbol, sl_price)
            
            # Enter position with OCO order (TP/SL included atomically)
            result = await self.enter_position_market(
                symbol=symbol,
                side=side,
                qty=qty,
                tp_price=tp_price_str,
                sl_price=sl_price_str
            )
            
            # Check for errors
            if "error" in result:
                self.logger.error(f"Error executing signal: {result['error']}")
                return {"error": result["error"]}
            
            # Get order ID
            order_id = result.get("orderId", "")
            
            # Mark this order as processed to prevent duplicate TP/SL setting
            if order_id:
                self.processed_order_ids.add(order_id)
            
            # Synchronize positions to update internal state
            await self.synchronize_positions()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing signal: {str(e)}")
            return {"error": str(e)}