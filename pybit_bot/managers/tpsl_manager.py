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
        
        # Max retries and backoff settings
        self.max_retries = 3
        self.retry_delay_base = 1.0  # Base delay in seconds
        
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
            'min_price': entry_price if side == "SHORT" else None,
            'last_checked': time.time()
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
            
            # Update last checked timestamp
            self.active_positions[position_id]['last_checked'] = time.time()
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
            
            # Try fallback approach for critical symbols
            try:
                # Get symbols from active positions
                symbols = {position['symbol'] for position_id, position in self.active_positions.items()}
                
                # Check each symbol directly
                for symbol in symbols:
                    try:
                        position_exists = await self.order_manager.position_exists(symbol)
                        if not position_exists:
                            # Find and remove positions for this symbol
                            to_remove = [pid for pid, pos in self.active_positions.items() if pos['symbol'] == symbol]
                            for pid in to_remove:
                                self.logger.info(f"Position closed for {symbol} (fallback check), removing {pid}")
                                self.remove_position(pid)
                    except Exception as symbol_error:
                        self.logger.error(f"Error checking symbol {symbol} in fallback: {str(symbol_error)}")
            except Exception as fallback_error:
                self.logger.error(f"Position fallback check failed: {str(fallback_error)}")
    
    async def check_positions(self):
        """
        Check all active positions for TP/SL conditions
        """
        # Synchronize with OrderManager first
        await self.synchronize_positions()
        
        # If we have positions to monitor
        position_count = len(self.active_positions)
        if position_count > 0:
            self.logger.info(f"Checking {position_count} pending TP/SL orders")
            
            # Process each position
            for position_id, position in list(self.active_positions.items()):
                try:
                    # Rate limit position checks
                    current_time = time.time()
                    last_checked = position.get('last_checked', 0)
                    
                    # Only check if enough time has passed (at least 1 second)
                    if current_time - last_checked >= 1.0:
                        await self._check_position(position)
                        # Update last checked timestamp
                        position['last_checked'] = current_time
                except Exception as e:
                    self.logger.error(f"Error checking position {position_id}: {str(e)}")
                    
                    # Try to verify if the position still exists
                    try:
                        symbol = position.get('symbol')
                        if symbol:
                            position_exists = await self.order_manager.position_exists(symbol)
                            if not position_exists:
                                self.logger.info(f"Position {position_id} no longer exists, removing from tracking")
                                self.remove_position(position_id)
                    except Exception as verify_error:
                        self.logger.error(f"Error verifying position existence: {str(verify_error)}")
    
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
        
        # Verify position still exists
        try:
            position_exists = await self.order_manager.position_exists(symbol)
            if not position_exists:
                self.logger.info(f"Position {position_id} for {symbol} no longer exists, removing from tracking")
                self.remove_position(position_id)
                return
        except Exception as e:
            self.logger.error(f"Error verifying position existence for {symbol}: {str(e)}")
            # Continue with check since the error might be temporary
        
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
                            await self._retry_set_tpsl(
                                symbol=symbol,
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
                            await self._retry_set_tpsl(
                                symbol=symbol,
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
    
    async def _retry_set_tpsl(self, symbol: str, tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Set TP/SL with retry logic for reliability
        
        Args:
            symbol: Trading symbol
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with TP/SL setting result
        """
        for attempt in range(self.max_retries):
            try:
                # Try to set TP/SL
                result = await self.order_manager.set_position_tpsl(
                    symbol=symbol,
                    position_idx=0,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
                
                # Check for success
                if "error" not in result:
                    return result
                
                # Check for position no longer exists errors
                error_msg = str(result.get("error", "")).lower()
                if "no active position" in error_msg or "zero position" in error_msg:
                    self.logger.warning(f"Position no longer exists for {symbol} when setting TP/SL")
                    # Find and remove positions for this symbol
                    to_remove = [pid for pid, pos in self.active_positions.items() if pos['symbol'] == symbol]
                    for pid in to_remove:
                        self.logger.info(f"Removing stale position {pid} from tracking")
                        self.remove_position(pid)
                    return {"status": "position_closed"}
                
                # For other errors, retry with backoff
                wait_time = self.retry_delay_base * (2 ** attempt)
                self.logger.warning(f"Retrying TP/SL set after error (attempt {attempt+1}/{self.max_retries}): {result.get('error')}, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                # For exceptions, also retry with backoff
                wait_time = self.retry_delay_base * (2 ** attempt)
                self.logger.error(f"Exception setting TP/SL (attempt {attempt+1}/{self.max_retries}): {str(e)}, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
                
                # On last attempt, check if position still exists
                if attempt == self.max_retries - 1:
                    try:
                        position_exists = await self.order_manager.position_exists(symbol)
                        if not position_exists:
                            # Find and remove positions for this symbol
                            to_remove = [pid for pid, pos in self.active_positions.items() if pos['symbol'] == symbol]
                            for pid in to_remove:
                                self.logger.info(f"Removing stale position {pid} from tracking")
                                self.remove_position(pid)
                    except Exception as verify_error:
                        self.logger.error(f"Error verifying position existence: {str(verify_error)}")
        
        # If we get here, all retries failed
        return {"status": "error", "reason": "max_retries_exceeded"}