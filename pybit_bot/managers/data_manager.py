"""
Data Manager - Manages market data collection and access

This module handles the connection to exchange data feeds,
processes market data, and provides a unified interface for
strategies to access market data.
"""

import os
import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

from ..utils.logger import Logger


class DataManager:
    """
    DataManager handles market data processing and storage
    """
    
    def __init__(self, client, config, logger=None, order_client=None):
        """
        Initialize the data manager
        
        Args:
            client: API client instance
            config: Configuration dictionary
            logger: Optional logger instance
            order_client: Optional order client for additional market data
        """
        self.logger = logger or Logger("DataManager")
        self.logger.debug(f"ENTER __init__(client={client}, config_id={id(config)}, logger={logger}, order_client={order_client})")
        
        self.client = client
        self.config = config
        self.order_client = order_client
        
        # Market data cache
        self.klines = {}  # Format: {symbol: {timeframe: pd.DataFrame}}
        self.tickers = {}  # Latest ticker data
        self.orderbooks = {}  # Latest orderbook data
        
        # Subscriptions
        self.kline_subscriptions = set()  # Format: {(symbol, timeframe)}
        self.ticker_subscriptions = set()  # Format: {symbol}
        self.orderbook_subscriptions = set()  # Format: {symbol}
        
        # Configuration
        data_config = self.config.get('general', {}).get('data', {})
        self.lookback_bars = data_config.get('lookback_bars', {
            '1m': 1000,
            '5m': 500,
            '15m': 200,
            '1h': 100,
            '4h': 50,
            '1d': 30
        })
        
        # WebSocket connection
        self.ws_connected = False
        self.ws_task = None
        
        self.logger.info("DataManager initialized")
        self.logger.debug(f"EXIT __init__ completed")
    
    def subscribe_klines(self, symbol: str, timeframe: str) -> bool:
        """
        Subscribe to kline (candlestick) data
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            timeframe: Timeframe (e.g., "1m", "5m", "1h")
            
        Returns:
            True if subscription was successful, False otherwise
        """
        self.logger.debug(f"ENTER subscribe_klines(symbol={symbol}, timeframe={timeframe})")
        
        try:
            # Add to subscriptions
            subscription = (symbol, timeframe)
            self.kline_subscriptions.add(subscription)
            
            # Initialize klines container if needed
            if symbol not in self.klines:
                self.klines[symbol] = {}
                
            if timeframe not in self.klines[symbol]:
                self.klines[symbol][timeframe] = pd.DataFrame()
                
            self.logger.info(f"Subscribed to {symbol} {timeframe} klines")
            self.logger.debug(f"EXIT subscribe_klines returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to klines: {str(e)}")
            self.logger.debug(f"EXIT subscribe_klines returned False (error)")
            return False
    
    def subscribe_ticker(self, symbol: str) -> bool:
        """
        Subscribe to ticker data
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            
        Returns:
            True if subscription was successful, False otherwise
        """
        self.logger.debug(f"ENTER subscribe_ticker(symbol={symbol})")
        
        try:
            # Add to subscriptions
            self.ticker_subscriptions.add(symbol)
            
            # Initialize ticker container if needed
            if symbol not in self.tickers:
                self.tickers[symbol] = {}
                
            self.logger.info(f"Subscribed to {symbol} ticker")
            self.logger.debug(f"EXIT subscribe_ticker returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to ticker: {str(e)}")
            self.logger.debug(f"EXIT subscribe_ticker returned False (error)")
            return False
    
    def subscribe_orderbook(self, symbol: str) -> bool:
        """
        Subscribe to orderbook data
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            
        Returns:
            True if subscription was successful, False otherwise
        """
        self.logger.debug(f"ENTER subscribe_orderbook(symbol={symbol})")
        
        try:
            # Add to subscriptions
            self.orderbook_subscriptions.add(symbol)
            
            # Initialize orderbook container if needed
            if symbol not in self.orderbooks:
                self.orderbooks[symbol] = {
                    'bids': [],
                    'asks': [],
                    'timestamp': 0
                }
                
            self.logger.info(f"Subscribed to {symbol} orderbook")
            self.logger.debug(f"EXIT subscribe_orderbook returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to orderbook: {str(e)}")
            self.logger.debug(f"EXIT subscribe_orderbook returned False (error)")
            return False
    
    async def load_initial_data(self) -> bool:
        """
        Load initial historical data for all subscriptions
        
        Returns:
            True if data was loaded successfully, False otherwise
        """
        self.logger.debug(f"ENTER load_initial_data()")
        
        try:
            # Load klines for all subscriptions
            for symbol, timeframe in self.kline_subscriptions:
                self.logger.info(f"Loading initial klines for {symbol} {timeframe}")
                
                # Get number of bars to fetch
                lookback = self.lookback_bars.get(timeframe, 1000)
                
                # Fetch historical klines
                success = await self._fetch_historical_klines(symbol, timeframe, lookback)
                if not success:
                    self.logger.warning(f"Failed to load initial klines for {symbol} {timeframe}")
            
            # Load tickers for all subscriptions
            for symbol in self.ticker_subscriptions:
                self.logger.info(f"Loading initial ticker for {symbol}")
                
                # Fetch latest ticker
                success = await self._fetch_ticker(symbol)
                if not success:
                    self.logger.warning(f"Failed to load initial ticker for {symbol}")
            
            # Load orderbooks for all subscriptions
            for symbol in self.orderbook_subscriptions:
                self.logger.info(f"Loading initial orderbook for {symbol}")
                
                # Fetch latest orderbook
                success = await self._fetch_orderbook(symbol)
                if not success:
                    self.logger.warning(f"Failed to load initial orderbook for {symbol}")
            
            self.logger.info("Initial data loading completed")
            self.logger.debug(f"EXIT load_initial_data returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading initial data: {str(e)}")
            self.logger.debug(f"EXIT load_initial_data returned False (error)")
            return False
    
    async def update_market_data(self) -> bool:
        """
        Update all subscribed market data
        
        Returns:
            True if update was successful, False otherwise
        """
        self.logger.debug(f"ENTER update_market_data()")
        
        try:
            # Update tickers
            for symbol in self.ticker_subscriptions:
                await self._fetch_ticker(symbol)
            
            # Update klines that need updating
            current_time = datetime.now().timestamp()
            for symbol, timeframe in self.kline_subscriptions:
                # Check if we need to update
                last_update = self._get_last_kline_timestamp(symbol, timeframe)
                if current_time - last_update > self._get_timeframe_seconds(timeframe):
                    await self._fetch_recent_klines(symbol, timeframe, 2)
            
            # Update orderbooks if needed
            for symbol in self.orderbook_subscriptions:
                await self._fetch_orderbook(symbol)
            
            self.logger.debug(f"EXIT update_market_data returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating market data: {str(e)}")
            self.logger.debug(f"EXIT update_market_data returned False (error)")
            return False
    
    async def _fetch_historical_klines(self, symbol: str, timeframe: str, limit: int = 1000) -> bool:
        """
        Fetch historical klines for a symbol and timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe interval
            limit: Number of candles to fetch
            
        Returns:
            True if fetch was successful, False otherwise
        """
        self.logger.debug(f"ENTER _fetch_historical_klines(symbol={symbol}, timeframe={timeframe}, limit={limit})")
        
        try:
            # Prepare parameters
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": timeframe,
                "limit": min(limit, 1000)  # API limit is 1000
            }
            
            # Make request
            response = await self.client.get_klines(params)
            
            # Process response
            if response and response.get("retCode") == 0:
                klines_data = response.get("result", {}).get("list", [])
                
                if not klines_data:
                    self.logger.warning(f"No klines data returned for {symbol} {timeframe}")
                    self.logger.debug(f"EXIT _fetch_historical_klines returned False (no data)")
                    return False
                
                # Convert to DataFrame
                df = self._convert_klines_to_dataframe(klines_data)
                
                # Store in cache
                self.klines[symbol][timeframe] = df
                
                self.logger.info(f"Fetched {len(df)} historical klines for {symbol} {timeframe}")
                self.logger.debug(f"EXIT _fetch_historical_klines returned True")
                return True
            else:
                error_msg = response.get("retMsg", "Unknown error") if response else "No response"
                self.logger.error(f"Error fetching historical klines: {error_msg}")
                self.logger.debug(f"EXIT _fetch_historical_klines returned False (API error)")
                return False
                
        except Exception as e:
            self.logger.error(f"Error fetching historical klines: {str(e)}")
            self.logger.debug(f"EXIT _fetch_historical_klines returned False (exception)")
            return False
    
    async def _fetch_recent_klines(self, symbol: str, timeframe: str, limit: int = 2) -> bool:
        """
        Fetch recent klines and update the cache
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe interval
            limit: Number of recent candles to fetch
            
        Returns:
            True if fetch was successful, False otherwise
        """
        self.logger.debug(f"ENTER _fetch_recent_klines(symbol={symbol}, timeframe={timeframe}, limit={limit})")
        
        try:
            # Prepare parameters
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": timeframe,
                "limit": limit
            }
            
            # Make request
            response = await self.client.get_klines(params)
            
            # Process response
            if response and response.get("retCode") == 0:
                klines_data = response.get("result", {}).get("list", [])
                
                if not klines_data:
                    self.logger.warning(f"No recent klines data returned for {symbol} {timeframe}")
                    self.logger.debug(f"EXIT _fetch_recent_klines returned False (no data)")
                    return False
                
                # Convert to DataFrame
                new_df = self._convert_klines_to_dataframe(klines_data)
                
                # Get existing data
                existing_df = self.klines.get(symbol, {}).get(timeframe, pd.DataFrame())
                
                if existing_df.empty:
                    # No existing data, just use the new data
                    self.klines[symbol][timeframe] = new_df
                else:
                    # Update existing data with new data
                    # First remove any overlapping timestamps
                    if not new_df.empty and not existing_df.empty:
                        existing_df = existing_df[~existing_df.index.isin(new_df.index)]
                        
                        # Concatenate and sort
                        combined_df = pd.concat([existing_df, new_df])
                        combined_df = combined_df.sort_index()
                        
                        # Limit to lookback bars
                        lookback = self.lookback_bars.get(timeframe, 1000)
                        if len(combined_df) > lookback:
                            combined_df = combined_df.iloc[-lookback:]
                            
                        # Store updated DataFrame
                        self.klines[symbol][timeframe] = combined_df
                
                self.logger.info(f"Updated klines for {symbol} {timeframe}")
                self.logger.debug(f"EXIT _fetch_recent_klines returned True")
                return True
            else:
                error_msg = response.get("retMsg", "Unknown error") if response else "No response"
                self.logger.error(f"Error fetching recent klines: {error_msg}")
                self.logger.debug(f"EXIT _fetch_recent_klines returned False (API error)")
                return False
                
        except Exception as e:
            self.logger.error(f"Error fetching recent klines: {str(e)}")
            self.logger.debug(f"EXIT _fetch_recent_klines returned False (exception)")
            return False
    
    async def _fetch_ticker(self, symbol: str) -> bool:
        """
        Fetch latest ticker for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if fetch was successful, False otherwise
        """
        self.logger.debug(f"ENTER _fetch_ticker(symbol={symbol})")
        
        try:
            # Prepare parameters
            params = {
                "category": "linear",
                "symbol": symbol
            }
            
            # Make request
            response = await self.client.get_tickers(params)
            
            # Process response
            if response and response.get("retCode") == 0:
                ticker_data = response.get("result", {}).get("list", [])
                
                if not ticker_data or len(ticker_data) == 0:
                    self.logger.warning(f"No ticker data returned for {symbol}")
                    self.logger.debug(f"EXIT _fetch_ticker returned False (no data)")
                    return False
                
                # Store in cache
                self.tickers[symbol] = ticker_data[0]
                
                self.logger.debug(f"Updated ticker for {symbol}")
                self.logger.debug(f"EXIT _fetch_ticker returned True")
                return True
            else:
                error_msg = response.get("retMsg", "Unknown error") if response else "No response"
                self.logger.error(f"Error fetching ticker: {error_msg}")
                self.logger.debug(f"EXIT _fetch_ticker returned False (API error)")
                return False
                
        except Exception as e:
            self.logger.error(f"Error fetching ticker: {str(e)}")
            self.logger.debug(f"EXIT _fetch_ticker returned False (exception)")
            return False
    
    async def _fetch_orderbook(self, symbol: str, limit: int = 50) -> bool:
        """
        Fetch orderbook for a symbol
        
        Args:
            symbol: Trading symbol
            limit: Depth of orderbook
            
        Returns:
            True if fetch was successful, False otherwise
        """
        self.logger.debug(f"ENTER _fetch_orderbook(symbol={symbol}, limit={limit})")
        
        try:
            # Prepare parameters
            params = {
                "category": "linear",
                "symbol": symbol,
                "limit": limit
            }
            
            # Make request
            response = await self.client.get_orderbook(params)
            
            # Process response
            if response and response.get("retCode") == 0:
                orderbook_data = response.get("result", {})
                
                if not orderbook_data:
                    self.logger.warning(f"No orderbook data returned for {symbol}")
                    self.logger.debug(f"EXIT _fetch_orderbook returned False (no data)")
                    return False
                
                # Store in cache
                self.orderbooks[symbol] = {
                    'bids': orderbook_data.get('b', []),
                    'asks': orderbook_data.get('a', []),
                    'timestamp': orderbook_data.get('ts', int(time.time() * 1000))
                }
                
                self.logger.debug(f"Updated orderbook for {symbol}")
                self.logger.debug(f"EXIT _fetch_orderbook returned True")
                return True
            else:
                error_msg = response.get("retMsg", "Unknown error") if response else "No response"
                self.logger.error(f"Error fetching orderbook: {error_msg}")
                self.logger.debug(f"EXIT _fetch_orderbook returned False (API error)")
                return False
                
        except Exception as e:
            self.logger.error(f"Error fetching orderbook: {str(e)}")
            self.logger.debug(f"EXIT _fetch_orderbook returned False (exception)")
            return False
    
    def _convert_klines_to_dataframe(self, klines_data: List[List]) -> pd.DataFrame:
        """
        Convert klines data from API to pandas DataFrame
        
        Args:
            klines_data: List of klines from API
            
        Returns:
            Pandas DataFrame with processed klines
        """
        # Check if we have data
        if not klines_data:
            return pd.DataFrame()
            
        # Create DataFrame
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
        df = pd.DataFrame(klines_data, columns=columns)
        
        # Convert types
        df['timestamp'] = pd.to_numeric(df['timestamp'])
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        df['turnover'] = pd.to_numeric(df['turnover'])
        
        # Set timestamp as index
        df.set_index('timestamp', inplace=True)
        
        # Sort by timestamp
        df.sort_index(inplace=True)
        
        return df
    
    def _get_last_kline_timestamp(self, symbol: str, timeframe: str) -> float:
        """
        Get the timestamp of the last kline in the cache
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe interval
            
        Returns:
            Timestamp in seconds
        """
        # Get klines for symbol and timeframe
        klines_df = self.klines.get(symbol, {}).get(timeframe)
        
        if klines_df is None or klines_df.empty:
            # No data, return old timestamp to force update
            return 0
            
        # Get the latest timestamp
        latest_ts = klines_df.index[-1]
        
        # Convert from milliseconds to seconds if needed
        if latest_ts > 1e12:  # Timestamp is in milliseconds
            latest_ts = latest_ts / 1000
            
        return latest_ts
    
    def _get_timeframe_seconds(self, timeframe: str) -> int:
        """
        Convert timeframe string to seconds
        
        Args:
            timeframe: Timeframe string (e.g., "1m", "5m", "1h")
            
        Returns:
            Seconds
        """
        # Parse timeframe
        value = int(timeframe[:-1])
        unit = timeframe[-1]
        
        # Convert to seconds
        if unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 60 * 60
        elif unit == 'd':
            return value * 60 * 60 * 24
        elif unit == 'w':
            return value * 60 * 60 * 24 * 7
        else:
            return 60  # Default to 1 minute
    
    def get_klines(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Get klines data for a symbol and timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe interval
            
        Returns:
            DataFrame with klines data or empty DataFrame if not found
        """
        self.logger.debug(f"ENTER get_klines(symbol={symbol}, timeframe={timeframe})")
        
        try:
            # Get klines from cache
            df = self.klines.get(symbol, {}).get(timeframe, pd.DataFrame())
            
            if df.empty:
                self.logger.warning(f"No klines data found for {symbol} {timeframe}")
                
            self.logger.debug(f"EXIT get_klines returned DataFrame with {len(df)} rows")
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting klines: {str(e)}")
            self.logger.debug(f"EXIT get_klines returned empty DataFrame (error)")
            return pd.DataFrame()
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get ticker data for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with ticker data or empty dict if not found
        """
        self.logger.debug(f"ENTER get_ticker(symbol={symbol})")
        
        try:
            # Get ticker from cache
            ticker = self.tickers.get(symbol, {})
            
            if not ticker:
                self.logger.warning(f"No ticker data found for {symbol}")
                
            self.logger.debug(f"EXIT get_ticker returned ticker data")
            return ticker
            
        except Exception as e:
            self.logger.error(f"Error getting ticker: {str(e)}")
            self.logger.debug(f"EXIT get_ticker returned empty dict (error)")
            return {}
    
    def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        """
        Get orderbook data for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with orderbook data or empty dict if not found
        """
        self.logger.debug(f"ENTER get_orderbook(symbol={symbol})")
        
        try:
            # Get orderbook from cache
            orderbook = self.orderbooks.get(symbol, {})
            
            if not orderbook:
                self.logger.warning(f"No orderbook data found for {symbol}")
                
            self.logger.debug(f"EXIT get_orderbook returned orderbook data")
            return orderbook
            
        except Exception as e:
            self.logger.error(f"Error getting orderbook: {str(e)}")
            self.logger.debug(f"EXIT get_orderbook returned empty dict (error)")
            return {}
    
    def get_market_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or 0 if not found
        """
        self.logger.debug(f"ENTER get_market_price(symbol={symbol})")
        
        try:
            # Try to get price from ticker
            ticker = self.get_ticker(symbol)
            if ticker and 'last_price' in ticker:
                price = float(ticker['last_price'])
                self.logger.debug(f"EXIT get_market_price returned {price}")
                return price
                
            # If ticker not available, try orderbook mid price
            orderbook = self.get_orderbook(symbol)
            if orderbook and orderbook.get('bids') and orderbook.get('asks'):
                best_bid = float(orderbook['bids'][0][0])
                best_ask = float(orderbook['asks'][0][0])
                mid_price = (best_bid + best_ask) / 2
                self.logger.debug(f"EXIT get_market_price returned {mid_price} (from orderbook)")
                return mid_price
                
            # If no price found, return 0
            self.logger.warning(f"No price data found for {symbol}")
            self.logger.debug(f"EXIT get_market_price returned 0 (no data)")
            return 0
            
        except Exception as e:
            self.logger.error(f"Error getting market price: {str(e)}")
            self.logger.debug(f"EXIT get_market_price returned 0 (error)")
            return 0
    
    async def start_websocket(self) -> bool:
        """
        Start WebSocket connection for real-time updates
        
        Returns:
            True if WebSocket started successfully, False otherwise
        """
        self.logger.debug(f"ENTER start_websocket()")
        
        try:
            # Check if WebSocket is already running
            if self.ws_task and not self.ws_task.done():
                self.logger.info("WebSocket is already running")
                self.logger.debug(f"EXIT start_websocket returned True (already running)")
                return True
                
            # Start WebSocket task
            self.ws_task = asyncio.create_task(self._websocket_handler())
            
            self.logger.info("WebSocket connection started")
            self.logger.debug(f"EXIT start_websocket returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting WebSocket: {str(e)}")
            self.logger.debug(f"EXIT start_websocket returned False (error)")
            return False
    
    async def stop_websocket(self) -> bool:
        """
        Stop WebSocket connection
        
        Returns:
            True if WebSocket stopped successfully, False otherwise
        """
        self.logger.debug(f"ENTER stop_websocket()")
        
        try:
            # Cancel WebSocket task if running
            if self.ws_task and not self.ws_task.done():
                self.ws_task.cancel()
                try:
                    await self.ws_task
                except asyncio.CancelledError:
                    pass
                    
            self.ws_connected = False
            self.ws_task = None
            
            self.logger.info("WebSocket connection stopped")
            self.logger.debug(f"EXIT stop_websocket returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping WebSocket: {str(e)}")
            self.logger.debug(f"EXIT stop_websocket returned False (error)")
            return False
    
    async def _websocket_handler(self) -> None:
        """
        WebSocket connection handler
        """
        self.logger.debug(f"ENTER _websocket_handler()")
        
        try:
            # Get WebSocket URL and other parameters
            ws_url = "wss://stream-testnet.bybit.com/v5/public/linear"
            
            # Connect to WebSocket
            self.logger.info(f"Connecting to WebSocket: {ws_url}")
            
            # Here we would connect to the WebSocket and handle messages
            # This would involve implementing WebSocket connection to Bybit API
            # For now, we'll just use a placeholder that sleeps
            
            self.ws_connected = True
            
            # Keep connection alive
            while True:
                # Process WebSocket messages
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            self.logger.info("WebSocket task cancelled")
        except Exception as e:
            self.logger.error(f"WebSocket error: {str(e)}")
        finally:
            self.ws_connected = False
            self.logger.debug(f"EXIT _websocket_handler completed")