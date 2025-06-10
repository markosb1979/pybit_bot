"""
OrderManager - High-level order management abstraction
Uses OrderManagerClient for core trading functionality
"""

import logging
from typing import Dict, List, Optional, Any, Union
import asyncio

from ..core.order_manager_client import OrderManagerClient
from ..utils.logger import Logger


class OrderManager:
    """
    Order management abstraction layer for strategy integration
    Provides async interface to OrderManagerClient for strategy integration
    """
    
    def __init__(self, client, config, logger=None):
        """
        Initialize with client, config, and logger
        """
        self.client = client
        self.config = config
        self.logger = logger or Logger("OrderManager")
        
        # Create OrderManagerClient instance
        self.order_client = OrderManagerClient(client, self.logger, config)
        
        # Default trading settings
        self.default_symbol = config.get("default_symbol", "BTCUSDT")
        
        self.logger.info("OrderManager initialized")
    
    async def initialize(self):
        """Initialize order manager and connect to API"""
        self.logger.info("OrderManager starting...")
        
        try:
            # Get instrument info for default symbol
            self.order_client.get_instrument_info(self.default_symbol)
            
            # Small delay to make this a proper coroutine
            await asyncio.sleep(0)
            
            self.logger.info("OrderManager initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing OrderManager: {str(e)}")
            return False
        
    async def close(self):
        """Clean shutdown of order manager"""
        self.logger.info("OrderManager shutting down...")
        try:
            # Small delay to make this a proper coroutine
            await asyncio.sleep(0)
            return True
        except Exception as e:
            self.logger.error(f"Error closing OrderManager: {str(e)}")
            return False
    
    # ========== CORE TRADING METHODS ==========
    
    async def get_positions(self, symbol=None):
        """
        Get current positions - ASYNC WRAPPER
        """
        result = self.order_client.get_positions(symbol)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def calculate_position_size(self, symbol, usdt_amount):
        """
        Calculate order size based on USDT amount - ASYNC WRAPPER
        
        Note: Modified to match test expectations
        """
        # Get price from data_manager if possible, otherwise use order_client
        price = None
        if hasattr(self, 'data_manager') and hasattr(self.data_manager, 'get_latest_price'):
            try:
                price = await self.data_manager.get_latest_price(symbol)
            except:
                pass
                
        result = self.order_client.calculate_position_size(symbol, usdt_amount, price)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def place_market_order(self, symbol, side, qty):
        """
        Place market order - ASYNC WRAPPER
        """
        result = self.order_client.place_market_order(symbol, side, qty)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def place_limit_order(self, symbol, side, qty, price):
        """
        Place limit order - ASYNC WRAPPER
        """
        result = self.order_client.place_limit_order(symbol, side, qty, price)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def set_take_profit(self, symbol, price):
        """
        Set take profit for current position - ASYNC WRAPPER
        """
        result = self.order_client.set_take_profit(symbol, price)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def set_stop_loss(self, symbol, price):
        """
        Set stop loss for current position - ASYNC WRAPPER
        """
        result = self.order_client.set_stop_loss(symbol, price)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def get_order_status(self, symbol, order_id):
        """
        Check status of a specific order - ASYNC WRAPPER
        """
        result = self.order_client.get_order_status(symbol, order_id)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def cancel_order(self, symbol, order_id):
        """
        Cancel a specific order - ASYNC WRAPPER
        """
        result = self.order_client.cancel_order(symbol, order_id)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def close_position(self, symbol):
        """
        Close an entire position - ASYNC WRAPPER
        """
        result = self.order_client.close_position(symbol)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def get_account_balance(self):
        """
        Get account wallet balance - ASYNC WRAPPER
        """
        result = self.order_client.get_account_balance()
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def get_active_orders(self, symbol=None):
        """
        Get all active orders - ASYNC WRAPPER
        """
        result = self.order_client.get_active_orders(symbol)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    async def get_order_history(self, symbol=None):
        """
        Get historical orders - ASYNC WRAPPER
        """
        result = self.order_client.get_order_history(symbol)
        await asyncio.sleep(0)  # Make awaitable
        return result
    
    # ========== ENHANCED TRADING METHODS ==========
    
    async def enter_long_with_tp_sl(self, symbol, qty, tp_price=None, sl_price=None):
        """
        Enter long position with optional TP/SL
        """
        # Place the entry order
        entry_order = await self.place_market_order(symbol, "Buy", qty)
        
        if "error" in entry_order:
            return entry_order
            
        result = {
            "entry_order": entry_order,
            "tp_order": None,
            "sl_order": None
        }
        
        # Set take profit if specified
        if tp_price:
            tp_order = await self.set_take_profit(symbol, tp_price)
            result["tp_order"] = tp_order
            
        # Set stop loss if specified
        if sl_price:
            sl_order = await self.set_stop_loss(symbol, sl_price)
            result["sl_order"] = sl_order
            
        return result
    
    async def enter_short_with_tp_sl(self, symbol, qty, tp_price=None, sl_price=None):
        """
        Enter short position with optional TP/SL
        """
        # Place the entry order
        entry_order = await self.place_market_order(symbol, "Sell", qty)
        
        if "error" in entry_order:
            return entry_order
            
        result = {
            "entry_order": entry_order,
            "tp_order": None,
            "sl_order": None
        }
        
        # Set take profit if specified
        if tp_price:
            tp_order = await self.set_take_profit(symbol, tp_price)
            result["tp_order"] = tp_order
            
        # Set stop loss if specified
        if sl_price:
            sl_order = await self.set_stop_loss(symbol, sl_price)
            result["sl_order"] = sl_order
            
        return result
    
    async def scale_in_position(self, symbol, side, qty, price=None):
        """
        Add to existing position
        """
        if price:
            return await self.place_limit_order(symbol, side, qty, price)
        else:
            return await self.place_market_order(symbol, side, qty)
    
    async def scale_out_position(self, symbol, percent=50):
        """
        Reduce position size by percentage - ASYNC WRAPPER
        """
        result = self.order_client.scale_out_position(symbol, percent)
        await asyncio.sleep(0)  # Make awaitable
        return result