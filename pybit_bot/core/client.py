"""
Bybit API Client Implementation
Provides a reliable and consistent interface to the Bybit API
"""

import hmac
import json
import time
import hashlib
import requests
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import urllib.parse

from ..utils.logger import Logger
from ..exceptions import (
    BybitAPIError,
    AuthenticationError,
    RateLimitError,
    InvalidOrderError,
    PositionError
)


@dataclass
class APICredentials:
    """API Credentials container"""
    api_key: str
    api_secret: str
    testnet: bool = False


class BybitClient:
    """
    Core Bybit API client
    
    Handles API requests, authentication, rate limiting, and error handling
    """
    
    API_URLS = {
        "mainnet": "https://api.bybit.com",
        "testnet": "https://api-testnet.bybit.com"
    }
    
    def __init__(self, credentials: APICredentials, logger: Optional[Logger] = None):
        """
        Initialize with API credentials
        
        Args:
            credentials: API credentials (key, secret, testnet flag)
            logger: Optional logger instance
        """
        self.credentials = credentials
        self.logger = logger or Logger("BybitClient")
        
        # Select endpoint based on testnet flag
        self.base_url = self.API_URLS["testnet" if credentials.testnet else "mainnet"]
        self.logger.info(f"BybitClient initialized for {'testnet' if credentials.testnet else 'mainnet'}")
        
        # Rate limiting settings
        self.req_timeout = 10.0  # Request timeout in seconds
        self.max_retries = 3     # Maximum number of retries for transient errors
        self.retry_delay = 1.0   # Initial retry delay in seconds
        
        # Session for connection pooling
        self.session = requests.Session()
        
        # Counter for debugging
        self.request_count = 0
    
    def test_connection(self) -> bool:
        """
        Test API connection by getting server time
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self._make_request("GET", "/v5/market/time", auth_required=False)
            if response and "timeSecond" in response:
                self.logger.info(f"API connection test successful, server time: {response['timeSecond']}")
                return True
            else:
                self.logger.error(f"API connection test failed: {response}")
                return False
        except Exception as e:
            self.logger.error(f"API connection test failed: {str(e)}")
            return False
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     auth_required: bool = True) -> Any:
        """
        Make an API request with authentication and error handling
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            params: Request parameters
            auth_required: Whether authentication is required
            
        Returns:
            Response data
        """
        # Increment request counter
        self.request_count += 1
        
        # Prepare parameters
        params = params or {}
        
        # Log API request (debug)
        self.logger.debug(f"{method} {endpoint} with params: {params}")
        
        # Add authentication if required
        if auth_required:
            params = self._sign_request(params)
        
        # Prepare URL
        url = f"{self.base_url}{endpoint}"
        
        # Prepare query string or request body based on method
        query_string = ""
        
        if method == "GET":
            # For GET requests, encode parameters in URL
            if params:
                query_string = "?" + urllib.parse.urlencode(params)
                url = f"{url}{query_string}"
            request_kwargs = {}
        else:
            # For POST requests, send parameters as JSON body
            request_kwargs = {"json": params}
        
        # Make request with retries
        retry_count = 0
        while True:
            try:
                # Make request
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.req_timeout,
                    **request_kwargs
                )
                
                # Log response status
                self.logger.debug(f"Response status: {response.status_code}")
                
                # Parse response
                try:
                    data = response.json()
                    self.logger.debug(f"Response data: {str(data)[:300]}...")
                except ValueError:
                    self.logger.error(f"Failed to parse response as JSON: {response.text[:300]}")
                    data = {"ret_code": -1, "ret_msg": "Invalid JSON response"}
                
                # Check for errors
                if response.status_code != 200:
                    error_msg = data.get("ret_msg", f"HTTP {response.status_code}")
                    error_code = data.get("ret_code", response.status_code)
                    
                    # Handle different error types
                    if response.status_code == 401 or error_code == 10000:  # Authentication error
                        raise AuthenticationError(f"Authentication failed: {error_msg}")
                    elif response.status_code == 429 or error_code == 10006:  # Rate limit
                        if retry_count < self.max_retries:
                            # Exponential backoff for rate limit
                            wait_time = self.retry_delay * (2 ** retry_count)
                            self.logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {retry_count+1})")
                            time.sleep(wait_time)
                            retry_count += 1
                            continue
                        else:
                            raise RateLimitError(f"Rate limit exceeded: {error_msg}")
                    else:
                        raise BybitAPIError(f"API error {error_code}: {error_msg}")
                
                # Check for API-level errors
                if data.get("ret_code", 0) != 0:
                    error_msg = data.get("ret_msg", "Unknown error")
                    error_code = data.get("ret_code", -1)
                    
                    # Special handling for order errors
                    if error_code in (30000, 30001, 30002, 30003, 30024, 30025):
                        raise InvalidOrderError(f"Order error {error_code}: {error_msg}")
                    elif error_code in (30004, 30006, 30007, 30008, 30022):
                        raise PositionError(f"Position error {error_code}: {error_msg}")
                    elif error_code == 10004:  # Signature error
                        # Include more diagnostic info for signature errors
                        self.logger.error(f"Signature error: {error_msg}")
                        if "origin_string" in error_msg:
                            # Log the unsigned string for debugging
                            self.logger.error(f"Unsigned string: {error_msg.split('origin_string')[1]}")
                        if retry_count < self.max_retries:
                            # Retry signature errors with updated timestamp
                            wait_time = self.retry_delay * (2 ** retry_count)
                            self.logger.warning(f"Signature error, retrying in {wait_time}s (attempt {retry_count+1})")
                            time.sleep(wait_time)
                            
                            # Update timestamp for retry
                            if auth_required and "timestamp" in params:
                                params["timestamp"] = str(int(time.time() * 1000))
                                params = self._sign_request(params)
                                if method == "GET":
                                    query_string = "?" + urllib.parse.urlencode(params)
                                    url = f"{self.base_url}{endpoint}{query_string}"
                                else:
                                    request_kwargs = {"json": params}
                                
                            retry_count += 1
                            continue
                        else:
                            raise AuthenticationError(f"Signature error: {error_msg}")
                    else:
                        raise BybitAPIError(f"API error {error_code}: {error_msg}")
                
                # Extract result from response
                if "result" in data and data["result"] is not None:
                    return data["result"]
                else:
                    return data
                
            except (requests.RequestException, ConnectionError, TimeoutError) as e:
                # Handle network errors with retries
                if retry_count < self.max_retries:
                    wait_time = self.retry_delay * (2 ** retry_count)
                    self.logger.warning(f"Network error: {str(e)}, retrying in {wait_time}s (attempt {retry_count+1})")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                else:
                    self.logger.error(f"Network error after {retry_count} retries: {str(e)}")
                    raise BybitAPIError(f"Network error: {str(e)}")
    
    def _sign_request(self, params: Dict) -> Dict:
        """
        Sign request with API key and secret
        
        Args:
            params: Request parameters
            
        Returns:
            Signed parameters
        """
        # Add API key and timestamp
        params["api_key"] = self.credentials.api_key
        
        # Ensure timestamp is present and fresh
        if "timestamp" not in params:
            params["timestamp"] = str(int(time.time() * 1000))
        
        # Add recv_window if not present
        if "recv_window" not in params:
            params["recv_window"] = "5000"
        
        # Sort parameters alphabetically by key
        sorted_params = dict(sorted(params.items()))
        
        # Create signature string
        query_string = urllib.parse.urlencode(sorted_params)
        
        # Generate HMAC signature
        signature = hmac.new(
            self.credentials.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Add signature to parameters
        sorted_params["sign"] = signature
        
        # Return signed parameters
        return sorted_params
    
    # ========== PUBLIC ENDPOINTS ==========
    
    def get_market_time(self) -> Dict:
        """
        Get server time
        
        Returns:
            Server time data
        """
        return self._make_request("GET", "/v5/market/time", auth_required=False)
    
    def get_server_time(self) -> Dict:
        """
        Get server time (alias for get_market_time for compatibility)
        
        Returns:
            Server time data
        """
        return self.get_market_time()
    
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
        """
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
        
        result = self._make_request("GET", "/v5/market/kline", params, auth_required=False)
        klines = result.get("list", [])
        
        self.logger.info(f"Retrieved {len(klines)} klines for {symbol}")
        
        return klines
    
    def get_ticker(self, symbol: str) -> Dict:
        """
        Get latest price ticker
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Ticker data
        """
        params = {
            "category": "linear",
            "symbol": symbol
        }
        
        result = self._make_request("GET", "/v5/market/tickers", params, auth_required=False)
        tickers = result.get("list", [])
        
        if tickers:
            return tickers[0]
        else:
            return {}
    
    def get_orderbook(self, symbol: str, limit: int = 25) -> Dict:
        """
        Get orderbook data
        
        Args:
            symbol: Trading symbol
            limit: Depth of orderbook (default: 25)
            
        Returns:
            Orderbook data
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "limit": limit
        }
        
        return self._make_request("GET", "/v5/market/orderbook", params, auth_required=False)
    
    # ========== PRIVATE ENDPOINTS ==========
    
    def get_wallet_balance(self, coin: Optional[str] = None) -> Dict:
        """
        Get wallet balance
        
        Args:
            coin: Optional coin to filter (e.g., USDT)
            
        Returns:
            Wallet balance data
        """
        params = {
            "accountType": "UNIFIED"
        }
        if coin:
            params["coin"] = coin
            
        return self._make_request("GET", "/v5/account/wallet-balance", params)
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get positions
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            List of positions
        """
        params = {
            "category": "linear"
        }
        if symbol:
            params["symbol"] = symbol
            
        result = self._make_request("GET", "/v5/position/list", params)
        return result.get("list", [])
    
    def place_order(self, symbol: str, side: str, order_type: str, qty: str, 
                   price: Optional[str] = None, order_link_id: Optional[str] = None,
                   take_profit: Optional[str] = None, stop_loss: Optional[str] = None,
                   **kwargs) -> Dict:
        """
        Place a new order
        
        Args:
            symbol: Trading symbol
            side: Order side (Buy/Sell)
            order_type: Order type (Market/Limit)
            qty: Order quantity
            price: Order price (required for Limit orders)
            order_link_id: Optional client order ID
            take_profit: Optional take profit price
            stop_loss: Optional stop loss price
            **kwargs: Additional parameters
            
        Returns:
            Order placement result
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty
        }
        
        # Add optional parameters
        if price and order_type.lower() != "market":
            params["price"] = price
            
        if order_link_id:
            params["orderLinkId"] = order_link_id
            
        if take_profit:
            params["takeProfit"] = take_profit
            
        if stop_loss:
            params["stopLoss"] = stop_loss
            
        # Add any additional parameters
        for key, value in kwargs.items():
            # Convert from snake_case to camelCase
            key_parts = key.split('_')
            camel_key = key_parts[0] + ''.join(x.title() for x in key_parts[1:])
            params[camel_key] = value
            
        return self._make_request("POST", "/v5/order/create", params)
    
    def cancel_order(self, symbol: str, order_id: Optional[str] = None, 
                    order_link_id: Optional[str] = None) -> Dict:
        """
        Cancel an order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            order_link_id: Client order ID
            
        Returns:
            Cancellation result
        """
        params = {
            "category": "linear",
            "symbol": symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        else:
            raise ValueError("Either order_id or order_link_id must be provided")
            
        return self._make_request("POST", "/v5/order/cancel", params)
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict:
        """
        Cancel all active orders
        
        Args:
            symbol: Optional symbol to filter
            
        Returns:
            Cancellation result
        """
        params = {
            "category": "linear"
        }
        if symbol:
            params["symbol"] = symbol
            
        return self._make_request("POST", "/v5/order/cancel-all", params)
    
    def get_order_history(self, symbol: Optional[str] = None, order_id: Optional[str] = None, 
                         order_link_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Get order history
        
        Args:
            symbol: Optional symbol to filter
            order_id: Optional order ID to filter
            order_link_id: Optional client order ID to filter
            limit: Maximum number of orders to return
            
        Returns:
            List of orders
        """
        params = {
            "category": "linear",
            "limit": limit
        }
        
        if symbol:
            params["symbol"] = symbol
        if order_id:
            params["orderId"] = order_id
        if order_link_id:
            params["orderLinkId"] = order_link_id
            
        result = self._make_request("GET", "/v5/order/history", params)
        return result.get("list", [])
    
    def get_active_orders(self, symbol: Optional[str] = None, order_id: Optional[str] = None, 
                         order_link_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Get active orders
        
        Args:
            symbol: Optional symbol to filter
            order_id: Optional order ID to filter
            order_link_id: Optional client order ID to filter
            limit: Maximum number of orders to return
            
        Returns:
            List of active orders
        """
        params = {
            "category": "linear",
            "limit": limit
        }
        
        if symbol:
            params["symbol"] = symbol
        if order_id:
            params["orderId"] = order_id
        if order_link_id:
            params["orderLinkId"] = order_link_id
            
        result = self._make_request("GET", "/v5/order/realtime", params)
        return result.get("list", [])
    
    def set_leverage(self, symbol: str, leverage: int, leverage_type: str = "isolated") -> Dict:
        """
        Set leverage for a symbol
        
        Args:
            symbol: Trading symbol
            leverage: Leverage value
            leverage_type: Leverage type (isolated/cross)
            
        Returns:
            Leverage setting result
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage)
        }
        
        return self._make_request("POST", "/v5/position/set-leverage", params)
    
    def set_position_mode(self, symbol: str, mode: str) -> Dict:
        """
        Set position mode
        
        Args:
            symbol: Trading symbol
            mode: Position mode (0: Merged Single, 3: Both Sides)
            
        Returns:
            Position mode setting result
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "mode": mode
        }
        
        return self._make_request("POST", "/v5/position/switch-mode", params)
    
    def set_position_tpsl(self, symbol: str, tp_price: Optional[str] = None, 
                         sl_price: Optional[str] = None, position_idx: int = 0) -> Dict:
        """
        Set take profit and stop loss for a position
        
        Args:
            symbol: Trading symbol
            tp_price: Take profit price
            sl_price: Stop loss price
            position_idx: Position index (0: one-way mode)
            
        Returns:
            Take profit/stop loss setting result
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "positionIdx": position_idx
        }
        
        if tp_price:
            params["takeProfit"] = tp_price
        if sl_price:
            params["stopLoss"] = sl_price
            
        return self._make_request("POST", "/v5/position/trading-stop", params)