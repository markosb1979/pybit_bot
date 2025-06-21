"""
TP/SL Manager - Monitors and manages take profit and stop loss orders
"""

import time
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

from pybit_bot.utils.logger import Logger


class TPSLManager:
    """
    Take Profit / Stop Loss Manager
    
    Monitors active positions and manages TP/SL order execution
    """
    
    def __init__(self, config: Dict, order_manager=None, logger=None, data_manager=None):
        """
        Initialize the TPSL manager
        
        Args:
            config: TPSL configuration settings
            order_manager: OrderManager instance
            logger: Optional logger instance
            data_manager: Optional DataManager instance
        """
        self.config = config
        self.order_manager = order_manager
        self.logger = logger or Logger("TPSLManager")
        self.data_manager = data_manager
        
        # Get configuration
        tpsl_config = config.get('tpsl_manager', {})
        self.check_interval_ms = tpsl_config.get('check_interval_ms', 100)
        self.default_stop_type = tpsl_config.get('default_stop_type', "TRAILING")
        
        # Active positions being monitored for TP/SL
        self.active_positions = {}
        
        # Stopped flag for clean shutdown
        self._stopped = False
        
        # Track last synchronization time
        self.last_sync_time = 0
        self.sync_interval = 5  # seconds
        
        self.logger.info("TPSLManager initialized")
    
    def add_position(self, symbol: str, side: str, entry_price: float, quantity: float, 
                    timestamp: int, position_id: str, sl_price: float, tp_price: float, 
                    stop_type: str = None):
        """
        Add a position to be monitored for TP/SL
        
        Args:
            symbol: Trading symbol
            side: "LONG" or "SHORT"
            entry_price: Entry price
            quantity: Position quantity
            timestamp: Entry timestamp
            position_id: Unique position identifier
            sl_price: Stop loss price
            tp_price: Take profit price
            stop_type: Stop type ("FIXED" or "TRAILING")
        """
        stop_type = stop_type or self.default_stop_type
        
        # Create position tracking object
        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'timestamp': timestamp,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'position_id': position_id,
            'stop_type': stop_type,
            'trail_active': False,
            'trail_price': None,
            'max_price': entry_price if side == "LONG" else None,
            'min_price': entry_price if side == "SHORT" else None
        }
        
        # Store in active positions
        self.active_positions[position_id] = position
        
        self.logger.info(f"Added position to TPSL manager: {position_id} ({symbol} {side})")
    
    def remove_position(self, position_id: str):
        """
        Remove a position from monitoring
        
        Args:
            position_id: Position ID to remove
        """
        if position_id in self.active_positions:
            position = self.active_positions[position_id]
            self.logger.info(f"Removing position from TPSL manager: {position_id} ({position['symbol']} {position['side']})")
            del self.active_positions[position_id]
    
    def update_position(self, position_id: str, **kwargs):
        """
        Update position parameters
        
        Args:
            position_id: Position ID to update
            **kwargs: Parameters to update
        """
        if position_id in self.active_positions:
            for key, value in kwargs.items():
                if key in self.active_positions[position_id]:
                    self.active_positions[position_id][key] = value
            
            self.logger.info(f"Updated position: {position_id} with {kwargs}")
    
    async def synchronize_positions(self):
        """
        Synchronize internal position state with OrderManager
        """
        if not self.order_manager:
            return
        
        try:
            current_time = time.time()
            
            # Only synchronize if enough time has passed
            if current_time - self.last_sync_time < self.sync_interval:
                return
                
            # Get current positions from OrderManager
            positions = await self.order_manager.get_positions()
            
            # Map positions by symbol
            position_map = {}
            for position in positions:
                symbol = position.get('symbol')
                if symbol and float(position.get('size', 0)) != 0:
                    position_map[symbol] = position
            
            # Check which positions are no longer active
            to_remove = []
            for position_id, position in self.active_positions.items():
                symbol = position['symbol']
                
                # If symbol no longer has a position or position size is zero
                if symbol not in position_map:
                    self.logger.info(f"Position closed for {symbol}, removing from active trades")
                    to_remove.append(position_id)
            
            # Remove closed positions
            for position_id in to_remove:
                self.remove_position(position_id)
            
            # Update last sync time
            self.last_sync_time = current_time
            
        except Exception as e:
            self.logger.error(f"Error synchronizing positions: {str(e)}")
    
    async def check_positions(self):
        """
        Check all active positions for TP/SL conditions
        """
        # Synchronize with OrderManager first
        await self.synchronize_positions()
        
        # If we have positions to monitor
        if self.active_positions:
            self.logger.info(f"Checking {len(self.active_positions)} pending TP/SL orders")
            
            # Process each position
            for position_id, position in list(self.active_positions.items()):
                try:
                    await self._check_position(position)
                except Exception as e:
                    self.logger.error(f"Error checking position {position_id}: {str(e)}")
    
    async def _check_position(self, position: Dict):
        """
        Check a single position for TP/SL conditions
        
        Args:
            position: Position dictionary
        """
        if not self.data_manager:
            return
            
        symbol = position['symbol']
        side = position['side']
        position_id = position['position_id']
        entry_price = position['entry_price']
        sl_price = position['sl_price']
        tp_price = position['tp_price']
        
        # Get current price
        current_price = await self.data_manager.get_latest_price(symbol)
        
        # Skip if price is invalid
        if current_price <= 0:
            return
            
        # For LONG positions
        if side == "LONG":
            # Update max price for trailing stops
            if position['stop_type'] == "TRAILING" and (position['max_price'] is None or current_price > position['max_price']):
                position['max_price'] = current_price
                
                # Check if trailing stop should be activated
                trail_activation = self.config.get('risk_management', {}).get('trail_activation_pct', 0.5)
                price_movement = (current_price - entry_price) / entry_price
                
                if price_movement >= trail_activation and not position['trail_active']:
                    position['trail_active'] = True
                    position['trail_price'] = current_price * (1 - trail_activation / 2)
                    self.logger.info(f"Trailing stop activated for {symbol} LONG at {position['trail_price']}")
                
                # Update trailing stop if active
                if position['trail_active']:
                    # Calculate new trailing stop level
                    atr_mult = self.config.get('strategy', {}).get('strategy_b', {}).get('trail_atr_mult', 2.0)
                    trail_distance = (await self.data_manager.get_atr(symbol)) * atr_mult
                    new_trail_price = current_price - trail_distance
                    
                    # Only update if it would raise the stop
                    if new_trail_price > position['trail_price']:
                        position['trail_price'] = new_trail_price
                        self.logger.info(f"Updated trailing stop for {symbol} LONG to {new_trail_price}")
                        
                        # Update stop loss in exchange
                        if self.order_manager:
                            await self.order_manager.set_position_tpsl(
                                symbol=symbol,
                                position_idx=0,
                                sl_price=str(new_trail_price)
                            )
            
            # Check for TP hit
            if current_price >= tp_price:
                self.logger.info(f"Take profit hit for {symbol} LONG at {current_price}")
                
                # Close position
                if self.order_manager:
                    await self.order_manager.close_position(symbol)
                    self.remove_position(position_id)
                    return
            
            # Check for SL hit (either fixed or trailing)
            sl_check_price = position['trail_price'] if position['trail_active'] else sl_price
            if current_price <= sl_check_price:
                self.logger.info(f"Stop loss hit for {symbol} LONG at {current_price}")
                
                # Close position
                if self.order_manager:
                    await self.order_manager.close_position(symbol)
                    self.remove_position(position_id)
                    return
        
        # For SHORT positions
        elif side == "SHORT":
            # Update min price for trailing stops
            if position['stop_type'] == "TRAILING" and (position['min_price'] is None or current_price < position['min_price']):
                position['min_price'] = current_price
                
                # Check if trailing stop should be activated
                trail_activation = self.config.get('risk_management', {}).get('trail_activation_pct', 0.5)
                price_movement = (entry_price - current_price) / entry_price
                
                if price_movement >= trail_activation and not position['trail_active']:
                    position['trail_active'] = True
                    position['trail_price'] = current_price * (1 + trail_activation / 2)
                    self.logger.info(f"Trailing stop activated for {symbol} SHORT at {position['trail_price']}")
                
                # Update trailing stop if active
                if position['trail_active']:
                    # Calculate new trailing stop level
                    atr_mult = self.config.get('strategy', {}).get('strategy_b', {}).get('trail_atr_mult', 2.0)
                    trail_distance = (await self.data_manager.get_atr(symbol)) * atr_mult
                    new_trail_price = current_price + trail_distance
                    
                    # Only update if it would lower the stop
                    if new_trail_price < position['trail_price']:
                        position['trail_price'] = new_trail_price
                        self.logger.info(f"Updated trailing stop for {symbol} SHORT to {new_trail_price}")
                        
                        # Update stop loss in exchange
                        if self.order_manager:
                            await self.order_manager.set_position_tpsl(
                                symbol=symbol,
                                position_idx=0,
                                sl_price=str(new_trail_price)
                            )
            
            # Check for TP hit
            if current_price <= tp_price:
                self.logger.info(f"Take profit hit for {symbol} SHORT at {current_price}")
                
                # Close position
                if self.order_manager:
                    await self.order_manager.close_position(symbol)
                    self.remove_position(position_id)
                    return
            
            # Check for SL hit (either fixed or trailing)
            sl_check_price = position['trail_price'] if position['trail_active'] else sl_price
            if current_price >= sl_check_price:
                self.logger.info(f"Stop loss hit for {symbol} SHORT at {current_price}")
                
                # Close position
                if self.order_manager:
                    await self.order_manager.close_position(symbol)
                    self.remove_position(position_id)
                    return