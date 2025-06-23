"""
Order Manager Client module.

This module provides a wrapper around the Bybit client for order management.
It handles order placement, tracking, and status updates with better error handling
and reconnection logic.
"""

import os
import time
import json
import asyncio
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union

from .client import BybitClientTransport
from ..utils.logger import Logger


class OrderManagerClient:
    """
    OrderManagerClient provides a high-level interface for managing orders.
    
    It handles:
    - Order placement (market, limit, etc.)
    - Order status tracking
    - Position information
    - Instrument metadata caching
    """
    
    def __init__(self, transport: BybitClientTransport, logger=None, config=None):
        """
        Initialize the OrderManagerClient.
        
        Args:
            transport: BybitClientTransport instance
            logger: Logger instance (optional)
            config: Configuration dictionary (optional)
        """
        self.logger = logger or Logger("OrderClient")
        self.logger.debug(f"ENTER __init__(transport={transport}, logger={logger}, config={config})")
        
        self.transport = transport
        self.config = config or {}
        
        # Bybit category
        self.category = "linear"  # USDT Perpetual is in linear category
        
        # Cached instrument information
        self.instruments_info = {}
        self.instruments_precision = {}
        self.price_scales = {}
        self.qty_scales = {}
        self.min_order_qty = {}
        
        # Order tracking
        self.active_orders = {}
        self.filled_orders = {}
        self.cancelled_orders = {}
        
        # Fetch instrument info to set up the cache
        self.logger.debug("Fetching instruments info for cache")
        resp = self.get_instruments_info()
        if resp:
            instruments_count = len(resp.get('list', []))
            self.logger.info(f"Cached info for {instruments_count} instruments")
            
            # Log a few sample symbols for verification
            sample_symbols = [item.get('symbol') for item in resp.get('list', [])[:3]]
            self.logger.debug(f"Sample symbols: {sample_symbols}")
            
        self.logger.debug(f"EXIT __init__ completed")
    
    async def place_market_order(self, symbol: str, side: str, qty: float, 
                          reduce_only: bool = False, tp_price: Optional[float] = None, 
                          sl_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Place a market order.
        
        Args:
            symbol: Trading symbol
            side: Order side ("Buy" or "Sell")
            qty: Order quantity
            reduce_only: Whether the order should only reduce position
            tp_price: Take profit price (optional)
            sl_price: Stop loss price (optional)
            
        Returns:
            Response dictionary
        """
        self.logger.debug(f"ENTER place_market_order(symbol={symbol}, side={side}, qty={qty}, reduce_only={reduce_only}, tp_price={tp_price}, sl_price={sl_price})")
        
        try:
            # Prepare order parameters
            params = {
                "category": self.category,
                "symbol": symbol,
                "side": side,
                "orderType": "Market",
                "qty": self._format_quantity(symbol, qty),
                "reduceOnly": reduce_only,
                "timeInForce": "GTC"
            }
            
            # Add take profit and stop loss if provided
            if tp_price:
                params["takeProfit"] = self._format_price(symbol, tp_price)
            
            if sl_price:
                params["stopLoss"] = self._format_price(symbol, sl_price)
            
            # Generate client order ID
            client_order_id = f"mkt_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            params["orderLinkId"] = client_order_id
            
            # Send order request
            self.logger.info(f"Placing {side} market order for {symbol}: {qty} units")
            response = await self.transport.place_order(params)
            
            # Process response
            if response.get("retCode") == 0:
                order_id = response.get("result", {}).get("orderId")
                self.logger.info(f"Market order placed successfully: {order_id}")
                
                # Add to active orders
                self.active_orders[order_id] = {
                    "symbol": symbol,
                    "side": side,
                    "type": "Market",
                    "qty": qty,
                    "status": "New",
                    "client_order_id": client_order_id,
                    "create_time": int(time.time() * 1000)
                }
                
                return {
                    "orderId": order_id,
                    "symbol": symbol,
                    "status": "New"
                }
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to place market order: {error_msg}")
                return {"error": error_msg}
            
        except Exception as e:
            self.logger.error(f"Error placing market order: {str(e)}")
            return {"error": str(e)}
        finally:
            self.logger.debug(f"EXIT place_market_order completed")
    
    async def place_limit_order(self, symbol: str, side: str, qty: float, price: float,
                         reduce_only: bool = False, post_only: bool = False,
                         tp_price: Optional[float] = None, sl_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Place a limit order.
        
        Args:
            symbol: Trading symbol
            side: Order side ("Buy" or "Sell")
            qty: Order quantity
            price: Limit price
            reduce_only: Whether the order should only reduce position
            post_only: Whether the order should be post-only
            tp_price: Take profit price (optional)
            sl_price: Stop loss price (optional)
            
        Returns:
            Response dictionary
        """
        self.logger.debug(f"ENTER place_limit_order(symbol={symbol}, side={side}, qty={qty}, price={price}, reduce_only={reduce_only}, post_only={post_only}, tp_price={tp_price}, sl_price={sl_price})")
        
        try:
            # Prepare order parameters
            params = {
                "category": self.category,
                "symbol": symbol,
                "side": side,
                "orderType": "Limit",
                "qty": self._format_quantity(symbol, qty),
                "price": self._format_price(symbol, price),
                "reduceOnly": reduce_only,
                "timeInForce": "PostOnly" if post_only else "GTC"
            }
            
            # Add take profit and stop loss if provided
            if tp_price:
                params["takeProfit"] = self._format_price(symbol, tp_price)
            
            if sl_price:
                params["stopLoss"] = self._format_price(symbol, sl_price)
            
            # Generate client order ID
            client_order_id = f"lmt_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            params["orderLinkId"] = client_order_id
            
            # Send order request
            self.logger.info(f"Placing {side} limit order for {symbol}: {qty} units at {price}")
            response = await self.transport.place_order(params)
            
            # Process response
            if response.get("retCode") == 0:
                order_id = response.get("result", {}).get("orderId")
                self.logger.info(f"Limit order placed successfully: {order_id}")
                
                # Add to active orders
                self.active_orders[order_id] = {
                    "symbol": symbol,
                    "side": side,
                    "type": "Limit",
                    "qty": qty,
                    "price": price,
                    "status": "New",
                    "client_order_id": client_order_id,
                    "create_time": int(time.time() * 1000)
                }
                
                return {
                    "orderId": order_id,
                    "symbol": symbol,
                    "status": "New"
                }
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to place limit order: {error_msg}")
                return {"error": error_msg}
            
        except Exception as e:
            self.logger.error(f"Error placing limit order: {str(e)}")
            return {"error": str(e)}
        finally:
            self.logger.debug(f"EXIT place_limit_order completed")
    
    async def place_stop_order(self, symbol: str, side: str, qty: float, trigger_price: float,
                        base_price: Optional[float] = None, reduce_only: bool = True,
                        close_on_trigger: bool = True) -> Dict[str, Any]:
        """
        Place a stop order.
        
        Args:
            symbol: Trading symbol
            side: Order side ("Buy" or "Sell")
            qty: Order quantity
            trigger_price: Stop trigger price
            base_price: Base price for the order (if None, places a market stop)
            reduce_only: Whether the order should only reduce position
            close_on_trigger: Whether the order should close the position
            
        Returns:
            Response dictionary
        """
        self.logger.debug(f"ENTER place_stop_order(symbol={symbol}, side={side}, qty={qty}, trigger_price={trigger_price}, base_price={base_price}, reduce_only={reduce_only}, close_on_trigger={close_on_trigger})")
        
        try:
            # Determine order type
            order_type = "Limit" if base_price else "Market"
            
            # Prepare order parameters
            params = {
                "category": self.category,
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": self._format_quantity(symbol, qty),
                "triggerPrice": self._format_price(symbol, trigger_price),
                "reduceOnly": reduce_only,
                "closeOnTrigger": close_on_trigger,
                "triggerBy": "LastPrice",
                "timeInForce": "GTC"
            }
            
            # Add base price if provided (for limit stop)
            if base_price:
                params["price"] = self._format_price(symbol, base_price)
            
            # Generate client order ID
            client_order_id = f"stp_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            params["orderLinkId"] = client_order_id
            
            # Send order request
            self.logger.info(f"Placing {side} stop {order_type.lower()} order for {symbol}: {qty} units, trigger at {trigger_price}")
            response = await self.transport.place_order(params)
            
            # Process response
            if response.get("retCode") == 0:
                order_id = response.get("result", {}).get("orderId")
                self.logger.info(f"Stop order placed successfully: {order_id}")
                
                # Add to active orders
                self.active_orders[order_id] = {
                    "symbol": symbol,
                    "side": side,
                    "type": f"Stop{order_type}",
                    "qty": qty,
                    "trigger_price": trigger_price,
                    "base_price": base_price,
                    "status": "New",
                    "client_order_id": client_order_id,
                    "create_time": int(time.time() * 1000)
                }
                
                return {
                    "orderId": order_id,
                    "symbol": symbol,
                    "status": "New"
                }
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to place stop order: {error_msg}")
                return {"error": error_msg}
            
        except Exception as e:
            self.logger.error(f"Error placing stop order: {str(e)}")
            return {"error": str(e)}
        finally:
            self.logger.debug(f"EXIT place_stop_order completed")
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an existing order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading symbol
            
        Returns:
            Response dictionary
        """
        self.logger.debug(f"ENTER cancel_order(order_id={order_id}, symbol={symbol})")
        
        try:
            # Prepare cancel parameters
            params = {
                "category": self.category,
                "symbol": symbol,
                "orderId": order_id
            }
            
            # Send cancel request
            self.logger.info(f"Cancelling order {order_id} for {symbol}")
            response = await self.transport.cancel_order(params)
            
            # Process response
            if response.get("retCode") == 0:
                self.logger.info(f"Order {order_id} cancelled successfully")
                
                # Move from active to cancelled
                if order_id in self.active_orders:
                    order_info = self.active_orders.pop(order_id)
                    order_info["status"] = "Cancelled"
                    order_info["cancel_time"] = int(time.time() * 1000)
                    self.cancelled_orders[order_id] = order_info
                
                return {
                    "orderId": order_id,
                    "symbol": symbol,
                    "status": "Cancelled"
                }
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to cancel order: {error_msg}")
                return {"error": error_msg}
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return {"error": str(e)}
        finally:
            self.logger.debug(f"EXIT cancel_order completed")
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all active orders.
        
        Args:
            symbol: Optional symbol to cancel orders for (if None, cancels all)
            
        Returns:
            Response dictionary
        """
        self.logger.debug(f"ENTER cancel_all_orders(symbol={symbol})")
        
        try:
            # Prepare cancel parameters
            params = {
                "category": self.category
            }
            
            # Add symbol if provided
            if symbol:
                params["symbol"] = symbol
            
            # Send cancel all request
            symbol_str = f"for {symbol}" if symbol else "for all symbols"
            self.logger.info(f"Cancelling all orders {symbol_str}")
            response = await self.transport.cancel_all_orders(params)
            
            # Process response
            if response.get("retCode") == 0:
                cancelled = response.get("result", {}).get("list", [])
                count = len(cancelled)
                self.logger.info(f"Cancelled {count} orders successfully")
                
                # Update order tracking
                for order in cancelled:
                    order_id = order.get("orderId")
                    if order_id in self.active_orders:
                        order_info = self.active_orders.pop(order_id)
                        order_info["status"] = "Cancelled"
                        order_info["cancel_time"] = int(time.time() * 1000)
                        self.cancelled_orders[order_id] = order_info
                
                return {
                    "success": True,
                    "count": count
                }
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to cancel all orders: {error_msg}")
                return {"error": error_msg}
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {str(e)}")
            return {"error": str(e)}
        finally:
            self.logger.debug(f"EXIT cancel_all_orders completed")
    
    async def get_active_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get active orders.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            List of active orders
        """
        self.logger.debug(f"ENTER get_active_orders(symbol={symbol})")
        
        try:
            # Prepare query parameters
            params = {
                "category": self.category,
                "limit": 50,
                "orderStatus": "New,PartiallyFilled"
            }
            
            # Add symbol if provided
            if symbol:
                params["symbol"] = symbol
            
            # Query active orders
            self.logger.info(f"Querying active orders{' for ' + symbol if symbol else ''}")
            response = await self.transport.get_active_orders(params)
            
            # Process response
            if response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                count = len(orders)
                self.logger.info(f"Retrieved {count} active orders")
                
                # Update order tracking
                for order in orders:
                    order_id = order.get("orderId")
                    if order_id not in self.active_orders:
                        self.active_orders[order_id] = {
                            "symbol": order.get("symbol"),
                            "side": order.get("side"),
                            "type": order.get("orderType"),
                            "qty": float(order.get("qty", "0")),
                            "price": float(order.get("price", "0")),
                            "status": order.get("orderStatus"),
                            "client_order_id": order.get("orderLinkId"),
                            "create_time": int(order.get("createdTime", "0"))
                        }
                
                return orders
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to get active orders: {error_msg}")
                return []
            
        except Exception as e:
            self.logger.error(f"Error getting active orders: {str(e)}")
            return []
        finally:
            self.logger.debug(f"EXIT get_active_orders completed")
    
    async def get_order_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get order history.
        
        Args:
            symbol: Optional symbol to filter by
            limit: Maximum number of orders to retrieve
            
        Returns:
            List of historical orders
        """
        self.logger.debug(f"ENTER get_order_history(symbol={symbol}, limit={limit})")
        
        try:
            # Prepare query parameters
            params = {
                "category": self.category,
                "limit": limit
            }
            
            # Add symbol if provided
            if symbol:
                params["symbol"] = symbol
            
            # Query order history
            self.logger.info(f"Querying order history{' for ' + symbol if symbol else ''}")
            response = await self.transport.get_order_history(params)
            
            # Process response
            if response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                count = len(orders)
                self.logger.info(f"Retrieved {count} historical orders")
                
                # Update order tracking for filled and cancelled orders
                for order in orders:
                    order_id = order.get("orderId")
                    status = order.get("orderStatus")
                    
                    if status == "Filled" and order_id not in self.filled_orders:
                        self.filled_orders[order_id] = {
                            "symbol": order.get("symbol"),
                            "side": order.get("side"),
                            "type": order.get("orderType"),
                            "qty": float(order.get("qty", "0")),
                            "price": float(order.get("price", "0")),
                            "status": status,
                            "client_order_id": order.get("orderLinkId"),
                            "create_time": int(order.get("createdTime", "0")),
                            "update_time": int(order.get("updatedTime", "0"))
                        }
                    elif status == "Cancelled" and order_id not in self.cancelled_orders:
                        self.cancelled_orders[order_id] = {
                            "symbol": order.get("symbol"),
                            "side": order.get("side"),
                            "type": order.get("orderType"),
                            "qty": float(order.get("qty", "0")),
                            "price": float(order.get("price", "0")),
                            "status": status,
                            "client_order_id": order.get("orderLinkId"),
                            "create_time": int(order.get("createdTime", "0")),
                            "update_time": int(order.get("updatedTime", "0"))
                        }
                
                return orders
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to get order history: {error_msg}")
                return []
            
        except Exception as e:
            self.logger.error(f"Error getting order history: {str(e)}")
            return []
        finally:
            self.logger.debug(f"EXIT get_order_history completed")
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get current positions.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            List of positions
        """
        self.logger.debug(f"ENTER get_positions(symbol={symbol})")
        
        try:
            # Prepare query parameters
            params = {
                "category": self.category
            }
            
            # Add symbol if provided
            if symbol:
                params["symbol"] = symbol
            
            # Query positions
            self.logger.info(f"Querying positions{' for ' + symbol if symbol else ''}")
            response = await self.transport.get_positions(params)
            
            # Process response
            if response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                count = len(positions)
                self.logger.info(f"Retrieved {count} positions")
                
                # Filter out zero-size positions
                non_zero_positions = [
                    pos for pos in positions
                    if float(pos.get("size", "0")) != 0
                ]
                
                if len(non_zero_positions) < count:
                    self.logger.info(f"Filtered out {count - len(non_zero_positions)} zero-size positions")
                
                return non_zero_positions
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to get positions: {error_msg}")
                return []
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            return []
        finally:
            self.logger.debug(f"EXIT get_positions completed")
    
    async def sync_order_status(self) -> bool:
        """
        Synchronize order status with the exchange.
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.debug(f"ENTER sync_order_status()")
        
        try:
            # Get active orders
            orders = await self.get_active_orders()
            
            # Check if any tracked orders are not active anymore
            tracked_order_ids = set(self.active_orders.keys())
            active_order_ids = set(order.get("orderId") for order in orders)
            
            # Find orders that are no longer active
            missing_order_ids = tracked_order_ids - active_order_ids
            
            if missing_order_ids:
                self.logger.info(f"Found {len(missing_order_ids)} orders that are no longer active")
                
                # Check order history for these missing orders
                for order_id in list(missing_order_ids):
                    # Get order from history by checking recent history
                    order_info = await self._get_order_info(order_id)
                    
                    if order_info:
                        status = order_info.get("orderStatus")
                        
                        # Remove from active orders
                        if order_id in self.active_orders:
                            order_data = self.active_orders.pop(order_id)
                            
                            # Update with latest info
                            order_data.update({
                                "status": status,
                                "update_time": int(time.time() * 1000)
                            })
                            
                            # Add to appropriate collection
                            if status == "Filled":
                                self.filled_orders[order_id] = order_data
                                self.logger.info(f"Order {order_id} is now filled")
                            elif status in ["Cancelled", "Rejected", "PendingCancel"]:
                                self.cancelled_orders[order_id] = order_data
                                self.logger.info(f"Order {order_id} is now {status}")
            
            self.logger.info(f"Order status synchronized, active: {len(self.active_orders)}, filled: {len(self.filled_orders)}, cancelled: {len(self.cancelled_orders)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error synchronizing order status: {str(e)}")
            return False
        finally:
            self.logger.debug(f"EXIT sync_order_status completed")
    
    async def _get_order_info(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an order.
        
        Args:
            order_id: Order ID to query
            
        Returns:
            Order information dictionary or None if not found
        """
        self.logger.debug(f"ENTER _get_order_info(order_id={order_id})")
        
        try:
            # Get symbol from tracked orders if available
            symbol = None
            if order_id in self.active_orders:
                symbol = self.active_orders[order_id].get("symbol")
            
            # We need symbol to query order info
            if not symbol:
                self.logger.warning(f"Cannot get order info: symbol unknown for order {order_id}")
                return None
            
            # Prepare query parameters
            params = {
                "category": self.category,
                "orderId": order_id,
                "symbol": symbol
            }
            
            # Query order
            response = await self.transport.get_order_info(params)
            
            # Process response
            if response.get("retCode") == 0:
                order = response.get("result", {})
                if order:
                    self.logger.info(f"Retrieved info for order {order_id}")
                    return order
                else:
                    self.logger.warning(f"Order {order_id} not found")
                    return None
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to get order info: {error_msg}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting order info: {str(e)}")
            return None
        finally:
            self.logger.debug(f"EXIT _get_order_info completed")
    
    def get_instruments_info(self, category: str = "linear") -> Optional[Dict[str, Any]]:
        """
        Get instrument information and cache it.
        
        Args:
            category: Instrument category ("linear" for USDT perpetuals)
            
        Returns:
            Dictionary of instrument information
        """
        self.logger.debug(f"ENTER get_instruments_info(category={category})")
        
        try:
            # Prepare query parameters
            params = {
                "category": category
            }
            
            # Query instruments
            self.logger.debug(f"Getting instruments info for {category}")
            response = self.transport.sync_get_instruments_info(params)
            
            # Process response
            if response.get("retCode") == 0:
                instruments = response.get("result", {}).get("list", [])
                instruments_count = len(instruments)
                
                # Cache instrument information
                for instrument in instruments:
                    symbol = instrument.get("symbol")
                    self.instruments_info[symbol] = instrument
                    
                    # Cache precision information
                    price_scale_str = instrument.get("priceScale", "2")
                    qty_scale_str = instrument.get("lotSizeFilter", {}).get("qtyStep", "0.001")
                    min_qty_str = instrument.get("lotSizeFilter", {}).get("minOrderQty", "0.001")
                    
                    try:
                        self.price_scales[symbol] = int(price_scale_str)
                        
                        # Determine quantity scale from step size
                        if "." in qty_scale_str:
                            qty_scale = len(qty_scale_str.split(".")[1])
                            self.qty_scales[symbol] = qty_scale
                        else:
                            self.qty_scales[symbol] = 0
                            
                        # Store minimum order quantity
                        self.min_order_qty[symbol] = float(min_qty_str)
                        
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Error parsing precision for {symbol}: {str(e)}")
                        self.price_scales[symbol] = 2
                        self.qty_scales[symbol] = 3
                        self.min_order_qty[symbol] = 0.001
                
                self.logger.debug(f"EXIT get_instruments_info returned info for {instruments_count} instruments")
                return {"list": instruments}
            else:
                error_msg = response.get("retMsg", "Unknown error")
                self.logger.error(f"Failed to get instruments info: {error_msg}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting instruments info: {str(e)}")
            return None
    
    def _format_price(self, symbol: str, price: float) -> str:
        """
        Format price according to symbol's price precision.
        
        Args:
            symbol: Trading symbol
            price: Price to format
            
        Returns:
            Formatted price string
        """
        precision = self.price_scales.get(symbol, 2)
        return f"{price:.{precision}f}"
    
    def _format_quantity(self, symbol: str, qty: float) -> str:
        """
        Format quantity according to symbol's quantity precision.
        
        Args:
            symbol: Trading symbol
            qty: Quantity to format
            
        Returns:
            Formatted quantity string
        """
        precision = self.qty_scales.get(symbol, 3)
        
        # Ensure minimum order size
        min_qty = self.min_order_qty.get(symbol, 0.001)
        if qty < min_qty:
            qty = min_qty
            
        return f"{qty:.{precision}f}"
    
    def get_price_precision(self, symbol: str) -> int:
        """
        Get price precision for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Price decimal precision
        """
        return self.price_scales.get(symbol, 2)
    
    def get_qty_precision(self, symbol: str) -> int:
        """
        Get quantity precision for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Quantity decimal precision
        """
        return self.qty_scales.get(symbol, 3)