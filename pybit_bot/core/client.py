"""
Bybit Client Transport Layer

This module provides a low-level transport wrapper around the PyBit library,
handling HTTP requests, WebSocket connections, authentication, rate limiting,
and error handling.

Example usage:
    # Initialize transport layer
    credentials = APICredentials(api_key="your_key", api_secret="your_secret", testnet=True)
    transport = BybitClientTransport(credentials)
    
    # Make raw HTTP requests
    server_time = transport.get_server_time()
    
    # Or use the raw request method for any endpoint
    result = transport.raw_request("GET", "/v5/market/tickers", {"category": "linear", "symbol": "BTCUSDT"})
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

# Import only the HTTP client to avoid WebSocket compatibility issues
from pybit.unified_trading import HTTP

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


class BybitClientTransport:
    """
    Low-level transport layer for Bybit API
    
    Handles authentication, rate limiting, retries, and WebSocket connections.
    This class should not contain any trading-specific business logic,
    only transport mechanisms.
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
        self.logger = logger or Logger("BybitTransport")
        
        # Initialize the official pybit HTTP client
        self.http_client = HTTP(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            testnet=credentials.testnet
        )
        
        # Select endpoint based on testnet flag
        self.base_url = self.API_URLS["testnet" if credentials.testnet else "mainnet"]
        self.logger.info(f"BybitClientTransport initialized for {'testnet' if credentials.testnet else 'mainnet'}")
        
        # WebSocket clients are initialized to None (implemented when needed)
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
    
    def get_server_time(self) -> Dict:
        """
        Get server time
        
        Returns:
            Server time data dictionary
        """
        try:
            response = self.http_client.get_server_time()
            return self._process_response(response)
        except Exception as e:
            self.logger.error(f"Error getting server time: {str(e)}")
            raise BybitAPIError(f"Failed to get server time: {str(e)}")
    
    def _process_response(self, response: Dict) -> Any:
        """
        Process API response and handle errors
        
        Args:
            response: API response
            
        Returns:
            Processed response data
            
        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limits are exceeded
            InvalidOrderError: If order parameters are invalid
            PositionError: If position operations fail
            BybitAPIError: For other API errors
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
    
    def raw_request(self, method: str, path: str, params: Dict = None, auth_required: bool = True) -> Any:
        """
        Make a raw HTTP request to the Bybit API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Request parameters
            auth_required: Whether authentication is required
            
        Returns:
            API response data
            
        Raises:
            Various exceptions based on error type
        """
        self.request_count += 1
        params = params or {}
        
        # Add proper authentication if required
        if auth_required:
            timestamp = str(int(time.time() * 1000))
            params["api_key"] = self.credentials.api_key
            params["timestamp"] = timestamp
            
            # Generate signature - consistent with PyBit implementation
            param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            signature = hmac.new(
                bytes(self.credentials.api_secret, "utf-8"),
                bytes(param_str, "utf-8"),
                hashlib.sha256
            ).hexdigest()
            params["sign"] = signature
        
        url = f"{self.base_url}{path}"
        
        # Implement retry logic for transient errors
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            try:
                self.logger.debug(f"Making {method} request to {path} (attempt {retries+1}/{self.max_retries+1})")
                
                if method.upper() == "GET":
                    response = self.session.get(url, params=params, timeout=self.req_timeout)
                elif method.upper() == "POST":
                    response = self.session.post(url, json=params, timeout=self.req_timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check if the request was successful
                if response.status_code == 200:
                    data = response.json()
                    return self._process_response(data)
                
                # Handle specific HTTP errors
                if response.status_code == 429:
                    self.logger.warning("Rate limit exceeded, retrying after delay")
                    time.sleep(self.retry_delay * (2 ** retries))
                    retries += 1
                    continue
                    
                # Retry on server errors
                if 500 <= response.status_code < 600:
                    self.logger.warning(f"Server error {response.status_code}, retrying after delay")
                    time.sleep(self.retry_delay * (2 ** retries))
                    retries += 1
                    continue
                
                # Other HTTP errors
                self.logger.error(f"HTTP error {response.status_code}: {response.text}")
                raise BybitAPIError(f"HTTP error {response.status_code}: {response.text}")
                
            except (requests.RequestException, json.JSONDecodeError) as e:
                last_error = str(e)
                self.logger.warning(f"Request error: {last_error}, retrying after delay")
                time.sleep(self.retry_delay * (2 ** retries))
                retries += 1
            
            except (BybitAPIError, AuthenticationError, RateLimitError) as e:
                # These are already processed errors that should be propagated
                raise
                
            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)}")
                raise BybitAPIError(f"Unexpected error: {str(e)}")
        
        # All retries failed
        self.logger.error(f"Max retries reached. Last error: {last_error}")
        raise BybitAPIError(f"Max retries reached. Last error: {last_error}")
    
    # ===== WEBSOCKET PLACEHOLDER METHODS =====
    # These methods will be implemented properly once we confirm which WebSocket classes are available
    
    async def connect_market_stream(self, symbols: List[str], on_update: Callable):
        """
        Connect to market data WebSocket stream
        
        Args:
            symbols: List of symbols to subscribe to
            on_update: Callback function for market updates
            
        Returns:
            None
        """
        self.logger.warning("WebSocket functionality is not currently implemented - update your pybit package or use HTTP polling instead")
        return None
    
    async def connect_trade_stream(self, on_trade: Callable):
        """
        Connect to private trade WebSocket stream for order & position updates
        
        Args:
            on_trade: Callback function for trade updates
            
        Returns:
            None
        """
        self.logger.warning("WebSocket functionality is not currently implemented - update your pybit package or use HTTP polling instead")
        return None
    
    async def close_market_stream(self):
        """Close the market data WebSocket connection"""
        if self.market_stream:
            self.logger.warning("WebSocket functionality is not currently implemented")
        return None
    
    async def close_trade_stream(self):
        """Close the trade WebSocket connection"""
        if self.trade_stream:
            self.logger.warning("WebSocket functionality is not currently implemented")
        return None
    
    async def close_all_streams(self):
        """Close all WebSocket connections"""
        self.logger.warning("WebSocket functionality is not currently implemented")
        return None

    # ===== BACKWARD COMPATIBILITY METHODS =====
    
    def get_klines(self, symbol: str, interval: str, limit: int = 1000, 
                  start_time: Optional[int] = None, end_time: Optional[int] = None) -> List:
        """
        Get historical kline/candlestick data (COMPATIBILITY METHOD)
        
        Args:
            symbol: Trading symbol
            interval: Kline interval (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            limit: Number of klines to return (max 1000)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            
        Returns:
            List of klines
            
        Note:
            This method is provided for backward compatibility.
            New code should use OrderManagerClient.get_klines() instead.
        """
        self.logger.warning("Using deprecated get_klines() method on BybitClientTransport. Consider using OrderManagerClient instead.")
        
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
            
        response = self.raw_request("GET", "/v5/market/kline", params, auth_required=False)
        return response.get("list", [])
    
    # Add compatibility methods for ticker and orderbook
    def get_ticker(self, symbol: str) -> Dict:
        """
        Get latest ticker data (COMPATIBILITY METHOD)
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Ticker data
            
        Note:
            This method is provided for backward compatibility.
            New code should use OrderManagerClient.get_ticker() instead.
        """
        self.logger.warning("Using deprecated get_ticker() method on BybitClientTransport. Consider using OrderManagerClient instead.")
        
        params = {
            "category": "linear",
            "symbol": symbol
        }
        
        response = self.raw_request("GET", "/v5/market/tickers", params, auth_required=False)
        tickers = response.get("list", [])
        
        if tickers:
            return tickers[0]
        return {}
    
    def get_orderbook(self, symbol: str, limit: int = 25) -> Dict:
        """
        Get orderbook data (COMPATIBILITY METHOD)
        
        Args:
            symbol: Trading symbol
            limit: Depth of orderbook
            
        Returns:
            Orderbook data
            
        Note:
            This method is provided for backward compatibility.
            New code should use OrderManagerClient.get_orderbook() instead.
        """
        self.logger.warning("Using deprecated get_orderbook() method on BybitClientTransport. Consider using OrderManagerClient instead.")
        
        params = {
            "category": "linear",
            "symbol": symbol,
            "limit": limit
        }
        
        return self.raw_request("GET", "/v5/market/orderbook", params, auth_required=False)


# For backward compatibility
class BybitClient(BybitClientTransport):
    """
    Legacy class for backward compatibility.
    Use BybitClientTransport for new code.
    """
    pass


# Quick smoke test to verify the client works
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Set up credentials
    credentials = APICredentials(
        api_key=os.getenv("BYBIT_API_KEY"),
        api_secret=os.getenv("BYBIT_API_SECRET"),
        testnet=os.getenv("BYBIT_TESTNET", "true").lower() == "true"
    )
    
    # Create transport client
    transport = BybitClientTransport(credentials)
    
    # Test connection
    print("Testing connection...")
    result = transport.test_connection()
    print(f"Connection test result: {result}")
    
    # Make raw request to get ticker
    print("\nGetting BTCUSDT ticker via raw request...")
    ticker = transport.raw_request("GET", "/v5/market/tickers", {"category": "linear", "symbol": "BTCUSDT"})
    print(f"BTCUSDT ticker: {ticker}")
    
    print("\nTransport test completed.")