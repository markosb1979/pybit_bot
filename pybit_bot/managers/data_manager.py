"""
Data Manager for PyBit Bot

This module is responsible for:
1. Loading and maintaining historical market data
2. Managing real-time data updates via WebSocket
3. Providing synchronized access to market data
4. Processing candle close events
5. Maintaining time synchronization with exchange server
"""

import time
import json
import asyncio
import websockets
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from threading import Lock

from ..core.client import BybitClient
from ..utils.logger import Logger
from ..utils.config_loader import ConfigLoader
from ..exceptions.errors import WebSocketError, BybitAPIError


class DataManager:
    """
    Manages market data through WebSocket connection and REST API,
    maintains data integrity and provides synchronized access
    """
    
    # Timeframe to milliseconds mapping
    TF_TO_MS = {
        "1m": 60 * 1000,
        "3m": 3 * 60 * 1000,
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "30m": 30 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "2h": 2 * 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "6h": 6 * 60 * 60 * 1000,
        "12h": 12 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
        "1w": 7 * 24 * 60 * 60 * 1000,
        "1M": 30 * 24 * 60 * 60 * 1000,
    }
    
    # Timeframe to seconds mapping (for timer calculations)
    TF_TO_SECONDS = {
        "1m": 60,
        "3m": 3 * 60,
        "5m": 5 * 60,
        "15m": 15 * 60,
        "30m": 30 * 60,
        "1h": 60 * 60,
        "2h": 2 * 60 * 60,
        "4h": 4 * 60 * 60,
        "6h": 6 * 60 * 60,
        "12h": 12 * 60 * 60,
        "1d": 24 * 60 * 60,
        "1w": 7 * 24 * 60 * 60,
        "1M": 30 * 24 * 60 * 60,
    }
    
    # Bybit interval mapping
    TF_TO_INTERVAL = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "2h": "120",
        "4h": "240",
        "6h": "360",
        "12h": "720",
        "1d": "D",
        "1w": "W",
        "1M": "M",
    }
    
    def __init__(
        self,
        client: BybitClient,
        config: ConfigLoader,
        logger: Optional[Logger] = None,
        on_candle_close: Optional[Callable[[str, pd.Series], None]] = None
    ):
        self.client = client
        self.config = config
        self.logger = logger or Logger("DataManager")
        self.on_candle_close = on_candle_close  # Callback for new candles
        
        # Get trading symbol from config
        self.symbol = self.config.get("trading.symbol", "BTCUSDT")
        
        # Main timeframe for trading
        self.main_timeframe = self.config.get("trading.timeframe", "1m")
        
        # Get lookback bars configuration
        self.lookback_bars = self.config.get("data.lookback_bars", {
            "1m": 2000,
            "5m": 1000,
            "1h": 200
        })
        
        # Data storage - dictionary of pandas DataFrames for each timeframe
        self.data = {}
        
        # Last candle timestamp for each timeframe
        self.last_candle_time = {}
        
        # Current candles being built from tick data
        self.current_candles = {}
        
        # Server time synchronization
        self.server_time_diff = 0  # Difference between server and local time
        self.last_sync_time = 0    # Last server sync timestamp
        
        # Timer task for candle synchronization
        self.candle_timer_task = None
        
        # Next candle close times (in seconds since epoch)
        self.next_candle_time = {}
        
        # Lock for thread-safe data updates
        self.data_lock = Lock()
        
        # WebSocket connection
        self.ws = None
        self.ws_connected = False
        self.ws_reconnect_count = 0
        self.ws_last_msg_time = 0
        self.ws_ping_interval = 20  # seconds
        self.ws_reconnect_interval = 5  # seconds
        self.ws_max_reconnect = 10
        
        # WebSocket connection URL
        self.ws_url = (
            "wss://stream-testnet.bybit.com/v5/public/linear"
            if self.client.credentials.testnet
            else "wss://stream.bybit.com/v5/public/linear"
        )
        
        # Subscribed topics
        self.subscribed_topics = set()
        
        # Flag to prefer REST API for critical data (like candle closing)
        self.use_rest_for_candle_close = True
        
        # Initialize empty data structures
        self._initialize_data_structures()
        
    def _initialize_data_structures(self):
        """Initialize empty data structures for all timeframes"""
        for tf in self.lookback_bars.keys():
            self.data[tf] = pd.DataFrame(columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume'
            ])
            self.data[tf].set_index('timestamp', inplace=True)
            
            self.current_candles[tf] = {
                'timestamp': None,
                'open': None,
                'high': None,
                'low': None,
                'close': None,
                'volume': 0
            }
    
    async def initialize(self):
        """Initialize the data manager by loading historical data"""
        self.logger.info(f"Initializing DataManager for {self.symbol}")
        
        # Synchronize with server time
        await self._sync_server_time()
        
        # Load historical data for all configured timeframes
        for timeframe, lookback in self.lookback_bars.items():
            try:
                await self.load_historical_data(timeframe, lookback)
            except Exception as e:
                self.logger.error(f"Failed to load historical data for {timeframe}: {e}")
        
        # Connect to WebSocket for real-time data
        try:
            await self.connect_websocket()
        except Exception as e:
            self.logger.error(f"Failed to connect to WebSocket: {e}")
            # Continue even if WebSocket fails - we'll retry later
        
        # Start candle timer
        self._start_candle_timer()
        
        self.logger.info("DataManager initialization completed")
        return True
    
    async def _sync_server_time(self):
        """Synchronize with Bybit server time"""
        try:
            local_time_before = time.time()
            server_time = self.client.get_server_time()
            local_time_after = time.time()
            
            # Calculate local time at the moment server responded
            local_time = (local_time_before + local_time_after) / 2
            
            # Server time in seconds
            server_time_sec = int(server_time.get("timeSecond", 0))
            
            # Calculate time difference (server - local)
            self.server_time_diff = server_time_sec - local_time
            
            # Log the synchronization
            server_datetime = datetime.fromtimestamp(server_time_sec)
            local_datetime = datetime.fromtimestamp(local_time)
            
            self.logger.info(f"Server time: {server_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Local time: {local_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Time difference: {self.server_time_diff:.2f} seconds")
            
            # Update sync time
            self.last_sync_time = local_time
            
            # Calculate next candle times
            self._calculate_next_candle_times()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to sync server time: {e}")
            return False
    
    def _calculate_next_candle_times(self):
        """Calculate next candle closing times for all timeframes"""
        # Get current server time in seconds
        current_server_time = time.time() + self.server_time_diff
        
        for timeframe in self.lookback_bars.keys():
            tf_seconds = self.TF_TO_SECONDS.get(timeframe, 60)
            
            # Calculate next candle close time
            # For 1m, this would be the next whole minute
            # For 1h, this would be the next whole hour, etc.
            next_close = current_server_time - (current_server_time % tf_seconds) + tf_seconds
            
            self.next_candle_time[timeframe] = next_close
            
            # Log next candle time
            next_close_dt = datetime.fromtimestamp(next_close)
            self.logger.info(f"Next {timeframe} candle closes at: {next_close_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def _start_candle_timer(self):
        """Start timer to track candle closings"""
        if self.candle_timer_task is not None:
            self.candle_timer_task.cancel()
            
        # Create a new task for the timer
        self.candle_timer_task = asyncio.create_task(self._candle_timer())
        
    async def _candle_timer(self):
        """Timer to trigger actions at candle close times"""
        try:
            while True:
                # Get current server time
                current_server_time = time.time() + self.server_time_diff
                
                # Find the next timeframe to close
                next_close_time = float('inf')
                next_timeframe = None
                
                for timeframe, close_time in self.next_candle_time.items():
                    if close_time < next_close_time:
                        next_close_time = close_time
                        next_timeframe = timeframe
                
                if next_timeframe is None:
                    # No candles scheduled, recalculate
                    self._calculate_next_candle_times()
                    await asyncio.sleep(1)
                    continue
                
                # Calculate time to wait
                wait_time = next_close_time - current_server_time
                
                if wait_time <= 0:
                    # Time has passed, process the candle
                    # If configured to use REST API for candle close, fetch the latest data
                    if self.use_rest_for_candle_close:
                        await self._fetch_latest_candle(next_timeframe)
                    
                    # Handle candle close
                    await self._handle_candle_close(next_timeframe)
                    
                    # Update next candle time for this timeframe
                    tf_seconds = self.TF_TO_SECONDS.get(next_timeframe, 60)
                    self.next_candle_time[next_timeframe] = next_close_time + tf_seconds
                    
                    # Re-sync with server every hour to prevent drift
                    if time.time() - self.last_sync_time > 3600:  # 1 hour
                        await self._sync_server_time()
                        
                elif wait_time < 1:
                    # Less than 1 second, wait precisely
                    await asyncio.sleep(wait_time)
                else:
                    # More than 1 second, wait with a small buffer
                    await asyncio.sleep(min(wait_time - 0.1, 1.0))
                
        except asyncio.CancelledError:
            self.logger.info("Candle timer cancelled")
        except Exception as e:
            self.logger.error(f"Error in candle timer: {e}")
            # Restart the timer
            self._start_candle_timer()
    
    async def _fetch_latest_candle(self, timeframe: str):
        """
        Fetch the latest candle data from REST API for verification
        before finalizing a candle close
        """
        try:
            # Get the interval for this timeframe
            interval = self.TF_TO_INTERVAL.get(timeframe)
            if not interval:
                return
                
            # Calculate timestamp for the candle that's about to close
            # The timestamp for a candle is its opening time
            current_server_time = time.time() + self.server_time_diff
            tf_seconds = self.TF_TO_SECONDS.get(timeframe, 60)
            candle_start_time = int((current_server_time - tf_seconds) * 1000)  # Convert to ms
            
            # Fetch the latest candles
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=interval,
                limit=2  # Get the current and previous candle
            )
            
            if not klines:
                self.logger.warning(f"No klines returned for {timeframe}")
                return
                
            # Find the matching candle
            current_candle = None
            for kline in klines:
                kline_time = int(kline[0])  # Timestamp in ms
                
                # Find the candle that matches our closing candle
                if abs(kline_time - candle_start_time) < tf_seconds * 1000:
                    current_candle = kline
                    break
            
            if not current_candle:
                self.logger.warning(f"Could not find matching candle for {timeframe} at {candle_start_time}")
                return
                
            # Update current candle with data from REST API
            with self.data_lock:
                current = self.current_candles[timeframe]
                
                # Use API data for candle close
                timestamp = pd.to_datetime(int(current_candle[0]), unit='ms')
                
                # Only update if timestamps roughly match
                if current['timestamp'] and abs((timestamp - current['timestamp']).total_seconds()) < tf_seconds:
                    # Update candle with REST API data
                    current['open'] = float(current_candle[1])
                    current['high'] = float(current_candle[2])
                    current['low'] = float(current_candle[3])
                    current['close'] = float(current_candle[4])
                    current['volume'] = float(current_candle[5])
                    
                    self.logger.info(f"Updated {timeframe} candle from REST API: O: {current['open']} H: {current['high']} L: {current['low']} C: {current['close']} V: {current['volume']}")
                else:
                    self.logger.warning(f"Timestamp mismatch: Current={current['timestamp']}, API={timestamp}")
                    
        except Exception as e:
            self.logger.error(f"Error fetching latest candle: {e}")
    
    async def _handle_candle_close(self, timeframe: str):
        """Handle candle close for a specific timeframe"""
        self.logger.debug(f"Handling {timeframe} candle close")
        
        try:
            with self.data_lock:
                # Get current candle
                current = self.current_candles.get(timeframe)
                
                if current and current['timestamp'] is not None:
                    # Validate candle data
                    valid_candle = (
                        current['open'] is not None and current['open'] > 0 and
                        current['high'] is not None and current['high'] > 0 and
                        current['low'] is not None and current['low'] > 0 and
                        current['close'] is not None and current['close'] > 0
                    )
                    
                    if not valid_candle:
                        self.logger.warning(f"Invalid {timeframe} candle detected, attempting to fix")
                        
                        # Try to fix invalid values
                        if current['close'] and current['close'] > 0:
                            # If close is valid, use it for any invalid values
                            if not current['open'] or current['open'] <= 0:
                                current['open'] = current['close']
                            if not current['high'] or current['high'] <= 0:
                                current['high'] = current['close']
                            if not current['low'] or current['low'] <= 0:
                                current['low'] = current['close']
                        elif current['open'] and current['open'] > 0:
                            # If open is valid but close isn't, use open
                            current['close'] = current['open']
                            if not current['high'] or current['high'] <= 0:
                                current['high'] = current['open']
                            if not current['low'] or current['low'] <= 0:
                                current['low'] = current['open']
                        else:
                            # If we can't fix with current data, try to fetch the latest ticker
                            try:
                                ticker = self.client.get_ticker(self.symbol)
                                last_price = float(ticker.get("lastPrice", 0))
                                
                                if last_price > 0:
                                    if not current['open'] or current['open'] <= 0:
                                        current['open'] = last_price
                                    if not current['high'] or current['high'] <= 0:
                                        current['high'] = last_price
                                    if not current['low'] or current['low'] <= 0:
                                        current['low'] = last_price
                                    if not current['close'] or current['close'] <= 0:
                                        current['close'] = last_price
                                        
                                    self.logger.info(f"Fixed {timeframe} candle using ticker price: {last_price}")
                                else:
                                    self.logger.error(f"Could not fix invalid {timeframe} candle, skipping")
                                    return
                            except Exception as e:
                                self.logger.error(f"Error fetching ticker to fix candle: {e}")
                                return
                    
                    # Ensure high >= open, close, low and low <= open, close
                    current['high'] = max(current['high'], current['open'], current['close'])
                    current['low'] = min(current['low'], current['open'], current['close'])
                    
                    # Create a new candle entry
                    new_row = pd.DataFrame([{
                        'open': current['open'],
                        'high': current['high'],
                        'low': current['low'],
                        'close': current['close'],
                        'volume': current['volume']
                    }], index=[current['timestamp']])
                    
                    # Add to dataframe
                    self.data[timeframe] = pd.concat([self.data[timeframe], new_row])
                    
                    # Update last candle time
                    self.last_candle_time[timeframe] = current['timestamp']
                    
                    # Log new candle
                    self.logger.info(f"New {timeframe} candle closed: {current['timestamp']} - O: {current['open']} H: {current['high']} L: {current['low']} C: {current['close']} V: {current['volume']}")
                    
                    # Calculate next candle timestamp
                    next_timestamp = current['timestamp'] + pd.Timedelta(timeframe)
                    
                    # Initialize next candle
                    self.current_candles[timeframe] = {
                        'timestamp': next_timestamp,
                        'open': current['close'],  # Use current close as next open
                        'high': current['close'],  # Initialize high with close price
                        'low': current['close'],   # Initialize low with close price
                        'close': current['close'], # Initialize close with close price
                        'volume': 0
                    }
                    
                    # Call the candle close callback if set
                    if self.on_candle_close:
                        # Convert to pandas Series for callback
                        candle_series = pd.Series({
                            'timestamp': current['timestamp'],
                            'open': current['open'],
                            'high': current['high'],
                            'low': current['low'],
                            'close': current['close'],
                            'volume': current['volume']
                        })
                        self.on_candle_close(timeframe, candle_series)
        
        except Exception as e:
            self.logger.error(f"Error handling {timeframe} candle close: {e}")
    
    async def load_historical_data(self, timeframe: str, lookback: int):
        """
        Load historical kline data for a specific timeframe using REST API
        """
        self.logger.info(f"Loading {lookback} {timeframe} candles for {self.symbol}")
        
        interval = self.TF_TO_INTERVAL.get(timeframe)
        if not interval:
            self.logger.error(f"Unsupported timeframe: {timeframe}")
            return
        
        # We need to make multiple requests if lookback > 1000 (API limit)
        all_klines = []
        remaining = lookback
        
        # Calculate batches
        batches = (remaining + 999) // 1000  # Ceiling division
        
        self.logger.info(f"Fetching {batches} batches of {timeframe} klines")
        
        for i in range(batches):
            batch_limit = min(1000, remaining)
            
            # If we already have klines, use the oldest one's timestamp as end time
            end_time = None
            if all_klines:
                # Convert to int and subtract 1ms to avoid duplicates
                end_time = int(all_klines[-1][0]) - 1
            
            # Make the API request
            try:
                batch = self.client.get_klines(
                    symbol=self.symbol,
                    interval=interval,
                    limit=batch_limit,
                    end_time=end_time
                )
                
                if not batch:
                    self.logger.warning(f"No klines returned for batch {i+1}")
                    break
                
                # Bybit returns newest first, so we keep that order
                all_klines.extend(batch)
                
                # Update remaining count
                remaining -= len(batch)
                
                # If we didn't get a full batch, we've reached the limit of available data
                if len(batch) < batch_limit:
                    self.logger.info(f"Reached end of available data after {len(all_klines)} {timeframe} bars")
                    break
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error fetching {timeframe} klines batch {i+1}: {e}")
                # Continue with what we have
                break
        
        self.logger.info(f"Loaded {len(all_klines)} {timeframe} klines")
        
        # Convert to DataFrame
        if all_klines:
            with self.data_lock:
                # Create DataFrame with proper column names
                df = pd.DataFrame(all_klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
                ])
                
                # Convert timestamp to milliseconds and set as index
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                df.set_index('timestamp', inplace=True)
                
                # Convert string values to float
                for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                    df[col] = df[col].astype(float)
                
                # Sort by timestamp (newest last)
                df.sort_index(inplace=True)
                
                # Store in data dictionary
                self.data[timeframe] = df
                
                # Update last candle time
                if not df.empty:
                    self.last_candle_time[timeframe] = df.index[-1]
                    
                    # Calculate next candle timestamp
                    next_timestamp = df.index[-1] + pd.Timedelta(timeframe)
                    
                    # Initialize current candle
                    self.current_candles[timeframe] = {
                        'timestamp': next_timestamp,
                        'open': float(df['close'].iloc[-1]),
                        'high': float(df['close'].iloc[-1]),
                        'low': float(df['close'].iloc[-1]),
                        'close': float(df['close'].iloc[-1]),
                        'volume': 0
                    }
                    
                    # Calculate next candle close time
                    next_close = next_timestamp.timestamp()
                    self.next_candle_time[timeframe] = next_close
    
    async def connect_websocket(self):
        """Connect to Bybit WebSocket and subscribe to topics"""
        if self.ws_connected:
            return True
        
        self.logger.info(f"Connecting to WebSocket at {self.ws_url}")
        
        try:
            # Connect to WebSocket
            self.ws = await websockets.connect(self.ws_url)
            self.ws_connected = True
            self.ws_reconnect_count = 0
            self.ws_last_msg_time = time.time()
            
            # Subscribe to topics
            await self._subscribe_topics()
            
            # Start WebSocket handler in the background
            asyncio.create_task(self._handle_websocket())
            
            # Start ping task to keep connection alive
            asyncio.create_task(self._websocket_ping())
            
            self.logger.info("WebSocket connected successfully")
            return True
            
        except Exception as e:
            self.ws_connected = False
            self.logger.error(f"WebSocket connection failed: {e}")
            return False
    
    async def _subscribe_topics(self):
        """Subscribe to WebSocket topics"""
        if not self.ws_connected:
            self.logger.error("Cannot subscribe, WebSocket not connected")
            return False
        
        # Define topics to subscribe to
        topics = [
            f"kline.{self.TF_TO_INTERVAL[tf]}.{self.symbol}" 
            for tf in self.lookback_bars.keys()
        ]
        
        # Add ticker subscription
        topics.append(f"tickers.{self.symbol}")
        
        # Add trade subscription for volume data
        topics.append(f"publicTrade.{self.symbol}")
        
        # Subscribe message
        subscribe_msg = {
            "op": "subscribe",
            "args": topics
        }
        
        try:
            # Send subscription message
            await self.ws.send(json.dumps(subscribe_msg))
            
            # Update subscribed topics
            self.subscribed_topics.update(topics)
            
            self.logger.info(f"Subscribed to topics: {topics}")
            return True
            
        except Exception as e:
            self.logger.error(f"Subscription failed: {e}")
            return False
    
    async def _handle_websocket(self):
        """Handle WebSocket messages"""
        if not self.ws_connected:
            return
        
        try:
            while self.ws_connected:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(self.ws.recv(), timeout=30)
                    self.ws_last_msg_time = time.time()
                    
                    # Process the message
                    await self._process_websocket_message(message)
                    
                except asyncio.TimeoutError:
                    # No message received in timeout period
                    self.logger.warning("WebSocket timeout, checking connection...")
                    
                    # Check if we need to reconnect
                    if time.time() - self.ws_last_msg_time > 60:
                        self.logger.error("WebSocket connection stale, reconnecting...")
                        self.ws_connected = False
                        asyncio.create_task(self._reconnect_websocket())
                        break
                    
                except websockets.exceptions.ConnectionClosed:
                    self.logger.warning("WebSocket connection closed")
                    self.ws_connected = False
                    asyncio.create_task(self._reconnect_websocket())
                    break
                    
        except Exception as e:
            self.logger.error(f"WebSocket handler error: {e}")
            self.ws_connected = False
            asyncio.create_task(self._reconnect_websocket())
    
    async def _process_websocket_message(self, message: str):
        """Process WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle ping/pong messages
            if "op" in data and data["op"] == "ping":
                await self._send_pong()
                return
            
            # Handle subscription response
            if "op" in data and data["op"] == "subscribe":
                self.logger.debug(f"Subscription response: {data}")
                return
            
            # Handle data message
            if "topic" in data:
                topic = data["topic"]
                
                # Handle kline data
                if "kline" in topic:
                    await self._process_kline_message(data)
                
                # Handle ticker data
                elif "tickers" in topic:
                    await self._process_ticker_message(data)
                
                # Handle trade data
                elif "publicTrade" in topic:
                    await self._process_trade_message(data)
            
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON in WebSocket message: {message}")
        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {e}")
    
    async def _process_kline_message(self, data: Dict[str, Any]):
        """Process kline WebSocket message"""
        try:
            topic = data["topic"]
            kline_data = data.get("data", [])
            
            if not kline_data:
                return
            
            # Extract timeframe from topic (e.g., "kline.1.BTCUSDT" -> "1")
            parts = topic.split(".")
            if len(parts) != 3:
                return
            
            interval = parts[1]
            timeframe = next((tf for tf, iv in self.TF_TO_INTERVAL.items() if iv == interval), None)
            
            if not timeframe:
                return
            
            # Process each kline in the message
            for kline in kline_data:
                # Check if this is a completed candle
                is_completed = kline.get("confirm", False)
                
                timestamp = pd.to_datetime(int(kline.get("start", 0)), unit='ms')
                open_price = float(kline.get("open", 0))
                high_price = float(kline.get("high", 0))
                low_price = float(kline.get("low", 0))
                close_price = float(kline.get("close", 0))
                volume = float(kline.get("volume", 0))
                
                # Skip invalid data
                if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
                    self.logger.debug(f"Skipping invalid kline data: {kline}")
                    continue
                
                with self.data_lock:
                    # Update current candle if it matches the timestamp
                    current = self.current_candles.get(timeframe)
                    if current and current['timestamp'] == timestamp:
                        current['open'] = open_price
                        current['high'] = high_price
                        current['low'] = low_price
                        current['close'] = close_price
                        current['volume'] = volume
                        
                        self.logger.debug(f"Updated {timeframe} candle from WebSocket: {timestamp}")
                    
                    # If this is a confirmed candle but not our current one, could be a previous candle update
                    elif is_completed and timeframe in self.data:
                        if timestamp in self.data[timeframe].index:
                            # Update historical candle
                            self.data[timeframe].loc[timestamp, 'open'] = open_price
                            self.data[timeframe].loc[timestamp, 'high'] = high_price
                            self.data[timeframe].loc[timestamp, 'low'] = low_price
                            self.data[timeframe].loc[timestamp, 'close'] = close_price
                            self.data[timeframe].loc[timestamp, 'volume'] = volume
                            
                            self.logger.debug(f"Updated historical {timeframe} candle: {timestamp}")
        
        except Exception as e:
            self.logger.error(f"Error processing kline message: {e}")
    
    async def _process_ticker_message(self, data: Dict[str, Any]):
        """Process ticker WebSocket message with enhanced logging"""
        try:
            ticker_data = data.get("data", {})
            
            if not ticker_data:
                return
            
            # Extract ticker information
            symbol = ticker_data.get("symbol", "")
            
            if symbol != self.symbol:
                return
            
            last_price = float(ticker_data.get("lastPrice", 0))
            price_24h_change = ticker_data.get("price24hPcnt", "None")
            
            # Log the ticker update (similar to test_bot_comprehensive.py)
            if last_price > 0:
                self.logger.info(f"Ticker: Last: {last_price} - 24h Change: {price_24h_change}%")
            
            # Skip invalid price
            if last_price <= 0:
                return
                
            # Update current candles with latest price
            with self.data_lock:
                for timeframe in self.current_candles:
                    current = self.current_candles[timeframe]
                    
                    if current['open'] is None or current['open'] <= 0:
                        # Initialize if not set
                        current['open'] = last_price
                        current['high'] = last_price
                        current['low'] = last_price
                        current['close'] = last_price
                    else:
                        # Update high and low
                        if last_price > current['high']:
                            current['high'] = last_price
                        
                        # Only update low if it's 0 or if the new price is lower
                        if current['low'] <= 0 or last_price < current['low']:
                            current['low'] = last_price
                    
                    # Always update close price
                    current['close'] = last_price
            
        except Exception as e:
            self.logger.error(f"Error processing ticker message: {e}")
    
    async def _process_trade_message(self, data: Dict[str, Any]):
        """Process trade WebSocket message with enhanced logging"""
        try:
            trade_data = data.get("data", [])
            
            if not trade_data:
                return
            
            # Log first trade in batch (for visibility at DEBUG level)
            if trade_data and len(trade_data) > 0:
                trade = trade_data[0]
                symbol = trade.get("symbol", "")
                price = float(trade.get("p", 0))
                size = float(trade.get("v", 0))
                side = trade.get("S", "?")
                
                if symbol == self.symbol and price > 0:
                    self.logger.debug(f"Trade: {symbol} {side} {size} @ {price}")
            
            # Process each trade
            for trade in trade_data:
                # Extract trade information
                symbol = trade.get("symbol", "")
                
                if symbol != self.symbol:
                    continue
                    
                price = float(trade.get("p", 0))  # Price
                volume = float(trade.get("v", 0))  # Volume
                
                if price <= 0 or volume <= 0:
                    continue
                
                # Update current candles with trade data
                with self.data_lock:
                    for timeframe in self.current_candles:
                        current = self.current_candles[timeframe]
                        
                        # Update volume
                        current['volume'] += volume
                        
                        # Update price data if needed
                        if current['open'] is None or current['open'] <= 0:
                            current['open'] = price
                            current['high'] = price
                            current['low'] = price
                            current['close'] = price
                        else:
                            # Update high/low
                            if price > current['high']:
                                current['high'] = price
                                
                            if current['low'] <= 0 or price < current['low']:
                                current['low'] = price
                                
                            # Update close price
                            current['close'] = price
        
        except Exception as e:
            self.logger.error(f"Error processing trade message: {e}")
    
    async def _send_pong(self):
        """Send pong response to ping"""
        if not self.ws_connected:
            return
        
        try:
            pong_msg = {"op": "pong"}
            await self.ws.send(json.dumps(pong_msg))
        except Exception as e:
            self.logger.error(f"Error sending pong: {e}")
            self.ws_connected = False
            asyncio.create_task(self._reconnect_websocket())
    
    async def _websocket_ping(self):
        """Send periodic ping to keep WebSocket connection alive"""
        while self.ws_connected:
            try:
                # Wait for ping interval
                await asyncio.sleep(self.ws_ping_interval)
                
                # Check if connection is still active
                if not self.ws_connected:
                    break
                
                # Check if we need to send a ping
                if time.time() - self.ws_last_msg_time > self.ws_ping_interval:
                    ping_msg = {"op": "ping"}
                    await self.ws.send(json.dumps(ping_msg))
            
            except Exception as e:
                self.logger.error(f"WebSocket ping error: {e}")
                self.ws_connected = False
                asyncio.create_task(self._reconnect_websocket())
                break
    
    async def _reconnect_websocket(self):
        """Reconnect to WebSocket if disconnected"""
        if self.ws_connected:
            return
        
        self.ws_reconnect_count += 1
        
        if self.ws_reconnect_count > self.ws_max_reconnect:
            self.logger.error(f"Max WebSocket reconnect attempts reached ({self.ws_max_reconnect})")
            return
        
        self.logger.warning(f"Reconnecting to WebSocket (attempt {self.ws_reconnect_count})")
        
        # Wait before reconnecting
        await asyncio.sleep(self.ws_reconnect_interval)
        
        try:
            # Close existing connection if any
            if self.ws:
                await self.ws.close()
            
            # Connect to WebSocket
            await self.connect_websocket()
            
        except Exception as e:
            self.logger.error(f"WebSocket reconnection failed: {e}")
            # Schedule another reconnect attempt
            asyncio.create_task(self._reconnect_websocket())
    
    def get_data(self, timeframe: str, lookback: int = None) -> pd.DataFrame:
        """
        Get market data for a specific timeframe
        
        Args:
            timeframe: Timeframe string (e.g., "1m", "5m")
            lookback: Number of candles to return (None for all)
            
        Returns:
            Pandas DataFrame with market data
        """
        with self.data_lock:
            if timeframe not in self.data:
                self.logger.warning(f"No data available for timeframe {timeframe}")
                return pd.DataFrame()
            
            df = self.data[timeframe].copy()
            
            if lookback and not df.empty:
                return df.iloc[-lookback:]
            
            return df
    
    def get_latest_price(self) -> float:
        """Get the latest price for the trading symbol"""
        with self.data_lock:
            # Try to get from current candle
            if self.main_timeframe in self.current_candles:
                current = self.current_candles[self.main_timeframe]
                if current['close'] is not None and current['close'] > 0:
                    return current['close']
            
            # Fall back to historical data
            if self.main_timeframe in self.data and not self.data[self.main_timeframe].empty:
                return float(self.data[self.main_timeframe]['close'].iloc[-1])
            
        # If no data available, fetch from API
        try:
            ticker = self.client.get_ticker(self.symbol)
            return float(ticker.get("lastPrice", 0))
        except Exception as e:
            self.logger.error(f"Error getting latest price: {e}")
            return 0.0
    
    def get_server_time(self) -> float:
        """Get current server time in seconds"""
        return time.time() + self.server_time_diff
    
    def get_next_candle_time(self, timeframe: str = None) -> float:
        """
        Get the next candle close time for a specific timeframe
        
        Args:
            timeframe: Timeframe to check (default: main timeframe)
            
        Returns:
            Timestamp in seconds for next candle close
        """
        tf = timeframe or self.main_timeframe
        return self.next_candle_time.get(tf, 0)
    
    def register_candle_callback(self, callback: Callable[[str, pd.Series], None]):
        """
        Register a callback to be called when a new candle closes
        
        Args:
            callback: Function to call with (timeframe, candle_data)
        """
        self.on_candle_close = callback
    
    async def close(self):
        """Close WebSocket connection and clean up"""
        self.logger.info("Closing DataManager connections")
        
        # Cancel candle timer
        if self.candle_timer_task:
            self.candle_timer_task.cancel()
            self.candle_timer_task = None
        
        # Close WebSocket
        if self.ws_connected and self.ws:
            try:
                await self.ws.close()
                self.ws_connected = False
                self.logger.info("WebSocket connection closed")
            except Exception as e:
                self.logger.error(f"Error closing WebSocket: {e}")