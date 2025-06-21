"""
Bybit API Client Implementation
Provides a reliable and consistent interface to the Bybit API using the official pybit library
"""

import hmac
import json
import time
import hashlib
import requests
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass
import urllib.parse

# Import official pybit library
from pybit.unified_trading import HTTP, WebSocket

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
        
        # Initialize the official pybit HTTP client
        self.http_client = HTTP(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            testnet=credentials.testnet
        )
        
        # Select endpoint based on testnet flag
        self.base_url = self.API_URLS["testnet" if credentials.testnet else "mainnet"]
        self.logger.info(f"BybitClient initialized for {'testnet' if credentials.testnet else 'mainnet'}")
        
        # Initialize WebSocket clients as None - they will be created when needed
        self.market_stream = None
        self.trade_stream = None
        
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
            response = self.get_server_time()
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
        
        # Call the appropriate pybit HTTP client method based on the endpoint and method
        if endpoint == "/v5/market/time":
            response = self.http_client.get_server_time()
        elif endpoint == "/v5/market/kline":
            response = self.http_client.get_kline(**params)
        elif endpoint == "/v5/market/tickers":
            response = self.http_client.get_tickers(**params)
        elif endpoint == "/v5/market/orderbook":
            response = self.http_client.get_orderbook(**params)
        elif endpoint == "/v5/account/wallet-balance":
            response = self.http_client.get_wallet_balance(**params)
        elif endpoint == "/v5/position/list":
            response = self.http_client.get_positions(**params)
        elif endpoint == "/v5/order/create" and method == "POST":
            response = self.http_client.place_order(**params)
        elif endpoint == "/v5/order/cancel" and method == "POST":
            response = self.http_client.cancel_order(**params)
        elif endpoint == "/v5/order/cancel-all" and method == "POST":
            response = self.http_client.cancel_all_orders(**params)
        elif endpoint == "/v5/order/history":
            response = self.http_client.get_order_history(**params)
        elif endpoint == "/v5/order/realtime":
            response = self.http_client.get_open_orders(**params)
        elif endpoint == "/v5/position/set-leverage" and method == "POST":
            response = self.http_client.set_leverage(**params)
        elif endpoint == "/v5/position/switch-mode" and method == "POST":
            response = self.http_client.switch_position_mode(**params)
        elif endpoint == "/v5/position/trading-stop" and method == "POST":
            response = self.http_client.set_trading_stop(**params)
        elif endpoint == "/v5/execution/list":
            response = self.http_client.get_executions(**params)
        elif endpoint == "/v5/position/closed-pnl":
            response = self.http_client.get_closed_pnl(**params)
        elif endpoint == "/v5/market/instruments-info":
            response = self.http_client.get_instruments_info(**params)
        else:
            # Fallback to direct request for endpoints not explicitly mapped
            self.logger.warning(f"Using fallback request mechanism for endpoint: {endpoint}")
            
            # Add authentication if required
            if auth_required:
                params["api_key"] = self.credentials.api_key
                params["timestamp"] = str(int(time.time() * 1000))
                params["recv_window"] = "5000"
                
                # Sort parameters and create signature
                sorted_params = dict(sorted(params.items()))
                query_string = urllib.parse.urlencode(sorted_params)
                signature = hmac.new(
                    self.credentials.api_secret.encode(),
                    query_string.encode(),
                    hashlib.sha256
                ).hexdigest()
                sorted_params["sign"] = signature
                params = sorted_params
            
            # Prepare URL
            url = f"{self.base_url}{endpoint}"
            
            # Make direct request
            if method == "GET":
                response = self.session.get(url, params=params, timeout=self.req_timeout)
            else:  # POST
                response = self.session.post(url, json=params, timeout=self.req_timeout)
                
            # Parse response
            response = response.json()
        
        # Process and validate the response
        return self._process_response(response)
    
    def _process_response(self, response: Dict) -> Any:
        """
        Process API response
        
        Args:
            response: API response
            
        Returns:
            Processed response data
        """
        # Check for error code in response
        ret_code = response.get("retCode", 0)
        if ret_code != 0:
            error_msg = response.get("retMsg", "Unknown error")
            
            # Map to appropriate exception types
            if ret_code in [10000, 10001]:  # Auth errors
                self.logger.error(f"Authentication error: {error_msg}")
                raise AuthenticationError(f"Authentication failed: {error_msg}")
            elif ret_code == 10006:  # Rate limit
                self.logger.warning(f"Rate limit error: {error_msg}")
                raise RateLimitError(f"Rate limit exceeded: {error_msg}")
            elif ret_code in [30000, 30001, 30002, 30003, 30024, 30025]:  # Order errors
                self.logger.error(f"Order error {ret_code}: {error_msg}")
                raise InvalidOrderError(f"Order error {ret_code}: {error_msg}")
            elif ret_code in [30004, 30006, 30007, 30008, 30022]:  # Position errors
                self.logger.error(f"Position error {ret_code}: {error_msg}")
                raise PositionError(f"Position error {ret_code}: {error_msg}")
            else:
                self.logger.error(f"API error {ret_code}: {error_msg}")
                raise BybitAPIError(f"API error {ret_code}: {error_msg}")
        
        # Extract and return the result
        if "result" in response:
            return response["result"]
        return response
    
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
            
        # Add a small delay before setting TP/SL to avoid race conditions
        time.sleep(0.5)
            
        return self._make_request("POST", "/v5/position/trading-stop", params)
    
    # ========== WEBSOCKET METHODS ==========
    
    async def connect_market_stream(self, symbols: List[str], on_update: Callable):
        """
        Connect to market data stream
        
        Args:
            symbols: List of symbols to subscribe to
            on_update: Callback function for market updates
        """
        try:
            # Ensure we're not already connected
            if self.market_stream:
                self.logger.warning("Market stream already connected, closing existing connection")
                await self.close_market_stream()
            
            # Create a handler for WebSocket messages
            def ws_handler(message):
                # Parse the message
                if not message:
                    return
                
                try:
                    # Dispatch to the callback
                    on_update(message)
                except Exception as e:
                    self.logger.error(f"Error in market stream handler: {str(e)}")
            
            # Create subscription channels
            channels = []
            for symbol in symbols:
                channels.extend([
                    f"kline.1.{symbol}",
                    f"kline.5.{symbol}",
                    f"kline.15.{symbol}",
                    f"kline.60.{symbol}",
                    f"tickers.{symbol}"
                ])
            
            # Initialize the WebSocket client
            self.market_stream = WebSocket(
                testnet=self.credentials.testnet,
                channel_type="linear",
                api_key=self.credentials.api_key,
                api_secret=self.credentials.api_secret
            )
            
            # Subscribe to channels
            for channel in channels:
                self.market_stream.subscribe_public(channel, callback=ws_handler)
            
            # Connect
            self.market_stream.start()
            self.logger.info(f"Connected to market stream for {symbols}")
            
        except Exception as e:
            self.logger.error(f"Error connecting to market stream: {str(e)}")
            raise BybitAPIError(f"Failed to connect to market stream: {str(e)}")
    
    async def connect_trade_stream(self, on_trade: Callable):
        """
        Connect to private trade stream for order & position updates
        
        Args:
            on_trade: Callback function for trade updates
        """
        try:
            # Ensure we're not already connected
            if self.trade_stream:
                self.logger.warning("Trade stream already connected, closing existing connection")
                await self.close_trade_stream()
            
            # Create a handler for WebSocket messages
            def ws_handler(message):
                # Parse the message
                if not message:
                    return
                
                try:
                    # Dispatch to the callback
                    on_trade(message)
                except Exception as e:
                    self.logger.error(f"Error in trade stream handler: {str(e)}")
            
            # Initialize the WebSocket client
            self.trade_stream = WebSocket(
                testnet=self.credentials.testnet,
                channel_type="private",
                api_key=self.credentials.api_key,
                api_secret=self.credentials.api_secret
            )
            
            # Subscribe to private channels
            channels = [
                "position",
                "execution",
                "order",
                "wallet"
            ]
            
            for channel in channels:
                self.trade_stream.subscribe_private(channel, callback=ws_handler)
            
            # Connect
            self.trade_stream.start()
            self.logger.info("Connected to trade stream")
            
        except Exception as e:
            self.logger.error(f"Error connecting to trade stream: {str(e)}")
            raise BybitAPIError(f"Failed to connect to trade stream: {str(e)}")
    
    async def close_market_stream(self):
        """Close the market data WebSocket connection"""
        if self.market_stream:
            try:
                self.market_stream.stop()
                self.market_stream = None
                self.logger.info("Market stream closed")
            except Exception as e:
                self.logger.error(f"Error closing market stream: {str(e)}")
    
    async def close_trade_stream(self):
        """Close the trade WebSocket connection"""
        if self.trade_stream:
            try:
                self.trade_stream.stop()
                self.trade_stream = None
                self.logger.info("Trade stream closed")
            except Exception as e:
                self.logger.error(f"Error closing trade stream: {str(e)}")
    
    async def close_all_streams(self):
        """Close all WebSocket connections"""
        await self.close_market_stream()
        await self.close_trade_stream()
        self.logger.info("All WebSocket streams closed")


# Quick smoke test to verify WebSocket connection works
if __name__ == "__main__":
    import os
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    
    async def test_websocket():
        # Set up credentials
        credentials = APICredentials(
            api_key=os.getenv("BYBIT_API_KEY"),
            api_secret=os.getenv("BYBIT_API_SECRET"),
            testnet=os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        )
        
        # Create client
        client = BybitClient(credentials)
        
        # Define update handler
        def handle_update(message):
            print(f"Received update: {message}")
        
        # Connect to market stream
        await client.connect_market_stream(["BTCUSDT"], handle_update)
        
        # Wait for some updates
        print("Waiting for WebSocket updates (press Ctrl+C to exit)...")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            # Clean up
            await client.close_all_streams()
    
    # Run the test
    asyncio.run(test_websocket())