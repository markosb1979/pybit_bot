"""
Order Manager Client - Specialized client for order management operations
Built with the same pattern as the core BybitClient
"""

import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
import json

from pybit.unified_trading import HTTP
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
    Built on top of BybitClient for reliability and consistency
    """

    def __init__(self, client, logger: Optional[Logger] = None, config: Optional[Any] = None):
        """
        Initialize with BybitClient instance
        """
        self.client = client
        self.logger = logger or Logger("OrderManagerClient")
        self.config = config
        
        # Default settings
        self.default_symbol = getattr(config, 'default_symbol', "BTCUSDT") if config else "BTCUSDT"
        self.max_leverage = getattr(config, 'max_leverage', 10) if config else 10
        
        # Cache for instrument info
        self._instrument_info_cache = {}
        
    # ========== INFORMATION METHODS ==========
    
    def get_instrument_info(self, symbol: str) -> Dict:
        """
        Get instrument specifications with caching
        """
        # Check cache first
        if symbol in self._instrument_info_cache:
            return self._instrument_info_cache[symbol]
            
        # Fetch instrument info
        try:
            response = self.client._make_request(
                "GET", 
                "/v5/market/instruments-info", 
                {
                    "category": "linear",
                    "symbol": symbol
                }, 
                auth_required=False
            )
            
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
        """
        symbol = symbol or self.default_symbol
        try:
            params = {"category": "linear"}
            if symbol:
                params["symbol"] = symbol
                
            response = self.client._make_request("GET", "/v5/position/list", params)
            return response.get("list", [])
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            return []
    
    def get_account_balance(self) -> Dict:
        """
        Get account wallet balance
        """
        try:
            response = self.client._make_request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
            
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
        """
        try:
            params = {"category": "linear"}
            if symbol:
                params["symbol"] = symbol
                
            response = self.client._make_request("GET", "/v5/order/realtime", params)
            return response.get("list", [])
        except Exception as e:
            self.logger.error(f"Error getting active orders: {str(e)}")
            return []
    
    def get_order_status(self, symbol: str, order_id: str) -> str:
        """
        Get current status of an order
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
    
    def get_order_history(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get historical orders
        """
        try:
            params = {"category": "linear"}
            if symbol:
                params["symbol"] = symbol
                
            response = self.client._make_request("GET", "/v5/order/history", params)
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
        """
        try:
            self.logger.info(f"Getting order info for {order_id} on {symbol}")
            
            # Check history
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            
            # Try getting order history
            response = self.client._make_request("GET", "/v5/order/history", params)
            orders = response.get("list", [])
            
            if orders:
                for order in orders:
                    if order.get("orderId") == order_id:
                        return order
            
            # If not found, try executions
            exec_params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            
            response = self.client._make_request("GET", "/v5/execution/list", exec_params)
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
    
    # ========== POSITION SIZING METHODS ==========
    
    def _round_quantity(self, symbol: str, quantity: float) -> str:
        """
        Round quantity to valid precision based on instrument specs
        """
        info = self.get_instrument_info(symbol)
        
        if not info:
            # Default to 3 decimal places if info not available
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
        """
        info = self.get_instrument_info(symbol)
        
        if not info:
            # Default to 2 decimal places if info not available
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
            ticker_params = {
                "category": "linear",
                "symbol": symbol
            }
            response = self.client._make_request("GET", "/v5/market/tickers", ticker_params, auth_required=False)
            tickers = response.get("list", [])
            if tickers:
                price = float(tickers[0].get("lastPrice", 0))
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
                
        Returns:
            Order result dictionary
        """
        try:
            # Prepare parameters
            params = {
                "category": "linear",
                "symbol": kwargs.get("symbol"),
                "side": kwargs.get("side"),
                "orderType": kwargs.get("order_type"),
                "qty": kwargs.get("qty"),
                "price": kwargs.get("price"),
                "reduceOnly": kwargs.get("reduce_only"),
                "closeOnTrigger": kwargs.get("close_on_trigger"),
                "timeInForce": kwargs.get("time_in_force", "GTC"),
                "takeProfit": kwargs.get("take_profit"),
                "stopLoss": kwargs.get("stop_loss"),
                "tpTriggerBy": kwargs.get("tp_trigger_by"),
                "slTriggerBy": kwargs.get("sl_trigger_by"),
                "orderLinkId": kwargs.get("order_link_id")
            }
            
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            
            # Place order
            response = self.client._make_request("POST", "/v5/order/create", params)
            
            self.logger.info(f"Order placed: {params['side']} {params['orderType']} for {params['symbol']}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error placing order: {str(e)}")
            return {"error": str(e)}
    
    def place_market_order(self, symbol: str, side: str, qty: str) -> Dict:
        """
        Place market order with simplified parameters
        """
        return self.place_active_order(
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty
        )
    
    def place_limit_order(self, symbol: str, side: str, qty: str, price: str) -> Dict:
        """
        Place limit order with simplified parameters
        """
        return self.place_active_order(
            symbol=symbol,
            side=side,
            order_type="Limit",
            qty=qty,
            price=price
        )
    
    def enter_position_market(self, symbol: str, side: str, qty: float) -> Dict:
        """
        Enter a position with a market order WITHOUT TP/SL.
        For use with post-fill TP/SL strategy.
        
        Args:
            symbol: Trading symbol
            side: "Buy" or "Sell"
            qty: Position size
            
        Returns:
            Dictionary with order results including order ID
        """
        # Generate a unique order link ID
        direction = "LONG" if side == "Buy" else "SHORT"
        order_link_id = f"{direction}_{symbol}_{int(time.time() * 1000)}"
        
        # Convert qty to string if it's a float
        qty_str = str(qty) if isinstance(qty, str) else self._round_quantity(symbol, qty)
        
        return self.place_active_order(
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty_str,
            order_link_id=order_link_id
        )
    
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
                trailingStop: Trailing stop distance
                tpTriggerBy: Trigger type for take profit
                slTriggerBy: Trigger type for stop loss
                tpslMode: TP/SL mode
                tpSize: Take profit size
                slSize: Stop loss size
                tpLimitPrice: Take profit limit price
                slLimitPrice: Stop loss limit price
                
        Returns:
            Dictionary with API response
        """
        try:
            # Prepare parameters
            params = {
                "category": "linear",
                **kwargs
            }
            
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            
            # Make the API request
            response = self.client._make_request("POST", "/v5/position/trading-stop", params)
            
            self.logger.info(f"Trading stop set for {params['symbol']}")
            return response
            
        except Exception as e:
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
        """
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
        """
        params = {
            "symbol": symbol,
            "stopLoss": str(stopLoss),
            "slTriggerBy": kwargs.get("slTriggerBy", "MarkPrice"),
            "positionIdx": kwargs.get("positionIdx", 0)
        }
        
        return self.set_trading_stop(**params)
    
    def set_position_tpsl(self, symbol: str, position_idx: int, tp_price: str, sl_price: str) -> Dict:
        """
        Set both take profit and stop loss for an existing position in one call.
        
        Args:
            symbol: Trading symbol
            position_idx: Position index (0 for one-way mode)
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with TP/SL setting result
        """
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
    
    # ========== ORDER MANAGEMENT METHODS ==========
    
    def cancel_order(self, symbol: str, order_id: str, **kwargs) -> Dict:
        """
        Cancel a specific order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with cancel result
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            
            response = self.client._make_request("POST", "/v5/order/cancel", params)
            
            self.logger.info(f"Order {order_id} for {symbol} cancelled")
            return response
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return {"error": str(e)}
    
    def cancel_all_orders(self, symbol: str, **kwargs) -> Dict:
        """
        Cancel all open orders for a symbol
        
        Args:
            symbol: Trading symbol
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with cancel result
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol
            }
            
            response = self.client._make_request("POST", "/v5/order/cancel-all", params)
            
            self.logger.info(f"All orders cancelled for {symbol}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {str(e)}")
            return {"error": str(e)}
    
    def close_position(self, symbol: str, **kwargs) -> Dict:
        """
        Close an entire position with a market order
        
        Args:
            symbol: Trading symbol
            **kwargs: Additional parameters
            
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
            
            # Place market order to close
            result = self.place_active_order(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=position_size,
                reduce_only=True,
                time_in_force="IOC"  # Immediate or Cancel
            )
            
            self.logger.info(f"Position closed for {symbol}: {position_side} {position_size} with {close_side} order")
            return result
            
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            return {"error": str(e)}
    
    # ========== ENHANCED TRADING METHODS ==========
    
    def get_executions(self, symbol: Optional[str] = None, **kwargs) -> List[Dict]:
        """
        Query users' execution records, sorted by execTime in descending order.
        
        Args:
            symbol: Optional symbol name to filter results
            **kwargs: Additional parameters including:
                orderId: Order ID
                startTime: Start timestamp
                endTime: End timestamp
                limit: Maximum number of results
                cursor: Cursor for pagination
                
        Returns:
            List of execution records
        """
        try:
            params = {
                "category": "linear",
                **kwargs
            }
            
            if symbol:
                params["symbol"] = symbol
            
            # Make the API request
            response = self.client._make_request("GET", "/v5/execution/list", params)
            
            # Extract and return the execution list
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
        """
        try:
            params = {
                "category": "linear",
                **kwargs
            }
            
            if symbol:
                params["symbol"] = symbol
            
            # Make the API request
            response = self.client._make_request("GET", "/v5/position/closed-pnl", params)
            
            # Extract and return the closed PNL list
            closed_pnl = response.get("list", [])
            self.logger.info(f"Retrieved {len(closed_pnl)} closed PNL records")
            
            return closed_pnl
            
        except Exception as e:
            self.logger.error(f"Error getting closed PNL: {str(e)}")
            return []