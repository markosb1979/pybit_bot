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
        self.logger = logger or Logger("OrderManagerClient")
        self.logger.debug(f"→ __init__(transport={transport}, logger={logger}, config={config})")
        
        self.transport = transport
        self.config = config
        
        # Default settings
        self.default_symbol = getattr(config, 'default_symbol', "BTCUSDT") if config else "BTCUSDT"
        self.max_leverage = getattr(config, 'max_leverage', 10) if config else 10
        
        # Cache position information to reduce API calls
        self.position_cache = {}
        self.position_cache_timestamp = {}
        self.position_cache_ttl = 1.0  # 1 second cache TTL
        
        # Cache instrument info for tick size derivation
        try:
            self.logger.debug("Fetching instruments info for cache")
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
        self.logger.debug(f"← __init__ completed")
        
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
        self.logger.debug(f"→ get_instrument_info(symbol={symbol})")
        
        # Check cache first
        if symbol in self._instrument_info_cache:
            result = self._instrument_info_cache[symbol]
            self.logger.debug(f"← get_instrument_info returned cached info for {symbol}")
            return result
            
        # Check if it's in the global cache already
        if symbol in self._instrument_info:
            self._instrument_info_cache[symbol] = self._instrument_info[symbol]
            result = self._instrument_info[symbol]
            self.logger.debug(f"← get_instrument_info returned info from global cache for {symbol}")
            return result
            
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
                self.logger.debug(f"← get_instrument_info returned empty dict (not found)")
                return {}
                
            # Cache the info
            self._instrument_info_cache[symbol] = instruments[0]
            self.logger.debug(f"← get_instrument_info returned fresh info for {symbol}")
            return instruments[0]
            
        except Exception as e:
            self.logger.error(f"Error fetching instrument info: {str(e)}")
            self.logger.debug(f"← get_instrument_info returned empty dict (error)")
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
        self.logger.debug(f"→ get_positions(symbol={symbol})")
        
        try:
            # Check cache for this symbol if requested
            current_time = time.time()
            if symbol and symbol in self.position_cache:
                cache_age = current_time - self.position_cache_timestamp.get(symbol, 0)
                if cache_age < self.position_cache_ttl:
                    # Return cached position
                    result = [self.position_cache[symbol]]
                    self.logger.debug(f"← get_positions returned {len(result)} positions from cache")
                    return result
            
            # FIX: Ensure proper parameters for position listing
            params = {
                "category": "linear",
                "settleCoin": "USDT"  # Added settleCoin as a fallback if symbol isn't provided
            }
            
            # Only add symbol if provided (not None or empty string)
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
            
            self.logger.debug(f"← get_positions returned {len(positions)} positions")
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            self.logger.debug(f"← get_positions returned empty list (error)")
            return []
    
    def get_account_balance(self) -> Dict:
        """
        Get account wallet balance
        
        Returns:
            Dictionary with balance information
            
        References:
            https://bybit-exchange.github.io/docs/v5/account/wallet-balance
        """
        self.logger.debug(f"→ get_account_balance()")
        
        try:
            response = self.transport.raw_request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
            
            # Extract USDT balance for convenience
            if isinstance(response, list) and response:
                for account in response:
                    coins = account.get("coin", [])
                    for coin in coins:
                        if coin.get("coin") == "USDT":
                            result = {
                                "totalBalance": coin.get("walletBalance", "0"),
                                "totalAvailableBalance": coin.get("availableToWithdraw", "0"),
                                "equity": coin.get("equity", "0")
                            }
                            self.logger.debug(f"← get_account_balance returned balance: {result}")
                            return result
            
            result = {"totalAvailableBalance": "0"}
            self.logger.debug(f"← get_account_balance returned default balance: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting account balance: {str(e)}")
            result = {"totalAvailableBalance": "0"}
            self.logger.debug(f"← get_account_balance returned default balance due to error: {result}")
            return result
    
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
        self.logger.debug(f"→ get_open_orders(symbol={symbol})")
        
        try:
            params = {
                "category": "linear"
            }
            
            if symbol:
                params["symbol"] = symbol
                
            response = self.transport.raw_request("GET", "/v5/order/realtime", params)
            orders = response.get("list", [])
            
            self.logger.debug(f"← get_open_orders returned {len(orders)} orders")
            return orders
            
        except Exception as e:
            self.logger.error(f"Error getting active orders: {str(e)}")
            self.logger.debug(f"← get_open_orders returned empty list (error)")
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
        self.logger.debug(f"→ get_order(symbol={symbol}, order_id={order_id})")
        
        try:
            self.logger.info(f"Getting order info for {order_id} on {symbol}")
            
            # Check history
            orders = self.get_order_history(symbol, order_id)
            
            if orders:
                for order in orders:
                    if order.get("orderId") == order_id:
                        self.logger.debug(f"← get_order returned order from history")
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
                        self.logger.debug(f"← get_order returned active order")
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
                result = {
                    "orderId": order_id,
                    "symbol": symbol,
                    "side": execution.get("side"),
                    "orderStatus": "Filled",
                    "avgPrice": execution.get("execPrice"),
                    "leavesQty": "0",
                    "execQty": execution.get("execQty"),
                    "execFee": execution.get("execFee")
                }
                self.logger.debug(f"← get_order returned order constructed from execution")
                return result
                
            # Order not found in any of the endpoints
            result = {"status": "NotFound", "orderId": order_id}
            self.logger.debug(f"← get_order returned NotFound status")
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting order info: {str(e)}")
            result = {"status": "Error", "message": str(e), "orderId": order_id}
            self.logger.debug(f"← get_order returned error status")
            return result
    
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
        self.logger.debug(f"→ get_order_history(symbol={symbol}, order_id={order_id})")
        
        try:
            params = {
                "category": "linear"
            }
            
            if symbol:
                params["symbol"] = symbol
                
            if order_id:
                params["orderId"] = order_id
                
            response = self.transport.raw_request("GET", "/v5/order/history", params)
            orders = response.get("list", [])
            
            self.logger.debug(f"← get_order_history returned {len(orders)} orders")
            return orders
            
        except Exception as e:
            self.logger.error(f"Error getting order history: {str(e)}")
            self.logger.debug(f"← get_order_history returned empty list (error)")
            return []
    
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
        self.logger.debug(f"→ get_order_fill_info(symbol={symbol}, order_id={order_id})")
        
        try:
            # Get order details
            order_info = self.get_order(symbol, order_id)
            
            # Check if order is filled
            if order_info.get("orderStatus") == "Filled":
                result = {
                    "filled": True,
                    "fill_price": float(order_info.get("avgPrice", 0)),
                    "side": order_info.get("side"),
                    "position_idx": 0  # Default for one-way mode
                }
                self.logger.debug(f"← get_order_fill_info returned filled status: {result}")
                return result
            elif "orderStatus" in order_info:
                result = {"filled": False, "status": order_info.get("orderStatus")}
                self.logger.debug(f"← get_order_fill_info returned not filled status: {result}")
                return result
            
            # If order not found, check positions for recent fills
            positions = self.get_positions(symbol)
            if positions and float(positions[0].get("size", "0")) > 0:
                # Position exists, order likely filled
                position = positions[0]
                result = {
                    "filled": True,
                    "fill_price": float(position.get("avgPrice", 0)),
                    "side": position.get("side"),
                    "position_idx": position.get("positionIdx", 0)
                }
                self.logger.debug(f"← get_order_fill_info returned filled status from position: {result}")
                return result
                
            # Order not found anywhere
            self.logger.warning(f"Order {order_id} not found for {symbol}")
            result = {"filled": False, "status": "Not Found"}
            self.logger.debug(f"← get_order_fill_info returned not found status: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting order fill info: {str(e)}")
            result = {"filled": False, "error": str(e)}
            self.logger.debug(f"← get_order_fill_info returned error status: {result}")
            return result
    
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
        self.logger.debug(f"→ get_instruments_info(category={category})")
        
        try:
            self.logger.debug(f"Getting instruments info for {category}")
            
            params = {
                "category": category
            }
            
            response = self.transport.raw_request("GET", "/v5/market/instruments-info", params, auth_required=False)
            
            if not response:
                self.logger.error("Error getting instruments info: Empty response")
                result = {"list": []}
                self.logger.debug(f"← get_instruments_info returned empty list (no response)")
                return result
            
            instruments_count = len(response.get("list", []))
            self.logger.debug(f"← get_instruments_info returned info for {instruments_count} instruments")
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting instruments info: {str(e)}")
            result = {"list": []}
            self.logger.debug(f"← get_instruments_info returned empty list (error)")
            return result
    
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
        self.logger.debug(f"→ get_ticker(symbol={symbol})")
        
        try:
            params = {
                "category": "linear",
                "symbol": symbol
            }
            
            response = self.transport.raw_request("GET", "/v5/market/tickers", params, auth_required=False)
            tickers = response.get("list", [])
            
            if tickers:
                self.logger.debug(f"← get_ticker returned ticker for {symbol}")
                return tickers[0]
            else:
                self.logger.debug(f"← get_ticker returned empty dict (no tickers)")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting ticker: {str(e)}")
            self.logger.debug(f"← get_ticker returned empty dict (error)")
            return {}
    
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
        self.logger.debug(f"→ _round_quantity(symbol={symbol}, quantity={quantity})")
        
        info = self.get_instrument_info(symbol)
        
        if not info:
            # Default to 3 decimal places if info not available
            self.logger.warning(f"No instrument info for {symbol}, using default qty precision (3 decimals)")
            result = "{:.3f}".format(quantity)
            self.logger.debug(f"← _round_quantity returned {result} (default)")
            return result
            
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
        result = "{:.{}f}".format(float(rounded), decimal_places)
        
        self.logger.debug(f"← _round_quantity returned {result}")
        return result
    
    def _round_price(self, symbol: str, price: float) -> str:
        """
        Round price to valid precision based on instrument specs
        
        Args:
            symbol: Trading symbol
            price: Raw price value
            
        Returns:
            Price as string with correct precision
        """
        self.logger.debug(f"→ _round_price(symbol={symbol}, price={price})")
        
        info = self.get_instrument_info(symbol)
        
        if not info:
            # Default to 2 decimal places if info not available
            self.logger.warning(f"No instrument info for {symbol}, using default price precision (2 decimals)")
            result = "{:.2f}".format(price)
            self.logger.debug(f"← _round_price returned {result} (default)")
            return result
            
        # Get price step from instrument info
        price_filter = info.get("priceFilter", {})
        tick_size = price_filter.get("tickSize", "0.01")
        
        # Round to the nearest tick
        step = Decimal(tick_size)
        rounded = Decimal(str(price)).quantize(step)
        
        # Format based on decimal places in step
        decimal_places = len(tick_size.split('.')[-1]) if '.' in tick_size else 0
        result = "{:.{}f}".format(float(rounded), decimal_places)
        
        self.logger.debug(f"← _round_price returned {result}")
        return result
    
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
        self.logger.debug(f"→ calculate_position_size(symbol={symbol}, usdt_amount={usdt_amount}, price={price})")
        
        # Get current price if not provided
        if price is None:
            # Get ticker data
            ticker = self.get_ticker(symbol)
            if ticker:
                price = float(ticker.get("lastPrice", 0))
            else:
                self.logger.error(f"Failed to get ticker for {symbol}")
                self.logger.debug(f"← calculate_position_size returned '0' (failed to get price)")
                return "0"
            
        if price <= 0:
            self.logger.error(f"Invalid price for {symbol}: {price}")
            self.logger.debug(f"← calculate_position_size returned '0' (invalid price)")
            return "0"
            
        # Calculate raw quantity
        raw_quantity = usdt_amount / price
        
        # Round to valid quantity
        rounded_qty = self._round_quantity(symbol, raw_quantity)
        
        self.logger.info(f"Position size for {usdt_amount} USDT of {symbol} at {price}: {rounded_qty}")
        self.logger.debug(f"← calculate_position_size returned {rounded_qty}")
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
        """
        self.logger.debug(f"→ place_active_order(kwargs={kwargs})")
        
        try:
            # Log the raw request parameters for debugging
            self.logger.debug(f"Raw order parameters: {kwargs}")
            
            # Extract required parameters
            symbol = kwargs.get("symbol")
            side = kwargs.get("side")
            order_type = kwargs.get("order_type")
            qty = kwargs.get("qty")
            
            if not all([symbol, side, order_type, qty]):
                self.logger.error(f"Missing required parameters. Received: {kwargs}")
                error_result = {"error": "Missing required parameters: symbol, side, order_type, and qty are required"}
                self.logger.debug(f"← place_active_order returned error: {error_result}")
                raise ValueError("Missing required parameters: symbol, side, order_type, and qty are required")
                
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
            
            # Log the processed parameters
            self.logger.debug(f"Processed order parameters: {params}")
            
            # Make the API request to place the order
            response = self.transport.raw_request("POST", "/v5/order/create", params)
            
            self.logger.info(f"Order placed: {side} {order_type} for {symbol}")
            self.logger.debug(f"← place_active_order returned: {response}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error placing order: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← place_active_order returned error: {error_result}")
            return error_result
    
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
        """
        self.logger.debug(f"→ amend_order(symbol={symbol}, order_id={order_id}, kwargs={kwargs})")
        
        try:
            if not symbol or not order_id:
                error_msg = "Symbol and order_id are required parameters"
                self.logger.error(error_msg)
                error_result = {"error": error_msg}
                self.logger.debug(f"← amend_order returned error: {error_result}")
                raise ValueError(error_msg)
                
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
                result = {
                    "success": True, 
                    "message": "No changes needed", 
                    "orderId": order_id
                }
                self.logger.debug(f"← amend_order returned: {result}")
                return result
                
            self.logger.info(f"Order {order_id} amended successfully")
            self.logger.debug(f"← amend_order returned: {response}")
            return response
            
        except Exception as e:
            # Check for no-modification error (success case)
            if "no modification" in str(e).lower() or "34040" in str(e):
                self.logger.info(f"Order {order_id} already has requested values, no changes needed")
                result = {
                    "success": True, 
                    "message": "No changes needed", 
                    "orderId": order_id
                }
                self.logger.debug(f"← amend_order returned: {result}")
                return result
                
            self.logger.error(f"Error amending order: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← amend_order returned error: {error_result}")
            return error_result
    
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
        self.logger.debug(f"→ enter_position_market(symbol={symbol}, side={side}, qty={qty}, tp_price={tp_price}, sl_price={sl_price})")
        
        # Generate a unique order link ID
        direction = "LONG" if side == "Buy" else "SHORT"
        order_link_id = f"{direction}_{symbol}_{int(time.time() * 1000)}"
        
        # Convert qty to string if it's a float
        qty_str = str(qty) if isinstance(qty, str) else self._round_quantity(symbol, qty)
        
        # Log the exact parameters for debugging
        self.logger.debug(f"enter_position_market - symbol: {symbol}, side: {side}, qty: {qty_str}, " +
                        f"tp_price: {tp_price}, sl_price: {sl_price}")
        
        # FIX: Use direct parameter passing to avoid variable name issues
        result = self.place_active_order(
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty_str,
            take_profit=tp_price,
            stop_loss=sl_price,
            tp_trigger_by="MarkPrice" if tp_price else None,
            sl_trigger_by="MarkPrice" if sl_price else None,
            order_link_id=order_link_id
        )
        
        self.logger.debug(f"← enter_position_market returned: {result}")
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
        self.logger.debug(f"→ set_trading_stop(kwargs={kwargs})")
        
        try:
            # Extract the symbol parameter
            symbol = kwargs.get("symbol")
            if not symbol:
                error_msg = "Symbol is required"
                self.logger.error(error_msg)
                error_result = {"error": error_msg}
                self.logger.debug(f"← set_trading_stop returned error: {error_result}")
                raise ValueError(error_msg)
            
            # FIX: Always include positionIdx (0 for one-way mode is default)
            # Prepare parameters for the trading-stop endpoint
            params = {
                "category": "linear",
                "symbol": symbol,
                "positionIdx": kwargs.get("positionIdx", 0)
            }
            
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
            self.logger.debug(f"← set_trading_stop returned: {response}")
            return response
            
        except Exception as e:
            # Special case handling for "no modification" errors (treat as success)
            if "no modification" in str(e).lower() or "34040" in str(e):
                self.logger.info(f"TP/SL already set to requested values for {kwargs.get('symbol')}")
                result = {
                    "success": True, 
                    "message": "No changes needed", 
                    "symbol": kwargs.get('symbol')
                }
                self.logger.debug(f"← set_trading_stop returned: {result}")
                return result
            # Special case for "zero position" errors
            elif "zero position" in str(e).lower() or "can not set tp/sl/ts for zero position" in str(e).lower():
                self.logger.warning(f"Cannot set TP/SL for zero position: {kwargs.get('symbol')}")
                result = {
                    "success": False,
                    "error": "No active position",
                    "message": "Cannot set TP/SL for a non-existent position"
                }
                self.logger.debug(f"← set_trading_stop returned: {result}")
                return result
            
            self.logger.error(f"Error setting trading stop: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← set_trading_stop returned error: {error_result}")
            return error_result
    
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
        self.logger.debug(f"→ set_position_tpsl(symbol={symbol}, position_idx={position_idx}, tp_price={tp_price}, sl_price={sl_price})")
        
        # Prepare parameters
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
        
        # Add retry logic for better reliability
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                result = self.set_trading_stop(**params)
                if "error" not in result:
                    self.logger.debug(f"← set_position_tpsl returned (attempt {attempt+1}): {result}")
                    return result
                    
                # Check for specific errors
                if "zero position" in str(result.get("error", "")).lower():
                    self.logger.warning(f"Position no longer exists for {symbol}")
                    result = {"status": "skipped", "reason": "position_closed"}
                    self.logger.debug(f"← set_position_tpsl returned: {result}")
                    return result
                
                # If we get here, there was an error but we might retry
                self.logger.warning(f"Error setting TP/SL (attempt {attempt+1}/{max_retries}): {result.get('error')}")
                time.sleep(retry_delay)
                
            except Exception as e:
                self.logger.error(f"Exception setting TP/SL (attempt {attempt+1}/{max_retries}): {str(e)}")
                time.sleep(retry_delay)
        
        # If we get here, all retries failed
        result = {"status": "error", "reason": "max_retries_exceeded"}
        self.logger.debug(f"← set_position_tpsl returned (all retries failed): {result}")
        return result
    
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
        self.logger.debug(f"→ cancel_order(symbol={symbol}, order_id={order_id})")
        
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
            self.logger.debug(f"← cancel_order returned: {response}")
            return response
            
        except Exception as e:
            # Check for order already cancelled/filled errors
            if "order not exists" in str(e).lower() or "not allowed to cancel" in str(e).lower():
                self.logger.warning(f"Order {order_id} already cancelled/filled")
                result = {
                    "success": True, 
                    "message": "Order already cancelled or filled",
                    "orderId": order_id
                }
                self.logger.debug(f"← cancel_order returned: {result}")
                return result
                
            self.logger.error(f"Error cancelling order: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← cancel_order returned error: {error_result}")
            return error_result
    
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
        self.logger.debug(f"→ cancel_all_orders(symbol={symbol})")
        
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
            self.logger.debug(f"← cancel_all_orders returned: {response}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← cancel_all_orders returned error: {error_result}")
            return error_result
    
    def close_position(self, symbol: str) -> Dict:
        """
        Close an entire position with a market order
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with close result
        """
        self.logger.debug(f"→ close_position(symbol={symbol})")
        
        try:
            # Get current position
            positions = self.get_positions(symbol)
            
            if not positions or float(positions[0].get("size", "0")) == 0:
                self.logger.info(f"No position to close for {symbol}")
                result = {"info": "No position to close"}
                self.logger.debug(f"← close_position returned: {result}")
                return result
                
            position = positions[0]
            position_size = position.get("size", "0")
            position_side = position.get("side", "")
            
            if float(position_size) == 0:
                self.logger.info(f"Position size is zero for {symbol}")
                result = {"info": "Position size is zero"}
                self.logger.debug(f"← close_position returned: {result}")
                return result
                
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
            
            self.logger.debug(f"← close_position returned: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            error_result = {"error": str(e)}
            self.logger.debug(f"← close_position returned error: {error_result}")
            return error_result
    
    # ========== SYNCHRONIZATION METHODS ==========
    
    def synchronize_positions(self) -> Dict[str, Dict]:
        """
        Synchronize position cache with current exchange state
        
        Returns:
            Dictionary of active positions by symbol
        """
        self.logger.debug(f"→ synchronize_positions()")
        
        try:
            # FIX: Use settleCoin for more reliable position listing
            params = {
                "category": "linear",
                "settleCoin": "USDT"  # Use settleCoin parameter
            }
            
            # Get all current positions from exchange
            response = self.transport.raw_request("GET", "/v5/position/list", params)
            positions = response.get("list", [])
            
            # Create map of active positions by symbol
            active_positions = {}
            for position in positions:
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
            
            self.logger.debug(f"← synchronize_positions returned {len(active_positions)} active positions")
            return active_positions
            
        except Exception as e:
            self.logger.error(f"Error synchronizing positions: {str(e)}")
            self.logger.debug(f"← synchronize_positions returned empty dict (error)")
            return {}