#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TPSL Manager

Manages take profit and stop loss orders according to the specified strategy requirements.
Implements ATR-based TP/SL and running (trailing) stop functionality.
"""

import logging
import time
import json
import os
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Status of TP/SL orders."""
    PENDING = "pending"
    ACTIVE = "active"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class TPSLManager:
    """
    Manages take profit and stop loss orders for open positions.
    
    Implements OCO (one-cancels-other) order management with 
    ATR-based fixed and trailing stop functionality.
    """
    
    def __init__(self, client, order_manager, data_manager):
        """
        Initialize the TPSL Manager.
        
        Args:
            client: Bybit API client
            order_manager: Order manager instance
            data_manager: Data manager instance for accessing ATR values
        """
        self.client = client
        self.order_manager = order_manager
        self.data_manager = data_manager
        
        # Load indicator configuration
        self.config = self._load_indicator_config()
        
        # Track active orders
        self.tp_orders = {}  # symbol -> order_id
        self.sl_orders = {}  # symbol -> order_id
        
        # Trailing stop tracking
        self.trailing_stops = {}  # symbol -> trailing stop state
        
        # State flags
        self.is_running = False
        self.last_check_time = 0
        self.check_interval_sec = 1.0  # Check every second
    
    def _load_indicator_config(self) -> Dict[str, Any]:
        """
        Load indicator configuration from indicators.json
        
        Returns:
            Configuration dictionary
        """
        try:
            config_path = "indicators.json"
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
            
            logger.warning(f"Indicator config file not found: {config_path}")
            return {}
        except Exception as e:
            logger.error(f"Error loading indicator config: {str(e)}")
            return {}
    
    def start(self):
        """Start the TPSL manager."""
        if self.is_running:
            logger.warning("TPSL Manager is already running")
            return
            
        logger.info("Starting TPSL Manager")
        self.is_running = True
    
    def stop(self):
        """Stop the TPSL manager."""
        if not self.is_running:
            return
            
        logger.info("Stopping TPSL Manager")
        self.is_running = False
    
    def process(self):
        """
        Process all open positions and manage their TP/SL orders.
        This should be called regularly from the main loop.
        """
        if not self.is_running:
            return
            
        current_time = time.time()
        if current_time - self.last_check_time < self.check_interval_sec:
            return
            
        self.last_check_time = current_time
        
        try:
            # Get all open positions
            positions = self.order_manager.get_positions()
            
            # Process each position
            for symbol, position in positions.items():
                position_size = float(position.get('size', 0))
                
                if position_size == 0:
                    # No active position, clean up any TP/SL orders
                    self._clean_up_tpsl_orders(symbol)
                    continue
                    
                # Check trailing stops if enabled
                if self.config.get('enable_trailing_stop', False):
                    self._update_trailing_stop(symbol, position)
        
        except Exception as e:
            logger.exception(f"Error in TPSL Manager: {str(e)}")
    
    def place_tpsl_orders(self, symbol: str, position: Dict[str, Any], atr_value: float) -> bool:
        """
        Place TP/SL orders for a position after entry is filled.
        
        Args:
            symbol: Trading symbol
            position: Position details
            atr_value: Current ATR value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Clean up any existing TP/SL orders
            self._clean_up_tpsl_orders(symbol)
            
            position_size = float(position.get('size', 0))
            entry_price = float(position.get('entry_price', 0))
            
            if position_size == 0 or entry_price == 0:
                logger.warning(f"Invalid position data for {symbol}")
                return False
            
            # Determine position side
            is_long = position_size > 0
            
            # Get configuration parameters
            sl_multiplier = self.config.get('stop_loss_multiplier', 2.0)
            tp_multiplier = self.config.get('take_profit_multiplier', 4.0)
            
            # Calculate TP/SL levels
            if is_long:
                sl_price = entry_price - (atr_value * sl_multiplier)
                tp_price = entry_price + (atr_value * tp_multiplier)
            else:  # Short
                sl_price = entry_price + (atr_value * sl_multiplier)
                tp_price = entry_price - (atr_value * tp_multiplier)
            
            # Round prices to appropriate precision
            sl_price = self._round_price(symbol, sl_price)
            tp_price = self._round_price(symbol, tp_price)
            
            logger.info(f"Setting TP/SL for {symbol}: TP={tp_price}, SL={sl_price}")
            
            # Place SL order (stop-market)
            sl_side = "Sell" if is_long else "Buy"
            sl_result = self.client.place_order(
                symbol=symbol,
                side=sl_side,
                order_type="Stop",
                qty=abs(position_size),
                stop_px=sl_price,  # Trigger price
                price=sl_price,    # Execution price
                time_in_force="GoodTillCancel",
                reduce_only=True,
                close_on_trigger=True
            )
            
            if not sl_result or not sl_result.get('success', False):
                logger.error(f"Failed to place SL order for {symbol}: {sl_result}")
                return False
            
            sl_order_id = sl_result['result']['order_id']
            self.sl_orders[symbol] = sl_order_id
            
            # Place TP order (limit)
            tp_side = "Sell" if is_long else "Buy"
            tp_result = self.client.place_order(
                symbol=symbol,
                side=tp_side,
                order_type="Limit",
                qty=abs(position_size),
                price=tp_price,
                time_in_force="GoodTillCancel",
                reduce_only=True,
                close_on_trigger=True
            )
            
            if not tp_result or not tp_result.get('success', False):
                logger.error(f"Failed to place TP order for {symbol}: {tp_result}")
                # Cancel SL order if TP fails
                self.client.cancel_order(symbol, sl_order_id)
                return False
            
            tp_order_id = tp_result['result']['order_id']
            self.tp_orders[symbol] = tp_order_id
            
            # Initialize trailing stop if enabled
            if self.config.get('enable_trailing_stop', False):
                self._initialize_trailing_stop(symbol, position, atr_value, tp_price)
            
            logger.info(f"TP/SL orders placed for {symbol}: TP={tp_price}, SL={sl_price}")
            return True
            
        except Exception as e:
            logger.exception(f"Error placing TP/SL orders for {symbol}: {str(e)}")
            return False
    
    def _clean_up_tpsl_orders(self, symbol: str) -> bool:
        """
        Cancel existing TP/SL orders for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if successful, False otherwise
        """
        success = True
        
        # Cancel TP order
        if symbol in self.tp_orders:
            tp_order_id = self.tp_orders[symbol]
            try:
                result = self.client.cancel_order(symbol, tp_order_id)
                if not result or not result.get('success', False):
                    logger.warning(f"Failed to cancel TP order {tp_order_id} for {symbol}")
                    success = False
                else:
                    logger.info(f"Canceled TP order {tp_order_id} for {symbol}")
            except Exception as e:
                logger.exception(f"Error canceling TP order {tp_order_id}: {str(e)}")
                success = False
            
            # Remove from tracking
            del self.tp_orders[symbol]
        
        # Cancel SL order
        if symbol in self.sl_orders:
            sl_order_id = self.sl_orders[symbol]
            try:
                result = self.client.cancel_order(symbol, sl_order_id)
                if not result or not result.get('success', False):
                    logger.warning(f"Failed to cancel SL order {sl_order_id} for {symbol}")
                    success = False
                else:
                    logger.info(f"Canceled SL order {sl_order_id} for {symbol}")
            except Exception as e:
                logger.exception(f"Error canceling SL order {sl_order_id}: {str(e)}")
                success = False
            
            # Remove from tracking
            del self.sl_orders[symbol]
        
        # Clear trailing stop state
        if symbol in self.trailing_stops:
            del self.trailing_stops[symbol]
        
        return success
    
    def _initialize_trailing_stop(self, symbol: str, position: Dict[str, Any], 
                                 atr_value: float, tp_price: float):
        """
        Initialize trailing stop tracking for a position.
        
        Args:
            symbol: Trading symbol
            position: Position details
            atr_value: Current ATR value
            tp_price: Take profit price
        """
        position_size = float(position.get('size', 0))
        entry_price = float(position.get('entry_price', 0))
        
        # Determine position side
        is_long = position_size > 0
        
        # Get trail multiplier
        trail_atr_mult = self.config.get('trail_atr_mult', 2.0)
        
        # Calculate initial stop level
        if is_long:
            initial_stop = entry_price - (atr_value * trail_atr_mult)
        else:  # Short
            initial_stop = entry_price + (atr_value * trail_atr_mult)
        
        # Calculate activation level (halfway to TP)
        if is_long:
            activation_level = entry_price + ((tp_price - entry_price) * 0.5)
        else:  # Short
            activation_level = entry_price - ((entry_price - tp_price) * 0.5)
        
        # Store trailing stop state
        self.trailing_stops[symbol] = {
            'is_long': is_long,
            'entry_price': entry_price,
            'tp_price': tp_price,
            'current_stop': initial_stop,
            'atr_value': atr_value,
            'trail_multiplier': trail_atr_mult,
            'activation_level': activation_level,
            'activated': False,
            'highest_price': entry_price,  # For long positions
            'lowest_price': entry_price    # For short positions
        }
        
        logger.info(f"Initialized trailing stop for {symbol}: initial={initial_stop}, activate_at={activation_level}")
    
    def _update_trailing_stop(self, symbol: str, position: Dict[str, Any]):
        """
        Update trailing stop based on current market price.
        
        Args:
            symbol: Trading symbol
            position: Position details
        """
        if symbol not in self.trailing_stops:
            return
        
        # Get trailing stop state
        ts = self.trailing_stops[symbol]
        
        # Skip if not yet activated
        if not ts['activated']:
            # Get current market price
            current_price = self._get_market_price(symbol)
            if not current_price:
                return
            
            # Check if activation level reached
            if (ts['is_long'] and current_price >= ts['activation_level']) or \
               (not ts['is_long'] and current_price <= ts['activation_level']):
                ts['activated'] = True
                logger.info(f"Trailing stop activated for {symbol} at {current_price}")
            else:
                # Not yet activated
                return
        
        # Update trailing stop if activated
        current_price = self._get_market_price(symbol)
        if not current_price:
            return
        
        # Update highest/lowest seen prices
        if ts['is_long'] and current_price > ts['highest_price']:
            ts['highest_price'] = current_price
            
            # Calculate new stop level (never move stop down)
            new_stop = current_price - (ts['atr_value'] * ts['trail_multiplier'])
            if new_stop > ts['current_stop']:
                old_stop = ts['current_stop']
                ts['current_stop'] = new_stop
                
                # Update stop loss order
                self._update_stop_loss_order(symbol, new_stop)
                logger.info(f"Trailing stop moved up for {symbol}: {old_stop} -> {new_stop}")
        
        elif not ts['is_long'] and current_price < ts['lowest_price']:
            ts['lowest_price'] = current_price
            
            # Calculate new stop level (never move stop up)
            new_stop = current_price + (ts['atr_value'] * ts['trail_multiplier'])
            if new_stop < ts['current_stop']:
                old_stop = ts['current_stop']
                ts['current_stop'] = new_stop
                
                # Update stop loss order
                self._update_stop_loss_order(symbol, new_stop)
                logger.info(f"Trailing stop moved down for {symbol}: {old_stop} -> {new_stop}")
    
    def _update_stop_loss_order(self, symbol: str, new_stop: float):
        """
        Update stop loss order with new stop price.
        
        Args:
            symbol: Trading symbol
            new_stop: New stop loss price
        """
        if symbol not in self.sl_orders:
            logger.warning(f"No SL order found for {symbol}")
            return
        
        # Get existing SL order ID
        sl_order_id = self.sl_orders[symbol]
        
        # Get position details
        position = self.order_manager.get_position(symbol)
        if not position:
            logger.warning(f"No position found for {symbol}")
            return
        
        position_size = float(position.get('size', 0))
        is_long = position_size > 0
        
        # Round price to appropriate precision
        new_stop = self._round_price(symbol, new_stop)
        
        try:
            # Cancel existing SL order
            cancel_result = self.client.cancel_order(symbol, sl_order_id)
            if not cancel_result or not cancel_result.get('success', False):
                logger.warning(f"Failed to cancel SL order {sl_order_id} for {symbol}")
                return
            
            # Place new SL order
            sl_side = "Sell" if is_long else "Buy"
            sl_result = self.client.place_order(
                symbol=symbol,
                side=sl_side,
                order_type="Stop",
                qty=abs(position_size),
                stop_px=new_stop,  # Trigger price
                price=new_stop,    # Execution price
                time_in_force="GoodTillCancel",
                reduce_only=True,
                close_on_trigger=True
            )
            
            if not sl_result or not sl_result.get('success', False):
                logger.error(f"Failed to place new SL order for {symbol}: {sl_result}")
                return
            
            # Update tracking
            new_sl_order_id = sl_result['result']['order_id']
            self.sl_orders[symbol] = new_sl_order_id
            
            logger.info(f"Updated SL order for {symbol} to {new_stop}")
            
        except Exception as e:
            logger.exception(f"Error updating SL order for {symbol}: {str(e)}")
    
    def handle_tp_fill(self, symbol: str, order_id: str):
        """
        Handle take profit order fill.
        
        Args:
            symbol: Trading symbol
            order_id: Filled order ID
        """
        logger.info(f"TP order filled for {symbol}: {order_id}")
        
        # Verify this is our TP order
        if symbol not in self.tp_orders or self.tp_orders[symbol] != order_id:
            logger.warning(f"Filled order {order_id} not found in TP tracking for {symbol}")
            return
        
        # Cancel corresponding SL order (OCO behavior)
        if symbol in self.sl_orders:
            sl_order_id = self.sl_orders[symbol]
            try:
                self.client.cancel_order(symbol, sl_order_id)
                logger.info(f"Canceled SL order {sl_order_id} after TP fill for {symbol}")
            except Exception as e:
                logger.exception(f"Error canceling SL order after TP fill: {str(e)}")
        
        # Clean up tracking
        self._clean_up_tpsl_orders(symbol)
    
    def handle_sl_fill(self, symbol: str, order_id: str):
        """
        Handle stop loss order fill.
        
        Args:
            symbol: Trading symbol
            order_id: Filled order ID
        """
        logger.info(f"SL order filled for {symbol}: {order_id}")
        
        # Verify this is our SL order
        if symbol not in self.sl_orders or self.sl_orders[symbol] != order_id:
            logger.warning(f"Filled order {order_id} not found in SL tracking for {symbol}")
            return
        
        # Cancel corresponding TP order (OCO behavior)
        if symbol in self.tp_orders:
            tp_order_id = self.tp_orders[symbol]
            try:
                self.client.cancel_order(symbol, tp_order_id)
                logger.info(f"Canceled TP order {tp_order_id} after SL fill for {symbol}")
            except Exception as e:
                logger.exception(f"Error canceling TP order after SL fill: {str(e)}")
        
        # Clean up tracking
        self._clean_up_tpsl_orders(symbol)
    
    def handle_position_close(self, symbol: str):
        """
        Handle position close (for any reason).
        
        Args:
            symbol: Trading symbol
        """
        logger.info(f"Position closed for {symbol}, cleaning up TP/SL orders")
        self._clean_up_tpsl_orders(symbol)
    
    def _get_market_price(self, symbol: str) -> Optional[float]:
        """
        Get current market price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current market price or None if unavailable
        """
        try:
            ticker = self.client.get_ticker(symbol)
            if ticker and ticker.get('success', False):
                return float(ticker['result']['last_price'])
            return None
        except Exception as e:
            logger.exception(f"Error getting market price for {symbol}: {str(e)}")
            return None
    
    def _round_price(self, symbol: str, price: float) -> float:
        """
        Round price to appropriate precision for the symbol.
        
        Args:
            symbol: Trading symbol
            price: Price to round
            
        Returns:
            Rounded price
        """
        # This would ideally use exchange info to get proper precision
        # For now, use a simple fixed precision
        return round(price, 2)