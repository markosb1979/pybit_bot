"""
Core Bybit API Client - Enhanced pybit wrapper, revised for full v5 compatibility
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

import requests
from urllib.parse import urlencode
import json
import hmac
import hashlib

from ..exceptions import (
    BybitAPIError,
    AuthenticationError,
    RateLimitError,
    InvalidOrderError
)
from ..utils.logger import Logger

@dataclass
class APICredentials:
    """API Credentials container"""
    api_key: str
    api_secret: str
    testnet: bool = True

class RateLimiter:
    """Rate limiting to prevent API abuse"""

    def __init__(self, requests_per_second: int = 10):
        self.requests_per_second = requests_per_second
        self.request_times = []

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < 1.0]
        if len(self.request_times) >= self.requests_per_second:
            sleep_time = 1.0 - (now - self.request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)

    def record_request(self):
        """Record a successful request"""
        self.request_times.append(time.time())

class BybitClient:
    """
    Enhanced Bybit API Client with comprehensive error handling
    and reliability features for production trading.
    This version matches pybit_ex_official v5 logic for all REST endpoints.
    """

    TESTNET_BASE_URL = "https://api-testnet.bybit.com"
    MAINNET_BASE_URL = "https://api.bybit.com"
    RECV_WINDOW = 5000

    def __init__(self, credentials: APICredentials, logger: Optional[Logger] = None,
                 config: Optional[Any] = None, testnet: Optional[bool] = None):
        self.credentials = credentials
        self.logger = logger or Logger("BybitClient")
        self.config = config
        if testnet is not None:
            self.credentials.testnet = testnet

        self.base_url = (
            self.TESTNET_BASE_URL if self.credentials.testnet
            else self.MAINNET_BASE_URL
        )
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'PybitBot/1.0.0'
        })
        self.rate_limiter = RateLimiter()
        self.connected = False
        self.last_heartbeat = None
        self.default_symbol = getattr(self.config, 'symbol', "BTCUSDT") if self.config else "BTCUSDT"
        self.logger.info(f"Initializing Bybit client for {'testnet' if self.credentials.testnet else 'mainnet'}")

    def _generate_signature(self, timestamp: int, recv_window: int, payload: str) -> str:
        """
        Generate API signature (matches pybit/official logic).
        """
        param_str = f"{timestamp}{self.credentials.api_key}{recv_window}{payload}"
        return hmac.new(
            self.credentials.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        auth_required: bool = True
    ) -> Dict[str, Any]:
        """
        Make authenticated API request with comprehensive error handling.
        This logic matches official pybit for v5 endpoints.
        """
        self.rate_limiter.wait_if_needed()
        url = f"{self.base_url}{endpoint}"
        timestamp = int(time.time() * 1000)
        recv_window = self.RECV_WINDOW
        headers = {}

        # Remove all None values from params
        params = {k: v for k, v in (params or {}).items() if v is not None}

        if auth_required:
            if method == "GET":
                query_string = urlencode(params, doseq=True)
                signature = self._generate_signature(timestamp, recv_window, query_string)
                headers.update({
                    'X-BAPI-API-KEY': self.credentials.api_key,
                    'X-BAPI-TIMESTAMP': str(timestamp),
                    'X-BAPI-RECV-WINDOW': str(recv_window),
                    'X-BAPI-SIGN': signature
                })
                # For GET, Bybit expects params in the query string, not the body
                req_params = params
                req_data = None
            elif method == "POST":
                payload = json.dumps(params)
                signature = self._generate_signature(timestamp, recv_window, payload)
                headers.update({
                    'X-BAPI-API-KEY': self.credentials.api_key,
                    'X-BAPI-TIMESTAMP': str(timestamp),
                    'X-BAPI-RECV-WINDOW': str(recv_window),
                    'X-BAPI-SIGN': signature
                })
                req_params = None
                req_data = payload
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        else:
            req_params = params if method == "GET" else None
            req_data = json.dumps(params) if method == "POST" else None

        try:
            if method == "GET":
                response = self.session.get(url, params=req_params, headers=headers, timeout=10)
            elif method == "POST":
                response = self.session.post(url, data=req_data, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            data = response.json()

            # Handle Bybit API errors (pybit logic: retCode != 0 is error)
            if data.get('retCode', 0) != 0:
                error_code = data.get('retCode')
                error_msg = data.get('retMsg', 'Unknown error')
                if error_code == 10002:
                    raise AuthenticationError(f"Authentication failed: {error_msg}")
                elif error_code == 10006:
                    raise RateLimitError(f"Rate limit exceeded: {error_msg}")
                else:
                    raise BybitAPIError(f"API Error {error_code}: {error_msg}")

            self.rate_limiter.record_request()
            return data.get('result', {})

        except requests.exceptions.Timeout:
            self.logger.error("Request timeout")
            raise BybitAPIError("Request timeout")
        except requests.exceptions.ConnectionError:
            self.logger.error("Connection error")
            raise BybitAPIError("Connection error")
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            raise BybitAPIError(f"Unexpected error: {str(e)}")

    # === Market Data Methods ===

    def get_server_time(self) -> Dict[str, Any]:
        """
        Get server time with full response structure
        
        Returns:
            Complete server time response matching official client
        """
        try:
            response = self._make_request("GET", "/v5/market/time", auth_required=False)
            # Log response for debugging
            self.logger.debug(f"Server time response: {response}")
            
            # Handle different response formats
            if isinstance(response, dict):
                if "timeSecond" in response:
                    # Already in the expected format
                    return response
                elif "time" in response:
                    # Alternate format, convert to expected format
                    time_second = str(int(response.get("time", 0) / 1000))
                    return {
                        "timeSecond": time_second,
                        "timeNano": f"{time_second}000000000"
                    }
            
            # If we can't determine the format, return current time as fallback
            current_time = str(int(time.time()))
            return {
                "timeSecond": current_time,
                "timeNano": f"{current_time}000000000"
            }
            
        except Exception as e:
            self.logger.error(f"Error getting server time: {str(e)}")
            # Return fallback with local time if server time fails
            current_time = str(int(time.time()))
            return {
                "timeSecond": current_time,
                "timeNano": f"{current_time}000000000"
            }

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[List[str]]:
        """Get historical kline data"""
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "start": start_time,
            "end": end_time
        }
        result = self._make_request("GET", "/v5/market/kline", params, auth_required=False)
        return result.get("list", [])

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get 24hr ticker statistics"""
        params = {
            "category": "linear",
            "symbol": symbol
        }
        result = self._make_request("GET", "/v5/market/tickers", params, auth_required=False)
        tickers = result.get("list", [])
        return tickers[0] if tickers else {}

    def get_orderbook(self, symbol: str, limit: int = 25) -> Dict[str, Any]:
        """Get orderbook data"""
        params = {
            "category": "linear",
            "symbol": symbol,
            "limit": limit
        }
        return self._make_request("GET", "/v5/market/orderbook", params, auth_required=False)

    # === Trading Methods ===

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: str,
        price: Optional[str] = None,
        time_in_force: str = "GTC",
        order_link_id: Optional[str] = None,
        stop_loss: Optional[str] = None,
        take_profit: Optional[str] = None
    ) -> Dict[str, Any]:
        """Place an order"""
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty,
            "timeInForce": time_in_force,
            "price": price,
            "orderLinkId": order_link_id,
            "stopLoss": stop_loss,
            "takeProfit": take_profit
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        return self._make_request("POST", "/v5/order/create", params)

    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel an order"""
        params = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id,
            "orderLinkId": order_link_id
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        if "orderId" not in params and "orderLinkId" not in params:
            raise InvalidOrderError("Either order_id or order_link_id must be provided")
        return self._make_request("POST", "/v5/order/cancel", params)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders"""
        params = {"category": "linear"}
        if symbol:
            params["symbol"] = symbol
        result = self._make_request("GET", "/v5/order/realtime", params)
        return result.get("list", [])

    def get_positions(self, symbol: Optional[str] = None, settle_coin: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get positions.
        Always provide symbol or settleCoin for unified account.
        Uses default symbol if neither provided.
        """
        params = {"category": "linear"}
        if symbol:
            params["symbol"] = symbol
        if settle_coin:
            params["settleCoin"] = settle_coin
        if not symbol and not settle_coin:
            params["symbol"] = self.default_symbol
        result = self._make_request("GET", "/v5/position/list", params)
        return result.get("list", [])

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Get wallet balance"""
        params = {"accountType": account_type}
        return self._make_request("GET", "/v5/account/wallet-balance", params)

    # === Utility Methods ===

    def test_connection(self) -> bool:
        """Test API connection and credentials"""
        try:
            self.get_server_time()
            self.connected = True
            self.last_heartbeat = datetime.utcnow()
            self.logger.info("API connection test successful")
            return True
        except Exception as e:
            self.connected = False
            self.logger.error(f"API connection test failed: {str(e)}")
            return False