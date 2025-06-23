"""
Bybit Client - Handles API communication with Bybit exchange

This module provides reliable API communication with error handling, 
retry logic, and rate limiting. It serves as the foundation for all
exchange interactions.

Example usage:
    credentials = APICredentials(api_key="your_key", api_secret="your_secret", testnet=True)
    client = BybitClient(credentials)
    
    # Use async methods
    server_time = await client.get_server_time()
    
    # Or make raw requests
    params = {"category": "linear", "symbol": "BTCUSDT"}
    ticker = await client.raw_request("GET", "/v5/market/tickers", params)
"""

import time
import hmac
import hashlib
import json
import urllib.parse
import aiohttp
import asyncio
import requests
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import logging

from ..utils.logger import Logger
from ..exceptions import (
    BybitAPIError, 
    AuthenticationError, 
    RateLimitError, 
    ConnectionError
)

@dataclass
class APICredentials:
    """API credentials for authentication"""
    api_key: str
    api_secret: str
    testnet: bool = True

class BybitClient:
    """
    Bybit Client
    
    Provides reliable API communication with error handling,
    retry logic, and rate limiting.
    """
    
    MAINNET_REST_URL = "https://api.bybit.com"
    TESTNET_REST_URL = "https://api-testnet.bybit.com"
    
    def __init__(self, credentials: APICredentials, logger: Optional[Logger] = None):
        """
        Initialize the client with API credentials
        
        Args:
            credentials: API credentials for authentication
            logger: Optional logger instance
        """
        self.api_key = credentials.api_key
        self.api_secret = credentials.api_secret
        self.testnet = credentials.testnet
        self.base_url = self.TESTNET_REST_URL if self.testnet else self.MAINNET_REST_URL
        self.logger = logger or Logger("BybitTransport")
        
        # Setup session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-BAPI-API-KEY': self.api_key
        })
        
        # Rate limiting settings
        self.request_interval = 0.05  # 50ms minimum between requests (20 requests per second max)
        self.last_request_time = 0
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        
        # Log initialization
        network_type = "testnet" if self.testnet else "mainnet"
        self.logger.info(f"BybitClient initialized for {network_type}")

    async def get_server_time(self) -> Dict:
        """
        Get server time from Bybit
        
        Returns:
            Dictionary with server time
        """
        return await self.raw_request("GET", "/v5/server/time", {}, auth_required=False)
        
    async def get_klines(self, category: str, symbol: str, interval: str, 
                         limit: int = 200, start: Optional[int] = None, 
                         end: Optional[int] = None) -> Dict:
        """
        Get candlestick/kline data
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Trading symbol (e.g., BTCUSDT)
            interval: Kline interval (1m, 5m, 1h, etc.)
            limit: Number of candles to return (default 200, max 1000)
            start: Start timestamp in milliseconds
            end: End timestamp in milliseconds
            
        Returns:
            Dictionary with kline data
            
        References:
            https://bybit-exchange.github.io/docs/v5/market/kline
        """
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start:
            params["start"] = start
            
        if end:
            params["end"] = end
            
        return await self.raw_request("GET", "/v5/market/klines", params, auth_required=False)
    
    async def get_orderbook(self, category: str, symbol: str, limit: int = 50) -> Dict:
        """
        Get orderbook data
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Trading symbol (e.g., BTCUSDT)
            limit: Depth of orderbook (default 50)
            
        Returns:
            Dictionary with orderbook data
        """
        params = {
            "category": category,
            "symbol": symbol,
            "limit": limit
        }
        
        return await self.raw_request("GET", "/v5/market/orderbook", params, auth_required=False)
    
    async def get_tickers(self, category: str, symbol: Optional[str] = None) -> Dict:
        """
        Get latest price tickers
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Optional trading symbol for single ticker
            
        Returns:
            Dictionary with ticker data
        """
        params = {"category": category}
        
        if symbol:
            params["symbol"] = symbol
            
        return await self.raw_request("GET", "/v5/market/tickers", params, auth_required=False)
    
    async def get_instruments_info(self, category: str = "linear", symbol: Optional[str] = None) -> Dict:
        """
        Get instrument information
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Optional trading symbol for single instrument
            
        Returns:
            Dictionary with instrument information
        """
        params = {"category": category}
        
        if symbol:
            params["symbol"] = symbol
            
        return await self.raw_request("GET", "/v5/market/instruments-info", params, auth_required=False)
    
    def sync_get_instruments_info(self, category: str = "linear", symbol: Optional[str] = None) -> Dict:
        """
        Synchronous wrapper for get_instruments_info
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Optional trading symbol for single instrument
            
        Returns:
            Dictionary with instrument information
        """
        params = {"category": category}
        
        if symbol:
            params["symbol"] = symbol
            
        return self._sync_raw_request("GET", "/v5/market/instruments-info", params, auth_required=False)
    
    async def get_positions(self, category: str = "linear", symbol: Optional[str] = None) -> Dict:
        """
        Get current positions
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Optional trading symbol to filter
            
        Returns:
            Dictionary with position information
        """
        params = {
            "category": category,
            "settleCoin": "USDT"  # Default to USDT-margined positions
        }
        
        if symbol:
            params["symbol"] = symbol
            
        return await self.raw_request("GET", "/v5/position/list", params)
    
    async def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict:
        """
        Get wallet balance
        
        Args:
            account_type: Account type (UNIFIED or CONTRACT)
            
        Returns:
            Dictionary with balance information
        """
        params = {"accountType": account_type}
        return await self.raw_request("GET", "/v5/account/wallet-balance", params)
    
    async def get_open_orders(self, category: str = "linear", symbol: Optional[str] = None) -> Dict:
        """
        Get active orders
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Optional trading symbol to filter
            
        Returns:
            Dictionary with open orders
        """
        params = {"category": category}
        
        if symbol:
            params["symbol"] = symbol
            
        return await self.raw_request("GET", "/v5/order/realtime", params)
    
    async def get_order_history(self, category: str = "linear", symbol: Optional[str] = None, 
                                limit: int = 50, order_id: Optional[str] = None) -> Dict:
        """
        Get historical orders
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Optional trading symbol to filter
            limit: Number of orders to return
            order_id: Optional order ID to filter
            
        Returns:
            Dictionary with order history
        """
        params = {
            "category": category,
            "limit": limit
        }
        
        if symbol:
            params["symbol"] = symbol
            
        if order_id:
            params["orderId"] = order_id
            
        return await self.raw_request("GET", "/v5/order/history", params)
    
    async def place_order(self, params: Dict) -> Dict:
        """
        Place an order
        
        Args:
            params: Dictionary with order parameters
            
        Returns:
            Dictionary with order result
        """
        return await self.raw_request("POST", "/v5/order/create", params)
    
    async def cancel_order(self, category: str, symbol: str, order_id: Optional[str] = None, 
                          order_link_id: Optional[str] = None) -> Dict:
        """
        Cancel an order
        
        Args:
            category: Product category (linear, inverse, spot)
            symbol: Trading symbol
            order_id: Order ID (required if order_link_id not provided)
            order_link_id: Client order ID (required if order_id not provided)
            
        Returns:
            Dictionary with cancel result
        """
        params = {
            "category": category,
            "symbol": symbol
        }
        
        if order_id:
            params["orderId"] = order_id
            
        if order_link_id:
            params["orderLinkId"] = order_link_id
            
        return await self.raw_request("POST", "/v5/order/cancel", params)
    
    async def amend_order(self, params: Dict) -> Dict:
        """
        Amend an existing order
        
        Args:
            params: Dictionary with amendment parameters
            
        Returns:
            Dictionary with amendment result
        """
        return await self.raw_request("POST", "/v5/order/amend", params)
    
    async def set_trading_stop(self, params: Dict) -> Dict:
        """
        Set trading stop (take profit, stop loss) for a position
        
        Args:
            params: Dictionary with TP/SL parameters
            
        Returns:
            Dictionary with TP/SL result
        """
        return await self.raw_request("POST", "/v5/position/trading-stop", params)

    async def raw_request(self, method: str, path: str, params: Dict, 
                         auth_required: bool = True) -> Dict:
        """
        Make a raw API request to Bybit
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Request parameters
            auth_required: Whether authentication is required
            
        Returns:
            Dictionary with API response
            
        Raises:
            BybitAPIError: On API error
            AuthenticationError: On authentication error
            RateLimitError: On rate limit exceeded
            ConnectionError: On connection error
        """
        # Convert to async implementation
        try:
            return await asyncio.to_thread(
                self._sync_raw_request, method, path, params, auth_required
            )
        except Exception as e:
            self.logger.error(f"Error in raw_request: {str(e)}")
            raise

    def _sync_raw_request(self, method: str, path: str, params: Dict, 
                         auth_required: bool = True) -> Dict:
        """
        Synchronous implementation of raw API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Request parameters
            auth_required: Whether authentication is required
            
        Returns:
            Dictionary with API response
        """
        # Apply rate limiting
        self._apply_rate_limit()
        
        # Setup request URL and params
        url = f"{self.base_url}{path}"
        request_params = params.copy()
        
        # Add authentication if required
        if auth_required:
            timestamp = str(int(time.time() * 1000))
            request_params["api_key"] = self.api_key
            request_params["timestamp"] = timestamp
            
            # Generate signature
            param_str = self._build_param_string(request_params)
            signature = self._generate_signature(param_str)
            request_params["sign"] = signature
        
        # Prepare for request
        if method == "GET":
            query_string = urllib.parse.urlencode(request_params)
            full_url = f"{url}?{query_string}"
            payload = None
        else:  # POST, PUT, DELETE
            full_url = url
            payload = json.dumps(request_params)
        
        # Make request with retry logic
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(f"Request: {method} {full_url}")
                
                if method == "GET":
                    response = self.session.get(full_url)
                elif method == "POST":
                    response = self.session.post(url, data=payload)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check for errors
                if response.status_code != 200:
                    error_msg = f"HTTP Error {response.status_code}: {response.text}"
                    self.logger.error(error_msg)
                    
                    # Handle specific error codes
                    if response.status_code == 401:
                        raise AuthenticationError(error_msg)
                    elif response.status_code == 429:
                        raise RateLimitError(error_msg)
                    else:
                        raise BybitAPIError(error_msg)
                
                # Parse JSON response
                result = response.json()
                
                # Check for API error codes
                if "retCode" in result and result["retCode"] != 0:
                    error_code = result["retCode"]
                    error_msg = result.get("retMsg", "Unknown API error")
                    
                    self.logger.warning(f"API Error {error_code}: {error_msg}")
                    
                    # Handle specific API errors
                    if error_code in [10003, 10004]:  # Auth errors
                        raise AuthenticationError(f"API Error {error_code}: {error_msg}")
                    elif error_code in [10006, 10007]:  # Rate limit errors
                        raise RateLimitError(f"API Error {error_code}: {error_msg}")
                    
                    # For other errors, just return the response with error code
                    # This allows the caller to handle business logic errors
                
                return result
                
            except (AuthenticationError, RateLimitError) as e:
                # Don't retry auth/rate limit errors
                raise
                
            except Exception as e:
                # For network/connection errors, retry with exponential backoff
                if attempt < self.max_retries:
                    retry_delay = self.retry_delay * (2 ** (attempt - 1))
                    self.logger.warning(f"Request failed, retrying in {retry_delay}s: {str(e)}")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"Request failed after {self.max_retries} attempts: {str(e)}")
                    raise ConnectionError(f"Failed to connect to Bybit API: {str(e)}")
    
    def _build_param_string(self, params: Dict) -> str:
        """
        Build parameter string for signature generation
        
        Args:
            params: Request parameters
            
        Returns:
            Parameter string
        """
        # Sort parameters by key
        sorted_params = sorted(params.items())
        
        # Build parameter string
        param_str = ""
        for key, value in sorted_params:
            param_str += f"{key}={value}&"
            
        # Remove trailing '&'
        param_str = param_str[:-1]
        
        return param_str
    
    def _generate_signature(self, param_str: str) -> str:
        """
        Generate HMAC signature for API authentication
        
        Args:
            param_str: Parameter string
            
        Returns:
            HMAC signature
        """
        # Create HMAC-SHA256 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _apply_rate_limit(self) -> None:
        """
        Apply rate limiting to avoid hitting API limits
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.request_interval:
            sleep_time = self.request_interval - elapsed
            time.sleep(sleep_time)
            
        self.last_request_time = time.time()


# Backwards compatibility: make BybitClientTransport available
BybitClientTransport = BybitClient