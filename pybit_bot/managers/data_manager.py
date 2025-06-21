"""
Data Manager - Handle all market data operations and caching
"""

import asyncio
import logging
import time
import pandas as pd
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

from ..utils.logger import Logger
from ..core.order_manager_client import OrderManagerClient


class DataManager:
    """
    Data management system for market data
    Provides price, orderbook, and ticker data with caching
    """
    
    def __init__(self, client, config, logger=None, order_client=None):
        """
        Initialize with client, config, and logger
        
        Args:
            client: BybitClientTransport instance
            config: ConfigLoader instance
            logger: Optional Logger instance
            order_client: Optional OrderManagerClient instance
        """
        self.client = client
        self.config = config
        self.logger = logger or Logger("DataManager")
        # Store the order_client for business logic operations
        self.order_client = order_client
        
        # Default settings
        trading_config = config.get("trading", {})
        self.default_symbol = trading_config.get("default_symbol", "BTCUSDT")
        
        # Data caches with timestamps
        self._price_cache = {}
        self._ticker_cache = {}
        self._orderbook_cache = {}
        self._kline_cache = {}
        self._formatted_kline_cache = {}  # For formatted klines with named columns
        
        # Cache TTL in seconds
        system_config = config.get("system", {})
        self.price_ttl = system_config.get("price_cache_ttl", 1)  # 1 second for prices
        self.ticker_ttl = system_config.get("ticker_cache_ttl", 5)  # 5 seconds for tickers
        self.orderbook_ttl = system_config.get("orderbook_cache_ttl", 2)  # 2 seconds for orderbook
        self.kline_ttl = system_config.get("kline_cache_ttl", 60)  # 60 seconds for klines
        
        # Standard column names for kline data
        self.kline_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
        
        # WebSocket connection state
        self.ws_connected = False
        self.ws_last_update = None
        self.ws_subscriptions = set()

        # Last price for non-async methods
        self._last_price = {}
        
        self.logger.info("DataManager initialized")
    
    async def initialize(self):
        """Initialize data manager and connect to WebSocket"""
        self.logger.info("DataManager starting...")
        
        try:
            # Initialize ticker cache with current data
            ticker = None
            
            # Try using order_client first, then fall back to client
            if self.order_client:
                ticker = self.order_client.get_ticker(self.default_symbol)
            else:
                # Use transport layer as fallback
                if hasattr(self.client, 'get_ticker'):
                    ticker = self.client.get_ticker(self.default_symbol)
                else:
                    self.logger.warning("No method to get ticker available - both order_client and client lack get_ticker")
            
            if ticker:
                self._ticker_cache[self.default_symbol] = {
                    "data": ticker,
                    "timestamp": time.time()
                }
                # Also initialize the last price for this symbol
                self._last_price[self.default_symbol] = float(ticker.get("lastPrice", 0))
                self.logger.info(f"Initial ticker loaded for {self.default_symbol}")
            
            # WebSocket initialization would go here in the future
            # For now, we'll use polling for data updates
            
            # Create a background task for updating data
            self._update_task = asyncio.create_task(self._data_update_loop())
            
            self.logger.info("DataManager initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing DataManager: {str(e)}")
            return False
    
    async def close(self):
        """Clean shutdown of data manager"""
        self.logger.info("DataManager shutting down...")
        
        try:
            # Cancel the update task if it exists
            if hasattr(self, '_update_task') and self._update_task:
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            
            # Close WebSocket connection if active
            # This would be implemented in the future
            
            self.logger.info("DataManager shutdown complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing DataManager: {str(e)}")
            return False
    
    async def _data_update_loop(self):
        """Background task to periodically update market data"""
        try:
            while True:
                # Update ticker for default symbol
                await self._update_ticker(self.default_symbol)
                
                # Sleep for a short interval
                await asyncio.sleep(5)  # Update every 5 seconds
                
        except asyncio.CancelledError:
            self.logger.info("Data update loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in data update loop: {str(e)}")
    
    async def _update_ticker(self, symbol):
        """Update ticker data for a symbol"""
        try:
            ticker = None
            
            # Try using order_client first, then fall back to client
            if self.order_client:
                ticker = self.order_client.get_ticker(symbol)
            elif hasattr(self.client, 'get_ticker'):
                ticker = self.client.get_ticker(symbol)
                
            if ticker:
                self._ticker_cache[symbol] = {
                    "data": ticker,
                    "timestamp": time.time()
                }
                # Also update price cache
                price = float(ticker.get("lastPrice", 0))
                self._price_cache[symbol] = {
                    "price": price,
                    "timestamp": time.time()
                }
                # Update last price for sync methods
                self._last_price[symbol] = price
        except Exception as e:
            self.logger.error(f"Error updating ticker for {symbol}: {str(e)}")
    
    async def get_latest_price(self, symbol):
        """
        Get the latest price for a specific symbol
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            
        Returns:
            Current market price as float
        """
        try:
            # Check cache first
            cache_entry = self._price_cache.get(symbol)
            current_time = time.time()
            
            if cache_entry and (current_time - cache_entry["timestamp"]) < self.price_ttl:
                return cache_entry["price"]
            
            # Get fresh ticker data
            ticker = None
            
            # Try using order_client first, then fall back to client
            if self.order_client:
                ticker = self.order_client.get_ticker(symbol)
            elif hasattr(self.client, 'get_ticker'):
                ticker = self.client.get_ticker(symbol)
            
            if not ticker:
                self.logger.warning(f"Failed to get ticker for {symbol}")
                return 0.0
                
            # Extract the last price
            price = float(ticker.get("lastPrice", 0))
            
            # Update cache
            self._price_cache[symbol] = {
                "price": price,
                "timestamp": current_time
            }
            # Update last price for sync methods
            self._last_price[symbol] = price
            
            return price
            
        except Exception as e:
            self.logger.error(f"Error getting latest price for {symbol}: {e}")
            return 0.0
    
    def get_last_price(self, symbol):
        """
        Synchronous version to get the last known price for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Last known price as float
        """
        return self._last_price.get(symbol, 0.0)
    
    async def get_ticker(self, symbol):
        """
        Get full ticker data for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Ticker dictionary with market data
        """
        try:
            # Check cache first
            cache_entry = self._ticker_cache.get(symbol)
            current_time = time.time()
            
            if cache_entry and (current_time - cache_entry["timestamp"]) < self.ticker_ttl:
                return cache_entry["data"]
            
            # Get fresh ticker data
            ticker = None
            
            # Try using order_client first, then fall back to client
            if self.order_client:
                ticker = self.order_client.get_ticker(symbol)
            elif hasattr(self.client, 'get_ticker'):
                ticker = self.client.get_ticker(symbol)
            
            if not ticker:
                self.logger.warning(f"Failed to get ticker for {symbol}")
                return {}
                
            # Update cache
            self._ticker_cache[symbol] = {
                "data": ticker,
                "timestamp": current_time
            }
            
            return ticker
            
        except Exception as e:
            self.logger.error(f"Error getting ticker for {symbol}: {e}")
            return {}
    
    async def get_orderbook(self, symbol, depth=25):
        """
        Get orderbook data for a symbol
        
        Args:
            symbol: Trading pair symbol
            depth: Orderbook depth
            
        Returns:
            Orderbook dictionary with bids and asks
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{depth}"
            cache_entry = self._orderbook_cache.get(cache_key)
            current_time = time.time()
            
            if cache_entry and (current_time - cache_entry["timestamp"]) < self.orderbook_ttl:
                return cache_entry["data"]
            
            # Get fresh orderbook data
            orderbook = None
            
            # Try using order_client first, then fall back to client
            if self.order_client and hasattr(self.order_client, 'get_orderbook'):
                params = {"symbol": symbol, "limit": depth}
                orderbook = self.order_client.get_orderbook(**params)
            elif hasattr(self.client, 'get_orderbook'):
                orderbook = self.client.get_orderbook(symbol, depth)
            elif hasattr(self.client, 'raw_request'):
                # Raw request fallback
                api_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "limit": depth
                }
                response = self.client.raw_request("GET", "/v5/market/orderbook", api_params, auth_required=False)
                orderbook = response
            
            if not orderbook:
                self.logger.warning(f"Failed to get orderbook for {symbol}")
                return {}
                
            # Update cache
            self._orderbook_cache[cache_key] = {
                "data": orderbook,
                "timestamp": current_time
            }
            
            return orderbook
            
        except Exception as e:
            self.logger.error(f"Error getting orderbook for {symbol}: {e}")
            return {}
    
    async def get_klines(self, symbol, interval="1m", limit=100, start_time=None, end_time=None):
        """
        Get historical kline data
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval (e.g., "1m", "5m", "1h")
            limit: Number of klines to retrieve
            start_time: Optional start timestamp
            end_time: Optional end timestamp
            
        Returns:
            List of kline data
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{interval}_{limit}"
            if start_time:
                cache_key += f"_{start_time}"
            if end_time:
                cache_key += f"_{end_time}"
                
            cache_entry = self._kline_cache.get(cache_key)
            current_time = time.time()
            
            if cache_entry and (current_time - cache_entry["timestamp"]) < self.kline_ttl:
                return cache_entry["data"]
            
            # Convert interval format for Bybit
            bybit_interval = self._convert_interval_for_bybit(interval)
            
            # Initialize klines as empty list
            klines = []
            
            # Prepare parameters
            params = {
                "symbol": symbol,
                "interval": bybit_interval,
                "limit": limit
            }
            
            if start_time:
                params["start"] = start_time
            if end_time:
                params["end"] = end_time
            
            # Try different methods to get klines
            try:
                # First try with OrderManagerClient if available
                if self.order_client and hasattr(self.order_client, 'get_klines'):
                    self.logger.info(f"Getting klines with OrderManagerClient for {symbol}")
                    klines = self.order_client.get_klines(**params)
                # Then try with client.get_klines if available
                elif hasattr(self.client, 'get_klines'):
                    self.logger.info(f"Getting klines with BybitClient for {symbol}")
                    klines = self.client.get_klines(**params)
                # Try the raw_request method as last resort
                elif hasattr(self.client, 'raw_request'):
                    self.logger.info(f"Getting klines with raw_request for {symbol}")
                    api_params = {
                        "category": "linear",
                        "symbol": symbol,
                        "interval": bybit_interval,
                        "limit": limit
                    }
                    if start_time:
                        api_params["start"] = start_time
                    if end_time:
                        api_params["end"] = end_time
                        
                    response = self.client.raw_request("GET", "/v5/market/kline", api_params, auth_required=False)
                    klines = response.get("list", [])
                else:
                    self.logger.error(f"No method available to get klines for {symbol}")
            except Exception as e:
                self.logger.error(f"Error calling API for klines: {str(e)}")
                klines = []
            
            if not klines:
                self.logger.warning(f"Failed to get klines for {symbol}")
                return []
                
            # Update cache
            self._kline_cache[cache_key] = {
                "data": klines,
                "timestamp": current_time
            }
            
            return klines
            
        except Exception as e:
            self.logger.error(f"Error getting klines for {symbol}: {e}")
            return []
    
    async def get_historical_data(self, symbol, interval="1m", limit=100, start_time=None, end_time=None):
        """
        Get historical kline data formatted with named columns for pandas
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval (e.g., "1m", "5m", "1h")
            limit: Number of klines to retrieve
            start_time: Optional start timestamp
            end_time: Optional end timestamp
            
        Returns:
            DataFrame with named columns for pandas
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{interval}_{limit}_formatted"
            if start_time:
                cache_key += f"_{start_time}"
            if end_time:
                cache_key += f"_{end_time}"
                
            cache_entry = self._formatted_kline_cache.get(cache_key)
            current_time = time.time()
            
            if cache_entry and (current_time - cache_entry["timestamp"]) < self.kline_ttl:
                return cache_entry["data"]
            
            # Generate sample data in case we can't get real data
            sample_data = self._get_sample_data(symbol, limit)
            
            try:
                # Get kline data using our get_klines method
                klines = await self.get_klines(symbol, interval, limit, start_time, end_time)
                
                self.logger.info(f"Klines response type: {type(klines)}, data: {klines[:2] if isinstance(klines, list) else klines}")
                
                if not klines or len(klines) == 0:
                    self.logger.warning(f"No kline data returned for {symbol}, using sample data")
                    # Use sample data as fallback
                    df = sample_data
                else:
                    # Convert to DataFrame with named columns
                    df = pd.DataFrame(klines, columns=self.kline_columns)
                    
                    # Convert numeric columns
                    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                        df[col] = pd.to_numeric(df[col])
                    
                    # Convert timestamp to numeric
                    df['timestamp'] = pd.to_numeric(df['timestamp'])
            except Exception as e:
                self.logger.error(f"Error processing kline data: {str(e)}")
                # Fall back to sample data
                df = sample_data
                
            # Update cache
            self._formatted_kline_cache[cache_key] = {
                "data": df,
                "timestamp": current_time
            }
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting historical data for {symbol}: {e}")
            # Return sample data on error
            return self._get_sample_data(symbol, limit)
    
    def _convert_interval_for_bybit(self, interval):
        """
        Convert standard interval format to Bybit format
        
        Args:
            interval: Standard interval (e.g., "1m", "5m", "1h")
            
        Returns:
            Bybit-compatible interval
        """
        # Bybit expects different formats depending on the interval
        if interval.endswith("m"):
            # For minutes, Bybit uses the number only (e.g., "1" for "1m")
            return interval[:-1]
        elif interval.endswith("h"):
            # For hours, Bybit uses minutes (e.g., "60" for "1h")
            hours = int(interval[:-1])
            return str(hours * 60)
        elif interval.endswith("d"):
            # For days, Bybit uses "D"
            return "D"
        elif interval.endswith("w"):
            # For weeks, Bybit uses "W"
            return "W"
        elif interval.endswith("M"):
            # For months, Bybit uses "M"
            return "M"
        else:
            # Default to the provided interval if it doesn't match known patterns
            return interval
    
    def _get_sample_data(self, symbol, limit=100):
        """
        Generate sample kline data for testing or when API fails
        
        Args:
            symbol: Trading symbol
            limit: Number of klines to generate
            
        Returns:
            DataFrame with sample data
        """
        # Create sample timestamps from now going back
        now = int(time.time() * 1000)
        timestamps = [now - (i * 60 * 1000) for i in range(limit)]  # 1-minute intervals
        timestamps.reverse()  # Oldest first
        
        # Generate some reasonable price data
        base_price = 45000.0 if "BTC" in symbol else (2000.0 if "ETH" in symbol else 100.0)
        
        # Create price oscillation
        prices = []
        price = base_price
        for i in range(limit):
            # Random walk with 0.1% standard deviation
            change = price * 0.001 * (2 * (i % 5) - 5)  # Simple oscillation
            price += change
            prices.append(price)
        
        # Create OHLC from the prices
        data = []
        for i in range(limit):
            p = prices[i]
            # Create slight variations for O, H, L around close price
            o = p * (1 + 0.0001 * ((i % 3) - 1))
            h = p * 1.001
            l = p * 0.999
            c = p
            v = 10 + i % 10  # Volume
            t = 10000 + v * p  # Turnover (volume * price)
            
            data.append([timestamps[i], o, h, l, c, v, t])
        
        # Create DataFrame
        df = pd.DataFrame(data, columns=self.kline_columns)
        
        # Set proper dtypes
        for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
            df[col] = pd.to_numeric(df[col])
        
        df['timestamp'] = pd.to_numeric(df['timestamp'])
        
        return df
        
    async def get_atr(self, symbol, timeframe="1m", length=14):
        """
        Calculate Average True Range (ATR) for a symbol
        
        Args:
            symbol: Trading symbol
            timeframe: Kline timeframe (e.g. "1m", "5m")
            length: ATR period
            
        Returns:
            ATR value as float
        """
        try:
            # Get historical data
            hist_data = await self.get_historical_data(symbol, interval=timeframe, limit=length+10)
            
            if hist_data.empty or len(hist_data) < length+1:
                self.logger.warning(f"Not enough data to calculate ATR for {symbol}")
                # Return a default value based on price
                current_price = await self.get_latest_price(symbol)
                return current_price * 0.01  # 1% of current price as fallback
            
            # Calculate True Range
            tr_values = []
            for i in range(1, len(hist_data)):
                high = hist_data['high'].iloc[i]
                low = hist_data['low'].iloc[i]
                prev_close = hist_data['close'].iloc[i-1]
                
                # True Range is the greatest of the three price ranges:
                # - Current high - current low
                # - Current high - previous close (absolute value)
                # - Current low - previous close (absolute value)
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            
            # Calculate ATR as simple average of TR values
            atr = sum(tr_values[-length:]) / length
            
            self.logger.info(f"Calculated ATR for {symbol} {timeframe}: {atr}")
            return atr
            
        except Exception as e:
            self.logger.error(f"Error calculating ATR for {symbol}: {e}")
            # Return a default value based on price
            current_price = await self.get_latest_price(symbol)
            return current_price * 0.01  # 1% of current price as fallback