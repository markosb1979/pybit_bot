"""
Order Manager Client - Specialized client for order management operations

This module provides a high-level interface for trading operations,
built on top of the BybitClientTransport for reliable API communication.
It handles order placement, management, position tracking, and all
trading-related functionality.

Example usage:
    # Initialize transport layer
    credentials = APICredentials(api_key="your_key", api_secret="your_secret", testnet=True)
    transport = BybitClientTransport(credentials)
    
    # Create order manager client
    order_client = OrderManagerClient(transport, logger=logger)
    
    # Place a market order with embedded TP/SL
    result = order_client.place_active_order(
        symbol="BTCUSDT",
        side="Buy",
        order_type="Market",
        qty="0.01",
        take_profit="90000",
        stop_loss="85000"
    )
    
    # Or manage existing orders/positions
    positions = order_client.get_positions("BTCUSDT")
    orders = order_client.get_open_orders("BTCUSDT")
    cancel_result = order_client.cancel_order("BTCUSDT", order_id)
"""

import time
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union, Tuple
import json

from .client import BybitClientTransport
from ..utils.logger import Logger
from ..exceptions import (
    BybitAPIError,
    AuthenticationError,
    RateLimitError,
    InvalidOrderError,
    PositionError
)

class OrderManagerClient:
    """
    Order management client providing specialized trading functionality
    Built on top of BybitClientTransport for reliability and consistency
    """

    def __init__(self, transport: BybitClientTransport, logger: Optional[Logger] = None, config: Optional[Any] = None):
        """
        Initialize with BybitClientTransport instance
        
        Args:
            transport: BybitClientTransport instance
            logger: Optional logger instance
            config: Optional configuration
        """
        self.transport = transport
        self.logger = logger or Logger("OrderManagerClient")
        self.config = config
        
        # Default settings
        self.default_symbol = getattr(config, 'default_symbol', "BTCUSDT") if config else "BTCUSDT"
        self.max_leverage = getattr(config, 'max_leverage', 10) if config else 10
        
        # Track processed orders to prevent duplicate processing
        self.processed_order_ids = set()
        
        # Cache position information to reduce API calls
        self.position_cache = {}
        self.position_cache_timestamp = {}
        self.position_cache_ttl = 1.0  # 1 second cache TTL
        
        # Cache instrument info for tick size derivation
        try:
            resp = self.get_instruments_info()
            instruments = resp.get("list", [])
            
            # Map symbol -> instrument metadata
            self._instrument_info = {item["symbol"]: item for item in instruments}
            self.logger.info(f"Cached info for {len(self._instrument_info)} instruments")
            
            # Log a few symbols as sample
            if len(self._instrument_info) > 0:
                sample_symbols = list(self._instrument_info.keys())[:3]
                self.logger.debug(f"Sample symbols: {sample_symbols}")
        except Exception as e:
            self.logger.error(f"Failed to fetch instrument info: {e}")
            self._instrument_info = {}
            # Critical dependency - alert clearly
            self.logger.warning("⚠️ CRITICAL: No instrument info available. Price/quantity rounding will use defaults!")
        
        # Cache for instrument info
        self._instrument_info_cache = {}
        
    # ========== INFORMATION METHODS ==========
    
    def get_instrument_info(self, symbol: str) -> Dict:
        """
        Get instrument specifications with caching
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Instrument information dictionary
            
        References:
            https://bybit-exchange.github.io/docs/v5/market/instrument
        """
        # Check cache first
        if symbol in self._instrument_info_cache:
            return self._instrument_info_cache[symbol]
            
        # Check if it's in the global cache already
        if symbol in self._instrument_info:
            self._instrument_info_cache[symbol] = self._instrument_info[symbol]
            return self._instrument_info[symbol]
            
        # Fetch instrument info directly
        try:
            params = {
                "category": "linear",
                "symbol": symbol
            }
            
            response = self.transport.raw_request("GET", "/v5/market/instruments-info", params, auth_required=False)
            instruments = response.get("list", [])
                
            if not instruments:
                self.logger.error(f"Instrument info not found for {symbol}")
                return {}
                
            # Cache the info
            self._instrument_info_cache[symbol] = instruments[0]
            return instruments[0]
            
        except Exception as e:
            self.logger.error(f"Error fetching instrument info: {str(e)}")
            return {}
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get current positions
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            List of position dictionaries
            
        References:
            https://bybit-exchange.github.io/docs/v5/position
        """
        try:
            # Check cache for this symbol if requested
            current_time = time.time()
            if symbol and symbol in self.position_cache:
                cache_age = current_time - self.position_cache_timestamp.get(symbol, 0)
                if cache_age < self.position_cache_ttl:
                    # Return cached position
                    return [self.position_cache[symbol]]
            
            params = {
                "category": "linear"
            }
            
            if symbol:
                params["symbol"] = symbol
                
            response = self.transport.raw_request("GET", "/v5/position/list", params)
            positions = response.get("list", [])
            
            # Update cache with active positions
            for position in positions:
                pos_symbol = position.get("symbol")
                if pos_symbol and float(position.get("size", 0)) != 0:
                    self.position_cache[pos_symbol] = position
                    self.position_cache_timestamp[pos_symbol] = current_time
                elif pos_symbol and pos_symbol in self.position_cache:
                    # Remove closed positions from cache
                    del self.position_cache[pos_symbol]
                    if pos_symbol in self.position_cache_timestamp:
                        del self.position_cache_timestamp[pos_symbol]
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            return []
    
    def position_exists(self, symbol: str) -> bool:
        """
        Check if an active position exists for a symbol
        
        Args:
            symbol: Trading symbol to check
            
        Returns:
            True if position exists with non-zero size, False otherwise
        """
        try:
            positions = self.get_positions(symbol)
            for position in positions:
                if position.get("symbol") == symbol and float(position.get("size", 0)) != 0:
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking position existence: {str(e)}")
            return False
    
    def get_account_balance(self) -> Dict:
        """
        Get account wallet balance
        
        Returns:
            Dictionary with balance information
            
        References:
            https://bybit-exchange.github.io/docs/v5/account/wallet-balance
        """
        try:
            response = self.transport.raw_request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
            
            # Extract USDT balance for convenience
            if isinstance(response, list) and response:
                for account in response:
                    coins = account.get("coin", [])
                    for coin in coins:
                        if coin.get("coin") == "USDT":
                            return {
                                "totalBalance": coin.get("walletBalance", "0"),
                                "totalAvailableBalance": coin.get("availableToWithdraw", "0"),
                                "equity": coin.get("equity", "0")
                            }
                
            return {"totalAvailableBalance": "0"}
            
        except Exception as e:
            self.logger.error(f"Error getting account balance: {str(e)}")
            return {"totalAvailableBalance": "0"}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get all active orders
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            List of active orders
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/open-order
        """
        try:
            params = {
                "category": "linear"
            }
            
            if symbol:
                params["symbol"] = symbol
                
            response = self.transport.raw_request("GET", "/v5/order/realtime", params)
            return response.get("list", [])
            
        except Exception as e:
            self.logger.error(f"Error getting active orders: {str(e)}")
            return []
    
    def get_order_status(self, symbol: str, order_id: str) -> str:
        """
        Get current status of an order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            
        Returns:
            Order status string
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/order-list
        """
        try:
            # Query order directly using get_order_fill_info
            fill_info = self.get_order_fill_info(symbol, order_id)
            
            if "status" in fill_info:
                return fill_info["status"]
            elif fill_info.get("filled", False):
                return "Filled"
            else:
                return "NotFound"
            
        except Exception as e:
            self.logger.error(f"Error getting order status: {str(e)}")
            return "Error"
    
    def get_order_history(self, symbol: Optional[str] = None, order_id: Optional[str] = None) -> List[Dict]:
        """
        Get historical orders
        
        Args:
            symbol: Optional symbol to filter
            order_id: Optional order ID to filter
            
        Returns:
            List of order history dictionaries
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/order-list
        """
        try:
            params = {
                "category": "linear"
            }
            
            if symbol:
                params["symbol"] = symbol
                
            if order_id:
                params["orderId"] = order_id
                
            response = self.transport.raw_request("GET", "/v5/order/history", params)
            return response.get("list", [])
            
        except Exception as e:
            self.logger.error(f"Error getting order history: {str(e)}")
            return []
    
    def get_order(self, symbol: str, order_id: str) -> Dict:
        """
        Get detailed order information by order ID.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            
        Returns:
            Order information dictionary
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/order-list
        """
        try:
            self.logger.info(f"Getting order info for {order_id} on {symbol}")
            
            # Check history
            orders = self.get_order_history(symbol, order_id)
            
            if orders:
                for order in orders:
                    if order.get("orderId") == order_id:
                        return order
            
            # If not found, try active orders
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            
            response = self.transport.raw_request("GET", "/v5/order/realtime", params)
            active_orders = response.get("list", [])
            
            if active_orders:
                for order in active_orders:
                    if order.get("orderId") == order_id:
                        return order
            
            # If not found, try executions
            exec_params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            
            response = self.transport.raw_request("GET", "/v5/execution/list", exec_params)
            executions = response.get("list", [])
            
            if executions:
                execution = executions[0]
                # Construct an order-like response from execution data
                return {
                    "orderId": order_id,
                    "symbol": symbol,
                    "side": execution.get("side"),
                    "orderStatus": "Filled",
                    "avgPrice": execution.get("execPrice"),
                    "leavesQty": "0",
                    "execQty": execution.get("execQty"),
                    "execFee": execution.get("execFee")
                }
                
            # Order not found in any of the endpoints
            return {"status": "NotFound", "orderId": order_id}
            
        except Exception as e:
            self.logger.error(f"Error getting order info: {str(e)}")
            return {"status": "Error", "message": str(e), "orderId": order_id}
    
    def get_order_fill_info(self, symbol: str, order_id: str) -> Dict:
        """
        Get fill information for a specific order.
        Useful for post-fill TP/SL calculations.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to check
            
        Returns:
            Dictionary with fill information or empty if not filled
        """
        try:
            # Get order details
            order_info = self.get_order(symbol, order_id)
            
            # Check if order is filled
            if order_info.get("orderStatus") == "Filled":
                return {
                    "filled": True,
                    "fill_price": float(order_info.get("avgPrice", 0)),
                    "side": order_info.get("side"),
                    "position_idx": 0  # Default for one-way mode
                }
            elif "orderStatus" in order_info:
                return {"filled": False, "status": order_info.get("orderStatus")}
            
            # If order not found, check positions for recent fills
            positions = self.get_positions(symbol)
            if positions and float(positions[0].get("size", "0")) > 0:
                # Position exists, order likely filled
                position = positions[0]
                return {
                    "filled": True,
                    "fill_price": float(position.get("avgPrice", 0)),
                    "side": position.get("side"),
                    "position_idx": position.get("positionIdx", 0)
                }
                
            # Order not found anywhere
            self.logger.warning(f"Order {order_id} not found for {symbol}")
            return {"filled": False, "status": "Not Found"}
            
        except Exception as e:
            self.logger.error(f"Error getting order fill info: {str(e)}")
            return {"filled": False, "error": str(e)}
    
    def get_instruments_info(self, category="linear") -> Dict:
        """
        Get instrument information for all symbols in a category
        
        Args:
            category: Instrument category (linear, inverse, spot)
            
        Returns:
            Dictionary with instrument information
            
        References:
            https://bybit-exchange.github.io/docs/v5/market/instrument
        """
        try:
            self.logger.debug(f"Getting instruments info for {category}")
            
            params = {
                "category": category
            }
            
            response = self.transport.raw_request("GET", "/v5/market/instruments-info", params, auth_required=False)
            
            if not response:
                self.logger.error("Error getting instruments info: Empty response")
                return {"list": []}
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting instruments info: {str(e)}")
            return {"list": []}
    
    def get_ticker(self, symbol: str) -> Dict:
        """
        Get latest price ticker
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Ticker data
            
        References:
            https://bybit-exchange.github.io/docs/v5/market/tickers
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol
            }
            
            response = self.transport.raw_request("GET", "/v5/market/tickers", params, auth_required=False)
            tickers = response.get("list", [])
            
            if tickers:
                return tickers[0]
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting ticker: {str(e)}")
            return {}
    
    def get_orderbook(self, symbol: str, limit: int = 25) -> Dict:
        """
        Get orderbook data
        
        Args:
            symbol: Trading symbol
            limit: Depth of orderbook (default: 25)
            
        Returns:
            Orderbook data
            
        References:
            https://bybit-exchange.github.io/docs/v5/market/orderbook
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "limit": limit
            }
            
            response = self.transport.raw_request("GET", "/v5/market/orderbook", params, auth_required=False)
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting orderbook: {str(e)}")
            return {}
    
    def get_klines(self, symbol: str, interval: str, limit: int = 1000, 
                  start_time: Optional[int] = None, end_time: Optional[int] = None) -> List:
        """
        Get historical kline/candlestick data
        
        Args:
            symbol: Trading symbol
            interval: Kline interval (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            limit: Number of klines to return (max 1000)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            
        Returns:
            List of klines
            
        References:
            https://bybit-exchange.github.io/docs/v5/market/kline
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            if start_time:
                params["start"] = start_time
            if end_time:
                params["end"] = end_time
                
            self.logger.info(f"Fetching kline data for {symbol} {interval}, limit={limit}")
            
            response = self.transport.raw_request("GET", "/v5/market/kline", params, auth_required=False)
            
            klines = response.get("list", [])
            self.logger.info(f"Retrieved {len(klines)} klines for {symbol}")
            
            return klines
            
        except Exception as e:
            self.logger.error(f"Error getting klines: {str(e)}")
            return []
    
    # ========== POSITION SIZING METHODS ==========
    
    def _round_quantity(self, symbol: str, quantity: float) -> str:
        """
        Round quantity to valid precision based on instrument specs
        
        Args:
            symbol: Trading symbol
            quantity: Raw quantity value
            
        Returns:
            Quantity as string with correct precision
        """
        info = self.get_instrument_info(symbol)
        
        if not info:
            # Default to 3 decimal places if info not available
            self.logger.warning(f"No instrument info for {symbol}, using default qty precision (3 decimals)")
            return "{:.3f}".format(quantity)
            
        # Get lot size step from instrument info
        lot_size_filter = info.get("lotSizeFilter", {})
        qty_step = lot_size_filter.get("qtyStep", "0.001")
        min_qty = float(lot_size_filter.get("minOrderQty", "0.001"))
        
        # Ensure quantity is at least the minimum
        quantity = max(quantity, min_qty)
        
        # Round to the nearest step
        step = Decimal(qty_step)
        rounded = Decimal(str(quantity)).quantize(step)
        
        # Format based on decimal places in step
        decimal_places = len(qty_step.split('.')[-1]) if '.' in qty_step else 0
        return "{:.{}f}".format(float(rounded), decimal_places)
    
    def _round_price(self, symbol: str, price: float) -> str:
        """
        Round price to valid precision based on instrument specs
        
        Args:
            symbol: Trading symbol
            price: Raw price value
            
        Returns:
            Price as string with correct precision
        """
        info = self.get_instrument_info(symbol)
        
        if not info:
            # Default to 2 decimal places if info not available
            self.logger.warning(f"No instrument info for {symbol}, using default price precision (2 decimals)")
            return "{:.2f}".format(price)
            
        # Get price step from instrument info
        price_filter = info.get("priceFilter", {})
        tick_size = price_filter.get("tickSize", "0.01")
        
        # Round to the nearest tick
        step = Decimal(tick_size)
        rounded = Decimal(str(price)).quantize(step)
        
        # Format based on decimal places in step
        decimal_places = len(tick_size.split('.')[-1]) if '.' in tick_size else 0
        return "{:.{}f}".format(float(rounded), decimal_places)
    
    def calculate_position_size(self, symbol: str, usdt_amount: float, price: Optional[float] = None) -> str:
        """
        Calculate contract quantity based on USDT amount
        
        Args:
            symbol: Trading pair symbol
            usdt_amount: Amount in USDT to use for position
            price: Optional price to use (if None, gets latest price)
            
        Returns:
            Contract quantity as string, properly rounded
        """
        # Get current price if not provided
        if price is None:
            # Get ticker data
            ticker = self.get_ticker(symbol)
            if ticker:
                price = float(ticker.get("lastPrice", 0))
            else:
                self.logger.error(f"Failed to get ticker for {symbol}")
                return "0"
            
        if price <= 0:
            self.logger.error(f"Invalid price for {symbol}: {price}")
            return "0"
            
        # Calculate raw quantity
        raw_quantity = usdt_amount / price
        
        # Round to valid quantity
        rounded_qty = self._round_quantity(symbol, raw_quantity)
        
        self.logger.info(f"Position size for {usdt_amount} USDT of {symbol} at {price}: {rounded_qty}")
        return rounded_qty
    
    # ========== ORDER PLACEMENT METHODS ==========
    
    def place_active_order(self, **kwargs) -> Dict:
        """
        Place an order with flexible parameters
        
        Args:
            **kwargs: Order parameters including:
                symbol: Trading symbol
                side: Buy or Sell
                order_type: Market, Limit, etc.
                qty: Order quantity
                price: Optional price for limit orders
                reduce_only: Optional boolean to only reduce position
                close_on_trigger: Optional boolean to close on trigger
                time_in_force: GTC, IOC, etc.
                take_profit: Optional take profit price
                stop_loss: Optional stop loss price
                tp_trigger_by: Optional TP trigger type
                sl_trigger_by: Optional SL trigger type
                order_link_id: Optional client order ID
                
        Returns:
            Order result dictionary
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/create-order
            
        Example:
            # Market order with embedded TP/SL
            result = client.place_active_order(
                symbol="BTCUSDT", 
                side="Buy", 
                order_type="Market",
                qty="0.01", 
                take_profit="90000", 
                stop_loss="85000"
            )
        """
        try:
            # Extract required parameters
            symbol = kwargs.get("symbol")
            side = kwargs.get("side")
            order_type = kwargs.get("order_type")
            qty = kwargs.get("qty")
            
            if not all([symbol, side, order_type, qty]):
                raise ValueError("Missing required parameters: symbol, side, order_type, and qty are required")
                
            # Log the request parameters
            self.logger.debug(f"Placing order with params: {kwargs}")
            
            # Create proper parameter mapping for create_order endpoint
            params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": qty
            }
            
            # Add optional parameters with correct camelCase conversion
            if kwargs.get("price") is not None:
                params["price"] = kwargs["price"]
                
            if kwargs.get("take_profit") is not None:
                # Round to proper precision
                tp_price = self._round_price(symbol, float(kwargs["take_profit"]))
                params["takeProfit"] = tp_price
                
                # Add trigger type if provided
                if kwargs.get("tp_trigger_by") is not None:
                    params["tpTriggerBy"] = kwargs["tp_trigger_by"]
                else:
                    params["tpTriggerBy"] = "MarkPrice"
                
            if kwargs.get("stop_loss") is not None:
                # Round to proper precision
                sl_price = self._round_price(symbol, float(kwargs["stop_loss"]))
                params["stopLoss"] = sl_price
                
                # Add trigger type if provided
                if kwargs.get("sl_trigger_by") is not None:
                    params["slTriggerBy"] = kwargs["sl_trigger_by"]
                else:
                    params["slTriggerBy"] = "MarkPrice"
                
            if kwargs.get("reduce_only") is not None:
                params["reduceOnly"] = kwargs["reduce_only"]
                
            if kwargs.get("close_on_trigger") is not None:
                params["closeOnTrigger"] = kwargs["close_on_trigger"]
                
            if kwargs.get("time_in_force") is not None:
                params["timeInForce"] = kwargs["time_in_force"]
            elif order_type.lower() == "limit":
                params["timeInForce"] = "GoodTillCancel"
                
            if kwargs.get("order_link_id") is not None:
                params["orderLinkId"] = kwargs["order_link_id"]
            
            # Make the API request to place the order
            response = self.transport.raw_request("POST", "/v5/order/create", params)
            
            self.logger.info(f"Order placed: {side} {order_type} for {symbol}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error placing order: {str(e)}")
            return {"error": str(e)}
    
    def create_order(self, **kwargs) -> Dict:
        """
        Create an order using the official endpoint naming
        (Alias for place_active_order for backward compatibility)
        
        References:
            https://bybit-exchange.github.io/docs/v5/order/create-order
        """
        return self.place_active_order(**kwargs)
    
    def amend_order(self, symbol: str, order_id: str, **kwargs) -> Dict:
        """
        Amend an existing order to update price, quantity, or TP/SL
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to amend
            **kwargs: Parameters to update, including:
                qty: New quantity
                price: New price
                take_profit: New take profit price
                stop_loss: New stop loss price
                tp_trigger_by: Take profit trigger type
                sl_trigger_by: Stop loss trigger type
                
        Returns:
            Dictionary with amendment result
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/amend-order
            
        Example:
            # Update TP/SL on an existing order
            result = client.amend_order(
                symbol="BTCUSDT",
                order_id="1234567890",
                take_profit="91000",
                stop_loss="84000"
            )
        """
        try:
            if not symbol or not order_id:
                raise ValueError("Symbol and order_id are required parameters")
                
            # Prepare parameters for amend_order endpoint
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            
            # Add optional parameters with correct camelCase conversion
            if kwargs.get("qty") is not None:
                params["qty"] = kwargs["qty"]
                
            if kwargs.get("price") is not None:
                params["price"] = kwargs["price"]
                
            if kwargs.get("take_profit") is not None:
                # Round to proper precision
                tp_price = self._round_price(symbol, float(kwargs["take_profit"]))
                params["takeProfit"] = tp_price
                
            if kwargs.get("stop_loss") is not None:
                # Round to proper precision
                sl_price = self._round_price(symbol, float(kwargs["stop_loss"]))
                params["stopLoss"] = sl_price
                
            if kwargs.get("tp_trigger_by") is not None:
                params["tpTriggerBy"] = kwargs["tp_trigger_by"]
                
            if kwargs.get("sl_trigger_by") is not None:
                params["slTriggerBy"] = kwargs["sl_trigger_by"]
            
            # Log the request
            self.logger.debug(f"Amending order {order_id} for {symbol} with params: {params}")
            
            # Make the API request to amend the order
            response = self.transport.raw_request("POST", "/v5/order/amend", params)
            
            # Handle special case for no-modification success
            if response and response.get("retCode") == 34040:
                self.logger.info(f"Order {order_id} already has requested values, no changes needed")
                return {
                    "success": True, 
                    "message": "No changes needed", 
                    "orderId": order_id
                }
                
            self.logger.info(f"Order {order_id} amended successfully")
            return response
            
        except Exception as e:
            # Check for no-modification error (success case)
            if "no modification" in str(e).lower() or "34040" in str(e):
                self.logger.info(f"Order {order_id} already has requested values, no changes needed")
                return {
                    "success": True, 
                    "message": "No changes needed", 
                    "orderId": order_id
                }
                
            self.logger.error(f"Error amending order: {str(e)}")
            return {"error": str(e)}
    
    def place_market_order(self, symbol: str, side: str, qty: str, tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Place market order with simplified parameters
        
        Args:
            symbol: Trading symbol
            side: Buy or Sell
            qty: Order quantity
            tp_price: Optional take profit price
            sl_price: Optional stop loss price
            
        Returns:
            Order result dictionary
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/create-order
        """
        params = {
            "symbol": symbol,
            "side": side,
            "order_type": "Market",
            "qty": qty
        }
        
        # Add TP/SL if provided
        if tp_price:
            params["take_profit"] = tp_price
            params["tp_trigger_by"] = "MarkPrice"
            
        if sl_price:
            params["stop_loss"] = sl_price
            params["sl_trigger_by"] = "MarkPrice"
            
        return self.place_active_order(**params)
    
    def place_limit_order(self, symbol: str, side: str, qty: str, price: str, 
                          tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Place limit order with simplified parameters
        
        Args:
            symbol: Trading symbol
            side: Buy or Sell
            qty: Order quantity
            price: Order price
            tp_price: Optional take profit price
            sl_price: Optional stop loss price
            
        Returns:
            Order result dictionary
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/create-order
        """
        params = {
            "symbol": symbol,
            "side": side,
            "order_type": "Limit",
            "qty": qty,
            "price": price,
            "time_in_force": "GoodTillCancel"
        }
        
        # Add TP/SL if provided
        if tp_price:
            params["take_profit"] = tp_price
            params["tp_trigger_by"] = "MarkPrice"
            
        if sl_price:
            params["stop_loss"] = sl_price
            params["sl_trigger_by"] = "MarkPrice"
            
        return self.place_active_order(**params)
    
    def enter_position_market(self, symbol: str, side: str, qty: float, tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Enter a position with a market order, optionally with TP/SL.
        
        Args:
            symbol: Trading symbol
            side: "Buy" or "Sell"
            qty: Position size
            tp_price: Optional take profit price
            sl_price: Optional stop loss price
            
        Returns:
            Dictionary with order results including order ID
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/create-order
        """
        # Generate a unique order link ID
        direction = "LONG" if side == "Buy" else "SHORT"
        order_link_id = f"{direction}_{symbol}_{int(time.time() * 1000)}"
        
        # Convert qty to string if it's a float
        qty_str = str(qty) if isinstance(qty, str) else self._round_quantity(symbol, qty)
        
        # Prepare order parameters
        params = {
            "symbol": symbol,
            "side": side,
            "order_type": "Market",
            "qty": qty_str,
            "order_link_id": order_link_id
        }
        
        # Add TP/SL if provided - using single-call entry pattern
        if tp_price:
            params["take_profit"] = tp_price
            params["tp_trigger_by"] = "MarkPrice"
            
        if sl_price:
            params["stop_loss"] = sl_price
            params["sl_trigger_by"] = "MarkPrice"
        
        # Place the order
        return self.place_active_order(**params)
    
    def place_oco_order(self, symbol: str, side: str, qty: float, tp_price: str, sl_price: str) -> Dict:
        """
        Place a market order with embedded TP/SL as a true OCO (one-cancels-other) order
        
        Args:
            symbol: Trading symbol
            side: "Buy" or "Sell"
            qty: Position size
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with order results
        """
        # Verify position doesn't already exist
        if self.position_exists(symbol):
            opposite_side = "Sell" if side == "Buy" else "Buy"
            # Try to close existing position first
            self.logger.info(f"Position already exists for {symbol}, closing before placing new OCO order")
            close_result = self.close_position(symbol)
            # Add delay to ensure position is closed
            time.sleep(1)
        
        # Generate a unique order link ID
        direction = "LONG" if side == "Buy" else "SHORT"
        order_link_id = f"OCO_{direction}_{symbol}_{int(time.time() * 1000)}"
        
        # Convert qty to string if it's a float
        qty_str = str(qty) if isinstance(qty, str) else self._round_quantity(symbol, qty)
        
        # Ensure TP/SL prices are properly formatted
        tp_price_str = str(tp_price) if isinstance(tp_price, str) else self._round_price(symbol, float(tp_price))
        sl_price_str = str(sl_price) if isinstance(sl_price, str) else self._round_price(symbol, float(sl_price))
        
        # Place market order with TP/SL in a single call
        self.logger.info(f"Placing OCO order: {side} {qty_str} {symbol} with TP={tp_price_str}, SL={sl_price_str}")
        
        result = self.place_active_order(
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty_str,
            take_profit=tp_price_str,
            stop_loss=sl_price_str,
            tp_trigger_by="MarkPrice",
            sl_trigger_by="MarkPrice",
            order_link_id=order_link_id
        )
        
        if "error" in result:
            self.logger.error(f"OCO order failed: {result['error']}")
            return result
            
        # Mark this order as processed to avoid duplicate TP/SL setting
        order_id = result.get("orderId")
        if order_id:
            self.processed_order_ids.add(order_id)
            
        self.logger.info(f"OCO order placed successfully: {order_id}")
        return result
    
    # ========== TAKE PROFIT / STOP LOSS METHODS ==========
    
    def set_trading_stop(self, **kwargs) -> Dict:
        """
        Set take profit, stop loss or trailing stop for the position.
        
        Args:
            **kwargs: Parameters including:
                symbol: Trading symbol
                positionIdx: Position index (0 for one-way mode)
                takeProfit: Take profit price
                stopLoss: Stop loss price
                tpTriggerBy: Trigger type for take profit
                slTriggerBy: Trigger type for stop loss
                
        Returns:
            Dictionary with API response
            
        References:
            https://bybit-exchange.github.io/docs/v5/position/trading-stop
        """
        try:
            # Extract the symbol parameter
            symbol = kwargs.get("symbol")
            if not symbol:
                raise ValueError("Symbol is required")
            
            # Check if position exists first
            if not self.position_exists(symbol):
                self.logger.warning(f"No active position for {symbol}, cannot set TP/SL")
                return {
                    "success": False,
                    "error": "No active position",
                    "message": "Cannot set TP/SL for a non-existent position"
                }
                
            # Prepare parameters for the trading-stop endpoint
            params = {
                "category": "linear",
                "symbol": symbol
            }
            
            # Handle position index
            if "positionIdx" in kwargs:
                params["positionIdx"] = kwargs["positionIdx"]
                
            # Handle TP/SL prices and triggers with proper formatting
            if "takeProfit" in kwargs and kwargs["takeProfit"]:
                # Round price to instrument precision
                tp_price = self._round_price(symbol, float(kwargs["takeProfit"]))
                params["takeProfit"] = tp_price
                
                if "tpTriggerBy" in kwargs:
                    params["tpTriggerBy"] = kwargs["tpTriggerBy"]
                else:
                    params["tpTriggerBy"] = "MarkPrice"
            
            if "stopLoss" in kwargs and kwargs["stopLoss"]:
                # Round price to instrument precision
                sl_price = self._round_price(symbol, float(kwargs["stopLoss"]))
                params["stopLoss"] = sl_price
                
                if "slTriggerBy" in kwargs:
                    params["slTriggerBy"] = kwargs["slTriggerBy"]
                else:
                    params["slTriggerBy"] = "MarkPrice"
            
            # Add a delay before setting TP/SL to avoid race conditions
            time.sleep(0.5)
            
            # Log the request
            self.logger.debug(f"Setting TP/SL for {symbol} with params: {params}")
            
            # Make the API request to set trading stop
            response = self.transport.raw_request("POST", "/v5/position/trading-stop", params)
            
            self.logger.info(f"Trading stop set for {symbol}")
            return response
            
        except Exception as e:
            # Special case handling for "no modification" errors (treat as success)
            if "no modification" in str(e).lower() or "34040" in str(e):
                self.logger.info(f"TP/SL already set to requested values for {kwargs.get('symbol')}")
                return {
                    "success": True, 
                    "message": "No changes needed", 
                    "symbol": kwargs.get('symbol')
                }
            # Special case for "zero position" errors
            elif "zero position" in str(e).lower() or "can not set tp/sl/ts for zero position" in str(e).lower():
                self.logger.warning(f"Cannot set TP/SL for zero position: {kwargs.get('symbol')}")
                return {
                    "success": False,
                    "error": "No active position",
                    "message": "Cannot set TP/SL for a non-existent position"
                }
            
            self.logger.error(f"Error setting trading stop: {str(e)}")
            return {"error": str(e)}
    
    def set_take_profit(self, symbol: str, takeProfit: float, **kwargs) -> Dict:
        """
        Set take profit for an existing position
        
        Args:
            symbol: Trading symbol
            takeProfit: Take profit price
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with API response
            
        References:
            https://bybit-exchange.github.io/docs/v5/position/trading-stop
        """
        # Check if position exists first
        if not self.position_exists(symbol):
            self.logger.warning(f"No active position for {symbol}, cannot set take profit")
            return {
                "success": False,
                "error": "No active position",
                "message": "Cannot set take profit for a non-existent position"
            }
            
        params = {
            "symbol": symbol,
            "takeProfit": str(takeProfit),
            "tpTriggerBy": kwargs.get("tpTriggerBy", "MarkPrice"),
            "positionIdx": kwargs.get("positionIdx", 0)
        }
        
        return self.set_trading_stop(**params)
    
    def set_stop_loss(self, symbol: str, stopLoss: float, **kwargs) -> Dict:
        """
        Set stop loss for an existing position
        
        Args:
            symbol: Trading symbol
            stopLoss: Stop loss price
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with API response
            
        References:
            https://bybit-exchange.github.io/docs/v5/position/trading-stop
        """
        # Check if position exists first
        if not self.position_exists(symbol):
            self.logger.warning(f"No active position for {symbol}, cannot set stop loss")
            return {
                "success": False,
                "error": "No active position",
                "message": "Cannot set stop loss for a non-existent position"
            }
            
        params = {
            "symbol": symbol,
            "stopLoss": str(stopLoss),
            "slTriggerBy": kwargs.get("slTriggerBy", "MarkPrice"),
            "positionIdx": kwargs.get("positionIdx", 0)
        }
        
        return self.set_trading_stop(**params)
    
    def set_position_tpsl(self, symbol: str, position_idx: int, tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Set both take profit and stop loss for an existing position in one call.
        
        Args:
            symbol: Trading symbol
            position_idx: Position index (0 for one-way mode)
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with TP/SL setting result
            
        References:
            https://bybit-exchange.github.io/docs/v5/position/trading-stop
        """
        # Check if position exists first
        if not self.position_exists(symbol):
            self.logger.warning(f"No active position for {symbol}, cannot set TP/SL")
            return {
                "success": False,
                "error": "No active position",
                "message": "Cannot set TP/SL for a non-existent position"
            }
            
        params = {
            "symbol": symbol,
            "positionIdx": position_idx
        }
        
        if tp_price:
            params["takeProfit"] = tp_price
            params["tpTriggerBy"] = "MarkPrice"
            
        if sl_price:
            params["stopLoss"] = sl_price
            params["slTriggerBy"] = "MarkPrice"
        
        return self.set_trading_stop(**params)
    
    def set_position_tpsl_safe(self, symbol: str, tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Safely set TP/SL for a position with existence check and error handling
        
        Args:
            symbol: Trading symbol
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with TP/SL setting result
        """
        # Check if position exists first
        positions = self.get_positions(symbol)
        
        if not positions or float(positions[0].get('size', '0')) == 0:
            self.logger.info(f"No active position for {symbol}, skipping TP/SL")
            return {"status": "skipped", "reason": "no_position"}
        
        # Position exists, set TP/SL
        position = positions[0]
        position_idx = position.get('positionIdx', 0)
        
        # Add retry logic for better reliability
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                result = self.set_position_tpsl(symbol, position_idx, tp_price, sl_price)
                if "error" not in result:
                    return result
                    
                # Check for specific errors
                if "zero position" in str(result.get("error", "")).lower():
                    self.logger.warning(f"Position no longer exists for {symbol}")
                    return {"status": "skipped", "reason": "position_closed"}
                
                # If we get here, there was an error but we might retry
                self.logger.warning(f"Error setting TP/SL (attempt {attempt+1}/{max_retries}): {result.get('error')}")
                time.sleep(retry_delay)
                
            except Exception as e:
                self.logger.error(f"Exception setting TP/SL (attempt {attempt+1}/{max_retries}): {str(e)}")
                time.sleep(retry_delay)
        
        # If we get here, all retries failed
        return {"status": "error", "reason": "max_retries_exceeded"}
    
    # ========== ORDER MANAGEMENT METHODS ==========
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """
        Cancel a specific order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            Dictionary with cancel result
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/cancel-order
        """
        try:
            # Log the request
            self.logger.info(f"Cancelling order {order_id} for {symbol}")
            
            # Prepare parameters for the cancel endpoint
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            
            # Make the API request to cancel the order
            response = self.transport.raw_request("POST", "/v5/order/cancel", params)
            
            self.logger.info(f"Order {order_id} for {symbol} cancelled")
            return response
            
        except Exception as e:
            # Check for order already cancelled/filled errors
            if "order not exists" in str(e).lower() or "not allowed to cancel" in str(e).lower():
                self.logger.warning(f"Order {order_id} already cancelled/filled")
                return {
                    "success": True, 
                    "message": "Order already cancelled or filled",
                    "orderId": order_id
                }
                
            self.logger.error(f"Error cancelling order: {str(e)}")
            return {"error": str(e)}
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """
        Cancel all open orders for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with cancel result
            
        References:
            https://bybit-exchange.github.io/docs/v5/order/cancel-all
        """
        try:
            # Log the request
            self.logger.info(f"Cancelling all orders for {symbol}")
            
            # Prepare parameters for the cancel-all endpoint
            params = {
                "category": "linear",
                "symbol": symbol
            }
            
            # Make the API request to cancel all orders
            response = self.transport.raw_request("POST", "/v5/order/cancel-all", params)
            
            self.logger.info(f"All orders cancelled for {symbol}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {str(e)}")
            return {"error": str(e)}
    
    def close_position(self, symbol: str) -> Dict:
        """
        Close an entire position with a market order
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with close result
        """
        try:
            # Get current position
            positions = self.get_positions(symbol)
            
            if not positions or float(positions[0].get("size", "0")) == 0:
                self.logger.info(f"No position to close for {symbol}")
                return {"info": "No position to close"}
                
            position = positions[0]
            position_size = position.get("size", "0")
            position_side = position.get("side", "")
            
            if float(position_size) == 0:
                self.logger.info(f"Position size is zero for {symbol}")
                return {"info": "Position size is zero"}
                
            # Determine opposite side for closing
            close_side = "Sell" if position_side == "Buy" else "Buy"
            
            # Place market order to close with reduce_only flag
            result = self.place_active_order(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=position_size,
                reduce_only=True,
                time_in_force="IOC"  # Immediate or Cancel
            )
            
            self.logger.info(f"Position closed for {symbol}: {position_side} {position_size} with {close_side} order")
            
            # Clear position from cache immediately
            if symbol in self.position_cache:
                del self.position_cache[symbol]
                if symbol in self.position_cache_timestamp:
                    del self.position_cache_timestamp[symbol]
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            return {"error": str(e)}
    
    def cancel_and_replace(self, symbol: str, order_id: str, **kwargs) -> Dict:
        """
        Cancel an existing order and place a new one atomically (for OCO scenarios)
        
        Args:
            symbol: Trading symbol
            order_id: Existing order ID to cancel
            **kwargs: Parameters for new order (see place_active_order)
            
        Returns:
            Dictionary with new order details or error
        """
        try:
            # Cancel the existing order
            cancel_result = self.cancel_order(symbol, order_id)
            
            # Check if cancellation succeeded
            if "error" in cancel_result:
                # If order was already filled/cancelled, that's fine for our purpose
                if "already cancelled" not in str(cancel_result.get("message", "")).lower() and \
                   "already filled" not in str(cancel_result.get("message", "")).lower():
                    self.logger.error(f"Failed to cancel order {order_id} for replacement: {cancel_result.get('error')}")
                    return {"error": f"Cancel failed: {cancel_result.get('error')}"}
            
            # Small delay to ensure cancellation is processed
            time.sleep(0.1)
            
            # Place the new order
            new_order = self.place_active_order(**kwargs)
            
            if "error" in new_order:
                self.logger.error(f"Failed to place replacement order: {new_order.get('error')}")
                return {"error": f"Replacement failed: {new_order.get('error')}", "cancel_result": cancel_result}
            
            self.logger.info(f"Successfully replaced order {order_id} with new order {new_order.get('orderId')}")
            return {
                "success": True,
                "old_order_id": order_id,
                "new_order": new_order,
                "cancel_result": cancel_result
            }
            
        except Exception as e:
            self.logger.error(f"Error in cancel_and_replace: {str(e)}")
            return {"error": str(e)}
    
    # ========== ENHANCED TRADING METHODS ==========
    
    def get_executions(self, symbol: Optional[str] = None, order_id: Optional[str] = None, **kwargs) -> List[Dict]:
        """
        Query users' execution records, sorted by execTime in descending order.
        
        Args:
            symbol: Optional symbol name to filter results
            order_id: Optional order ID to filter
            **kwargs: Additional parameters including:
                startTime: Start timestamp
                endTime: End timestamp
                limit: Maximum number of results
                cursor: Cursor for pagination
                
        Returns:
            List of execution records
            
        References:
            https://bybit-exchange.github.io/docs/v5/execution/execution-list
        """
        try:
            params = {
                "category": "linear"
            }
            
            if symbol:
                params["symbol"] = symbol
                
            if order_id:
                params["orderId"] = order_id
                
            # Add any additional parameters
            for key, value in kwargs.items():
                # Convert snake_case to camelCase for API
                if "_" in key:
                    parts = key.split("_")
                    key = parts[0] + "".join(x.capitalize() for x in parts[1:])
                params[key] = value
            
            # Make the API request
            response = self.transport.raw_request("GET", "/v5/execution/list", params)
            executions = response.get("list", [])
            
            self.logger.info(f"Retrieved {len(executions)} execution records")
            
            return executions
            
        except Exception as e:
            self.logger.error(f"Error getting execution records: {str(e)}")
            return []
    
    def get_closed_pnl(self, symbol: Optional[str] = None, **kwargs) -> List[Dict]:
        """
        Query user's closed profit and loss records.
        
        Args:
            symbol: Optional symbol name to filter results
            **kwargs: Additional parameters including:
                startTime: Start timestamp
                endTime: End timestamp
                limit: Maximum number of results
                cursor: Cursor for pagination
                
        Returns:
            List of closed PNL records
            
        References:
            https://bybit-exchange.github.io/docs/v5/position/closed-pnl
        """
        try:
            params = {
                "category": "linear"
            }
            
            if symbol:
                params["symbol"] = symbol
                
            # Add any additional parameters
            for key, value in kwargs.items():
                # Convert snake_case to camelCase for API
                if "_" in key:
                    parts = key.split("_")
                    key = parts[0] + "".join(x.capitalize() for x in parts[1:])
                params[key] = value
            
            # Make the API request
            response = self.transport.raw_request("GET", "/v5/position/closed-pnl", params)
            closed_pnl = response.get("list", [])
            
            self.logger.info(f"Retrieved {len(closed_pnl)} closed PNL records")
            
            return closed_pnl
            
        except Exception as e:
            self.logger.error(f"Error getting closed PNL: {str(e)}")
            return []
    
    # ========== SYNCHRONIZATION METHODS ==========
    
    def synchronize_positions(self) -> Dict[str, Dict]:
        """
        Synchronize position cache with current exchange state
        
        Returns:
            Dictionary of active positions by symbol
        """
        try:
            # Get all current positions from exchange
            all_positions = self.get_positions()
            
            # Create map of active positions by symbol
            active_positions = {}
            for position in all_positions:
                symbol = position.get("symbol")
                size = float(position.get("size", "0"))
                
                if symbol and size != 0:
                    active_positions[symbol] = position
            
            # Update internal cache
            current_time = time.time()
            for symbol, position in active_positions.items():
                self.position_cache[symbol] = position
                self.position_cache_timestamp[symbol] = current_time
            
            # Remove closed positions from cache
            for symbol in list(self.position_cache.keys()):
                if symbol not in active_positions:
                    del self.position_cache[symbol]
                    if symbol in self.position_cache_timestamp:
                        del self.position_cache_timestamp[symbol]
            
            return active_positions
            
        except Exception as e:
            self.logger.error(f"Error synchronizing positions: {str(e)}")
            return {}