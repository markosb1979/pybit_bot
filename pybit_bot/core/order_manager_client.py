"""
Order Manager Client - Specialized client for order management operations

This module provides a high-level interface for trading operations,
built on top of the BybitClient for reliable API communication.
It handles order placement, management, position tracking, and all
trading-related functionality.

Example usage:
    # Initialize transport layer
    credentials = APICredentials(api_key="your_key", api_secret="your_secret", testnet=True)
    transport = BybitClient(credentials)
    
    # Create order manager client
    order_client = OrderManagerClient(transport, logger=logger)
    
    # Place a market order with embedded TP/SL
    result = await order_client.place_active_order(
        symbol="BTCUSDT",
        side="Buy",
        order_type="Market",
        qty="0.01",
        take_profit="90000",
        stop_loss="85000"
    )
    
    # Or manage existing orders/positions
    positions = await order_client.get_positions("BTCUSDT")
    orders = await order_client.get_open_orders("BTCUSDT")
    cancel_result = await order_client.cancel_order("BTCUSDT", order_id)
"""

import time
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union, Tuple
import json

from .client import BybitClient
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

    def __init__(self, transport: BybitClient, logger: Optional[Logger] = None, config: Optional[Any] = None):
        """
        Initialize with BybitClient instance
        
        Args:
            transport: BybitClient instance
            logger: Optional logger instance
            config: Optional configuration
        """
        self.logger = logger or Logger("OrderManagerClient")
        self.logger.debug(f"ENTER __init__(transport={transport}, logger={logger}, config={config})")
        
        self.transport = transport
        self.config = config
        
        # Default settings
        self.default_symbol = getattr(config, 'default_symbol', "BTCUSDT") if config else "BTCUSDT"
        self.max_leverage = getattr(config, 'max_leverage', 10) if config else 10
        
        # Cache position information to reduce API calls
        self.position_cache = {}
        self.position_cache_timestamp = {}
        self.position_cache_ttl = 1.0  # 1 second cache TTL
        
        # Cache instrument info for tick size derivation
        try:
            self.logger.debug(f"Fetching instruments info for cache")
            resp = self.get_instruments_info()
            instruments = resp.get("list", [])
            
            # Map symbol -> instrument metadata
            self._instrument_info = {item["symbol"]: item for item in instruments}
            self.logger.info(f"Cached info for {len(self._instrument_info)} instruments")
            
            # Log a few symbols as sample
            if len(self._instrument_info) > 0:
                sample_symbols = list(self._instrument_info.keys())[:3]
                self.logger.debug(f"Sample symbols: {sample_symbols}")
        except Exception as e:
            self.logger.error(f"Failed to fetch instrument info: {e}")
            self._instrument_info = {}
            # Critical dependency - alert clearly
            self.logger.warning("⚠️ CRITICAL: No instrument info available. Price/quantity rounding will use defaults!")
        
        # Cache for instrument info
        self._instrument_info_cache = {}
        
        self.logger.debug(f"EXIT __init__ completed")
        
    # Rest of the class implementation remains the same, just ensure all references to BybitClientTransport are changed to BybitClient
    # ...