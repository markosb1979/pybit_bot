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


class DataManager:
    """
    Data management system for market data
    Provides price, orderbook, and ticker data with caching
    """
    
    def __init__(self, client, config, logger=None):
        """
        Initialize with client, config, and logger
        
        Args:
            client: BybitClient instance
            config: ConfigLoader instance
            logger: Optional Logger instance
        """
        self.client = client
        self.config = config
        self.logger = logger or Logger("DataManager")
        
        # Default settings
        self.default_symbol = config.get("default_symbol", "BTCUSDT")
        
        # Data caches with timestamps
        self._price_cache = {}
        self._ticker_cache = {}
        self._orderbook_cache = {}
        self._kline_cache = {}
        self._formatted_kline_cache = {}  # For formatted klines with named columns
        
        # Cache TTL in seconds
        self.price_ttl = config.get("price_cache_ttl", 1)  # 1 second for prices
        self.ticker_ttl = config.get("ticker_cache_ttl", 5)  # 5 seconds for tickers
        self.orderbook_ttl = config.get("orderbook_cache_ttl", 2)  # 2 seconds for orderbook
        self.kline_ttl = config.get("kline_cache_ttl", 60)  # 60 seconds for klines
        
        # Standard column names for kline data
        self.kline_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
        
        # WebSocket connection state
        self.ws_connected = False
        self.ws_last_update = None
        self.ws_subscriptions = set()
        
        self.logger.info("DataManager initialized")
    
    async def initialize(self):
        """Initialize data manager and connect to WebSocket"""
        self.logger.info("DataManager starting...")
        
        try:
            # Initialize ticker cache with current data
            ticker = self.client.get_ticker(self.default_symbol)
            if ticker:
                self._ticker_cache[self.default_symbol] = {
                    "data": ticker,
                    "timestamp": time.time()
                }
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
            ticker = self.client.get_ticker(symbol)
            if ticker:
                self._ticker_cache[symbol] = {
                    "data": ticker,
                    "timestamp": time.time()
                }
                # Also update price cache
                self._price_cache[symbol] = {
                    "price": float(ticker.get("lastPrice", 0)),
                    "timestamp": time.time()
                }
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
            
            return price
            
        except Exception as e:
            self.logger.error(f"Error getting latest price for {symbol}: {e}")
            return 0.0
    
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
            orderbook = self.client.get_orderbook(symbol, limit=depth)
            
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
    
    async def get_klines(self, symbol, interval="1m", limit=100):
        """
        Get historical kline data
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval (e.g., "1m", "5m", "1h")
            limit: Number of klines to retrieve
            
        Returns:
            List of kline data
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{interval}_{limit}"
            cache_entry = self._kline_cache.get(cache_key)
            current_time = time.time()
            
            if cache_entry and (current_time - cache_entry["timestamp"]) < self.kline_ttl:
                return cache_entry["data"]
            
            # Convert interval format if needed
            client_interval = interval
            if interval.endswith("m"):
                client_interval = interval[:-1]  # "1m" -> "1"
            elif interval.endswith("h"):
                client_interval = str(int(interval[:-1]) * 60)  # "1h" -> "60"
            elif interval.endswith("d"):
                client_interval = "D"  # "1d" -> "D"
            
            # Get fresh kline data
            klines = self.client.get_klines(
                symbol=symbol, 
                interval=client_interval, 
                limit=limit
            )
            
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
    
    def get_historical_data(self, symbol, interval="1m", limit=100):
        """
        Get historical kline data formatted with named columns for pandas
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval (e.g., "1m", "5m", "1h")
            limit: Number of klines to retrieve
            
        Returns:
            DataFrame with named columns for pandas
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{interval}_{limit}_formatted"
            cache_entry = self._formatted_kline_cache.get(cache_key)
            current_time = time.time()
            
            if cache_entry and (current_time - cache_entry["timestamp"]) < self.kline_ttl:
                return cache_entry["data"]
            
            # Convert interval format if needed
            client_interval = interval
            if interval.endswith("m"):
                client_interval = interval[:-1]  # "1m" -> "1"
            elif interval.endswith("h"):
                client_interval = str(int(interval[:-1]) * 60)  # "1h" -> "60"
            elif interval.endswith("d"):
                client_interval = "D"  # "1d" -> "D"
            
            # Get raw kline data
            klines = self.client.get_klines(
                symbol=symbol, 
                interval=client_interval, 
                limit=limit
            )
            
            if not klines:
                self.logger.warning(f"Failed to get historical data for {symbol}")
                return pd.DataFrame(columns=self.kline_columns)
            
            # Convert to DataFrame with named columns
            df = pd.DataFrame(klines, columns=self.kline_columns)
            
            # Convert numeric columns
            for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                df[col] = pd.to_numeric(df[col])
            
            # Convert timestamp to numeric
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            
            # Update cache
            self._formatted_kline_cache[cache_key] = {
                "data": df,
                "timestamp": current_time
            }
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting historical data for {symbol}: {e}")
            # Return empty DataFrame with correct column names
            return pd.DataFrame(columns=self.kline_columns)