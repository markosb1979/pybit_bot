"""
TP/SL Manager - Manage Take Profit and Stop Loss orders

This module provides specialized functionality for setting and managing
take profit and stop loss orders, ensuring positions have proper risk management.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal

from ..utils.logger import Logger


class TPSLManager:
    """
    Take Profit / Stop Loss manager for trading positions
    
    Handles TP/SL logic, dynamic adjustments, and trailing stops
    """
    
    def __init__(self, order_client, data_manager, config, logger=None):
        """
        Initialize with order client, data manager, and config
        
        Args:
            order_client: OrderManagerClient instance
            data_manager: DataManager instance
            config: Configuration dictionary
            logger: Optional Logger instance
        """
        self.logger = logger or Logger("TPSLManager")
        self.logger.debug(f"→ __init__(order_client={order_client}, data_manager={data_manager}, config_id={id(config)}, logger={logger})")
        
        self.order_client = order_client
        self.data_manager = data_manager
        self.config = config
        
        # Internal state
        self.pending_orders = {}
        self.active_tpsl = {}
        
        # Configuration
        self.default_tp_percent = self.config.get('execution', {}).get('take_profit', {}).get('default_percent', 0.03)
        self.default_sl_percent = self.config.get('execution', {}).get('stop_loss', {}).get('default_percent', 0.02)
        
        # Trailing stop configuration
        self.use_trailing_stop = self.config.get('execution', {}).get('trailing_stop', {}).get('enabled', False)
        self.trailing_stop_activation = self.config.get('execution', {}).get('trailing_stop', {}).get('activation_percent', 0.01)
        self.trailing_stop_callback = self.config.get('execution', {}).get('trailing_stop', {}).get('callback_percent', 0.005)
        
        # Order retry settings
        self.retry_delay = 1.0
        self.max_retries = 3
        
        self.logger.info(f"TPSLManager initialized with TP: {self.default_tp_percent*100}%, SL: {self.default_sl_percent*100}%")
        self.logger.debug(f"← __init__ completed")
    
    async def apply_tpsl_for_position(self, symbol: str, position: Dict) -> bool:
        """
        Apply take profit and stop loss for a position
        
        Args:
            symbol: Trading symbol
            position: Position dictionary from API
            
        Returns:
            True if TP/SL applied successfully, False otherwise
        """
        self.logger.debug(f"→ apply_tpsl_for_position(symbol={symbol}, position={position})")
        
        try:
            # Check if position exists and has size
            position_size = float(position.get('size', '0'))
            if position_size == 0:
                self.logger.warning(f"Position for {symbol} has zero size, skipping TP/SL")
                self.logger.debug(f"← apply_tpsl_for_position returned False (zero size)")
                return False
                
            # Get position details
            entry_price = float(position.get('entryPrice', '0'))
            position_side = position.get('side', '')
            position_idx = int(position.get('positionIdx', 0))
            
            self.logger.info(f"Setting TP/SL for {symbol} position: {position_side} {position_size} at {entry_price}")
            
            # Calculate TP/SL prices
            tp_price, sl_price = await self._calculate_tpsl_prices(
                symbol, 
                entry_price, 
                position_side
            )
            
            self.logger.info(f"Calculated TP: {tp_price}, SL: {sl_price} for {symbol}")
            
            # Set TP/SL for position
            for attempt in range(self.max_retries):
                try:
                    result = self.order_client.set_position_tpsl(
                        symbol=symbol,
                        position_idx=position_idx,
                        tp_price=str(tp_price) if tp_price else None,
                        sl_price=str(sl_price) if sl_price else None
                    )
                    
                    # Check for errors
                    if result.get('status') == 'error':
                        self.logger.error(f"Error setting TP/SL for {symbol}: {result.get('reason', 'Unknown error')}")
                        if attempt < self.max_retries - 1:
                            self.logger.info(f"Retrying TP/SL setup for {symbol} (attempt {attempt+2}/{self.max_retries})")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        else:
                            self.logger.error(f"Failed to set TP/SL for {symbol} after {self.max_retries} attempts")
                            self.logger.debug(f"← apply_tpsl_for_position returned False (max retries exceeded)")
                            return False
                    
                    # TP/SL successfully set
                    self.logger.info(f"TP/SL set successfully for {symbol}")
                    
                    # Save in active TP/SL tracking
                    self.active_tpsl[symbol] = {
                        'entry_price': entry_price,
                        'position_side': position_side,
                        'tp_price': tp_price,
                        'sl_price': sl_price,
                        'timestamp': time.time()
                    }
                    
                    self.logger.debug(f"← apply_tpsl_for_position returned True (success)")
                    return True
                    
                except Exception as e:
                    self.logger.error(f"Exception setting TP/SL for {symbol} (attempt {attempt+1}/{self.max_retries}): {str(e)}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                    else:
                        self.logger.debug(f"← apply_tpsl_for_position returned False (exception)")
                        return False
                    
        except Exception as e:
            self.logger.error(f"Error applying TP/SL for {symbol}: {str(e)}")
            self.logger.debug(f"← apply_tpsl_for_position returned False (error)")
            return False
    
    async def _calculate_tpsl_prices(self, symbol: str, entry_price: float, position_side: str) -> tuple:
        """
        Calculate TP and SL prices based on configuration
        
        Args:
            symbol: Trading symbol
            entry_price: Position entry price
            position_side: Position side (Buy/Sell)
            
        Returns:
            Tuple of (tp_price, sl_price)
        """
        self.logger.debug(f"→ _calculate_tpsl_prices(symbol={symbol}, entry_price={entry_price}, position_side={position_side})")
        
        try:
            # Get TP/SL configuration
            execution_config = self.config.get('execution', {})
            
            # Determine TP/SL mode
            tp_mode = execution_config.get('take_profit', {}).get('mode', 'fixed')
            sl_mode = execution_config.get('stop_loss', {}).get('mode', 'fixed')
            
            # Initialize TP/SL prices
            tp_price = None
            sl_price = None
            
            # Calculate TP based on mode
            if tp_mode == 'fixed':
                # Fixed percentage TP
                tp_percent = execution_config.get('take_profit', {}).get('percent', self.default_tp_percent)
                
                if position_side == 'Buy':
                    tp_price = entry_price * (1 + tp_percent)
                else:
                    tp_price = entry_price * (1 - tp_percent)
                    
                self.logger.debug(f"Fixed TP for {symbol}: {tp_price} ({tp_percent*100}% from entry)")
                
            elif tp_mode == 'atr':
                # ATR-based TP
                atr_multiplier = execution_config.get('take_profit', {}).get('atr_multiplier', 3)
                timeframe = execution_config.get('take_profit', {}).get('atr_timeframe', '1h')
                
                # Get ATR value
                atr = await self.data_manager.get_atr(symbol, timeframe)
                
                if position_side == 'Buy':
                    tp_price = entry_price + (atr * atr_multiplier)
                else:
                    tp_price = entry_price - (atr * atr_multiplier)
                    
                self.logger.debug(f"ATR-based TP for {symbol}: {tp_price} (ATR: {atr}, multiplier: {atr_multiplier})")
            
            # Calculate SL based on mode
            if sl_mode == 'fixed':
                # Fixed percentage SL
                sl_percent = execution_config.get('stop_loss', {}).get('percent', self.default_sl_percent)
                
                if position_side == 'Buy':
                    sl_price = entry_price * (1 - sl_percent)
                else:
                    sl_price = entry_price * (1 + sl_percent)
                    
                self.logger.debug(f"Fixed SL for {symbol}: {sl_price} ({sl_percent*100}% from entry)")
                
            elif sl_mode == 'atr':
                # ATR-based SL
                atr_multiplier = execution_config.get('stop_loss', {}).get('atr_multiplier', 2)
                timeframe = execution_config.get('stop_loss', {}).get('atr_timeframe', '1h')
                
                # Get ATR value
                atr = await self.data_manager.get_atr(symbol, timeframe)
                
                if position_side == 'Buy':
                    sl_price = entry_price - (atr * atr_multiplier)
                else:
                    sl_price = entry_price + (atr * atr_multiplier)
                    
                self.logger.debug(f"ATR-based SL for {symbol}: {sl_price} (ATR: {atr}, multiplier: {atr_multiplier})")
            
            # Round prices to appropriate precision
            if tp_price:
                tp_price = self._round_price_to_tick(symbol, tp_price)
            if sl_price:
                sl_price = self._round_price_to_tick(symbol, sl_price)
            
            self.logger.debug(f"← _calculate_tpsl_prices returned tp_price={tp_price}, sl_price={sl_price}")
            return tp_price, sl_price
            
        except Exception as e:
            self.logger.error(f"Error calculating TP/SL prices for {symbol}: {str(e)}")
            # Return default values
            tp_percent = self.default_tp_percent
            sl_percent = self.default_sl_percent
            
            if position_side == 'Buy':
                tp_price = entry_price * (1 + tp_percent)
                sl_price = entry_price * (1 - sl_percent)
            else:
                tp_price = entry_price * (1 - tp_percent)
                sl_price = entry_price * (1 + sl_percent)
                
            self.logger.debug(f"← _calculate_tpsl_prices returned default values: tp_price={tp_price}, sl_price={sl_price}")
            return tp_price, sl_price
    
    def _round_price_to_tick(self, symbol: str, price: float) -> float:
        """
        Round price to valid tick size for symbol
        
        Args:
            symbol: Trading symbol
            price: Raw price
            
        Returns:
            Price rounded to valid tick size
        """
        self.logger.debug(f"→ _round_price_to_tick(symbol={symbol}, price={price})")
        
        try:
            # Get tick size for the symbol
            tick_size = self._get_tick_size(symbol)
            
            if tick_size:
                # Round to nearest tick
                rounded_price = round(price / tick_size) * tick_size
                self.logger.debug(f"← _round_price_to_tick returned {rounded_price} (tick_size={tick_size})")
                return rounded_price
            else:
                # Fallback: round to 2 decimal places
                rounded_price = round(price, 2)
                self.logger.debug(f"← _round_price_to_tick returned {rounded_price} (default rounding)")
                return rounded_price
        except Exception as e:
            self.logger.error(f"Error rounding price for {symbol}: {str(e)}")
            # Fallback: round to 2 decimal places
            rounded_price = round(price, 2)
            self.logger.debug(f"← _round_price_to_tick returned {rounded_price} (error fallback)")
            return rounded_price
    
    def _get_tick_size(self, symbol: str) -> float:
        """
        Get tick size for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Tick size as float
        """
        self.logger.debug(f"→ _get_tick_size(symbol={symbol})")
        
        try:
            # Try to get from order client
            if hasattr(self.order_client, 'get_instrument_info'):
                instrument_info = self.order_client.get_instrument_info(symbol)
                if instrument_info:
                    price_filter = instrument_info.get('priceFilter', {})
                    tick_size = float(price_filter.get('tickSize', 0.01))
                    self.logger.debug(f"← _get_tick_size returned {tick_size} from instrument info")
                    return tick_size
            
            # Fallback to common tick sizes
            if 'BTC' in symbol:
                tick_size = 0.5  # $0.50 for BTC
            elif 'ETH' in symbol:
                tick_size = 0.05  # $0.05 for ETH
            else:
                tick_size = 0.001  # Default for most coins
                
            self.logger.debug(f"← _get_tick_size returned fallback tick size: {tick_size}")
            return tick_size
            
        except Exception as e:
            self.logger.error(f"Error getting tick size for {symbol}: {str(e)}")
            # Default fallback
            default_tick_size = 0.01
            self.logger.debug(f"← _get_tick_size returned default tick size: {default_tick_size}")
            return default_tick_size
    
    async def check_and_update_trailing_stops(self, symbol: str, current_price: float) -> bool:
        """
        Check and update trailing stops if needed
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            True if trailing stop updated, False otherwise
        """
        self.logger.debug(f"→ check_and_update_trailing_stops(symbol={symbol}, current_price={current_price})")
        
        if not self.use_trailing_stop:
            self.logger.debug(f"← check_and_update_trailing_stops returned False (trailing stop disabled)")
            return False
            
        try:
            # Check if symbol has active TP/SL
            if symbol not in self.active_tpsl:
                self.logger.debug(f"← check_and_update_trailing_stops returned False (no active TP/SL)")
                return False
                
            tpsl_data = self.active_tpsl[symbol]
            position_side = tpsl_data.get('position_side')
            entry_price = tpsl_data.get('entry_price')
            sl_price = tpsl_data.get('sl_price')
            
            # Calculate price movement from entry
            if position_side == 'Buy':
                # For long positions
                price_movement = (current_price - entry_price) / entry_price
                
                # Check if price has moved enough to activate trailing stop
                if price_movement >= self.trailing_stop_activation:
                    # Calculate new stop loss level
                    new_sl = current_price * (1 - self.trailing_stop_callback)
                    
                    # Only update if new SL is higher than current SL
                    if not sl_price or new_sl > sl_price:
                        self.logger.info(f"Updating trailing stop for {symbol}: {sl_price} -> {new_sl}")
                        
                        # Get current position
                        positions = self.order_client.get_positions(symbol)
                        if positions and float(positions[0].get('size', '0')) > 0:
                            position = positions[0]
                            position_idx = int(position.get('positionIdx', 0))
                            
                            # Update stop loss
                            result = self.order_client.set_position_tpsl(
                                symbol=symbol,
                                position_idx=position_idx,
                                tp_price=str(tpsl_data.get('tp_price')) if tpsl_data.get('tp_price') else None,
                                sl_price=str(new_sl)
                            )
                            
                            # Update tracking data
                            if 'error' not in result:
                                self.active_tpsl[symbol]['sl_price'] = new_sl
                                self.logger.info(f"Trailing stop updated for {symbol} to {new_sl}")
                                self.logger.debug(f"← check_and_update_trailing_stops returned True (updated)")
                                return True
                        else:
                            self.logger.warning(f"Position not found for {symbol}, removing from TP/SL tracking")
                            if symbol in self.active_tpsl:
                                del self.active_tpsl[symbol]
            
            elif position_side == 'Sell':
                # For short positions
                price_movement = (entry_price - current_price) / entry_price
                
                # Check if price has moved enough to activate trailing stop
                if price_movement >= self.trailing_stop_activation:
                    # Calculate new stop loss level
                    new_sl = current_price * (1 + self.trailing_stop_callback)
                    
                    # Only update if new SL is lower than current SL
                    if not sl_price or new_sl < sl_price:
                        self.logger.info(f"Updating trailing stop for {symbol}: {sl_price} -> {new_sl}")
                        
                        # Get current position
                        positions = self.order_client.get_positions(symbol)
                        if positions and float(positions[0].get('size', '0')) > 0:
                            position = positions[0]
                            position_idx = int(position.get('positionIdx', 0))
                            
                            # Update stop loss
                            result = self.order_client.set_position_tpsl(
                                symbol=symbol,
                                position_idx=position_idx,
                                tp_price=str(tpsl_data.get('tp_price')) if tpsl_data.get('tp_price') else None,
                                sl_price=str(new_sl)
                            )
                            
                            # Update tracking data
                            if 'error' not in result:
                                self.active_tpsl[symbol]['sl_price'] = new_sl
                                self.logger.info(f"Trailing stop updated for {symbol} to {new_sl}")
                                self.logger.debug(f"← check_and_update_trailing_stops returned True (updated)")
                                return True
                        else:
                            self.logger.warning(f"Position not found for {symbol}, removing from TP/SL tracking")
                            if symbol in self.active_tpsl:
                                del self.active_tpsl[symbol]
            
            # No update needed
            self.logger.debug(f"← check_and_update_trailing_stops returned False (no update needed)")
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating trailing stop for {symbol}: {str(e)}")
            self.logger.debug(f"← check_and_update_trailing_stops returned False (error)")
            return False
    
    async def check_open_positions(self) -> Dict:
        """
        Check all open positions and ensure they have TP/SL
        
        Returns:
            Dictionary of positions updated with TP/SL
        """
        self.logger.debug(f"→ check_open_positions()")
        
        updated_positions = {}
        
        try:
            # Get all positions
            positions = self.order_client.get_positions()
            
            if not positions:
                self.logger.debug("No open positions found")
                self.logger.debug(f"← check_open_positions returned empty dict (no positions)")
                return {}
                
            # Process each position with size > 0
            for position in positions:
                symbol = position.get('symbol')
                size = float(position.get('size', '0'))
                
                if size > 0:
                    self.logger.debug(f"Found open position for {symbol}, size: {size}")
                    
                    # Check if the position has TP/SL
                    tp_active = float(position.get('takeProfit', '0')) > 0
                    sl_active = float(position.get('stopLoss', '0')) > 0
                    
                    # If either TP or SL is missing, apply them
                    if not (tp_active and sl_active):
                        self.logger.info(f"Position {symbol} missing TP/SL, applying now")
                        result = await self.apply_tpsl_for_position(symbol, position)
                        
                        if result:
                            updated_positions[symbol] = position
                            self.logger.info(f"Applied TP/SL for {symbol}")
                        else:
                            self.logger.warning(f"Failed to apply TP/SL for {symbol}")
                    else:
                        self.logger.debug(f"Position {symbol} already has TP/SL")
            
            self.logger.debug(f"← check_open_positions returned dict with {len(updated_positions)} updated positions")
            return updated_positions
            
        except Exception as e:
            self.logger.error(f"Error checking open positions: {str(e)}")
            self.logger.debug(f"← check_open_positions returned empty dict (error)")
            return {}
    
    async def process_position_updates(self, symbol: str, position: Dict) -> Dict:
        """
        Process position updates and manage TP/SL
        
        Args:
            symbol: Trading symbol
            position: Position dictionary
            
        Returns:
            Dictionary with update results
        """
        self.logger.debug(f"→ process_position_updates(symbol={symbol}, position={position})")
        
        result = {
            "symbol": symbol,
            "updated": False,
            "action": "none"
        }
        
        try:
            # Check if position exists
            if not position or float(position.get('size', '0')) == 0:
                # Position closed or doesn't exist
                if symbol in self.active_tpsl:
                    # Remove from tracking
                    del self.active_tpsl[symbol]
                    self.logger.info(f"Position closed for {symbol}, removed from TP/SL tracking")
                    result["action"] = "removed"
                    
                self.logger.debug(f"← process_position_updates returned: {result}")
                return result
                
            # Check if TP/SL are set
            tp_active = float(position.get('takeProfit', '0')) > 0
            sl_active = float(position.get('stopLoss', '0')) > 0
            
            # If either TP or SL is missing, apply them
            if not (tp_active and sl_active):
                self.logger.info(f"Position {symbol} missing TP/SL, applying now")
                apply_result = await self.apply_tpsl_for_position(symbol, position)
                
                if apply_result:
                    result["updated"] = True
                    result["action"] = "applied"
                    self.logger.debug(f"← process_position_updates returned: {result}")
                    return result
            
            # Get current price for trailing stop
            current_price = await self.data_manager.get_latest_price(symbol)
            
            # Update trailing stop if needed
            if current_price > 0 and self.use_trailing_stop:
                trailing_updated = await self.check_and_update_trailing_stops(symbol, current_price)
                
                if trailing_updated:
                    result["updated"] = True
                    result["action"] = "trailing_updated"
                    
            self.logger.debug(f"← process_position_updates returned: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing position updates for {symbol}: {str(e)}")
            result["error"] = str(e)
            self.logger.debug(f"← process_position_updates returned: {result}")
            return result