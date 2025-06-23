"""
TP/SL Manager - Manages take profit and stop loss orders

This module handles tracking and execution of take profit and stop loss orders,
including trailing stops.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from ..utils.logger import Logger


class TPSLManager:
    """
    TPSLManager handles take profit and stop loss order management
    """
    
    def __init__(self, order_manager, config, logger=None):
        """
        Initialize the TP/SL manager
        
        Args:
            order_manager: OrderManager instance
            config: Configuration dictionary
            logger: Optional logger instance
        """
        self.logger = logger or Logger("TPSLManager")
        self.logger.debug(f"ENTER __init__(order_manager={order_manager}, config={config}, logger={logger})")
        
        self.order_manager = order_manager
        self.config = config
        
        # Configuration for TP/SL
        tpsl_config = self.config.get('execution', {}).get('tpsl_manager', {})
        self.check_interval_ms = tpsl_config.get('check_interval_ms', 100)
        self.default_stop_type = tpsl_config.get('default_stop_type', 'TRAILING')
        
        # Track TP/SL orders
        self.tpsl_orders = {}  # Format: {order_id: {tp_order_id, sl_order_id, ...}}
        
        # Track positions with trailing stops
        self.trailing_stops = {}  # Format: {symbol: {side: {activation_price, trail_value, ...}}}
        
        self.logger.info("TP/SL Manager initialized")
        self.logger.debug(f"EXIT __init__ completed")
    
    def add_tpsl_order(self, symbol: str, order_id: str, side: str, entry_price: float,
                       tp_price: Optional[float] = None, sl_price: Optional[float] = None) -> bool:
        """
        Add a new TP/SL order to track
        
        Args:
            symbol: Trading symbol
            order_id: Main order ID
            side: Order side ("Buy" or "Sell")
            entry_price: Entry price
            tp_price: Take profit price (optional)
            sl_price: Stop loss price (optional)
            
        Returns:
            True if added successfully, False otherwise
        """
        self.logger.debug(f"ENTER add_tpsl_order(symbol={symbol}, order_id={order_id}, side={side}, entry_price={entry_price}, tp_price={tp_price}, sl_price={sl_price})")
        
        try:
            # Add to tracking
            self.tpsl_orders[order_id] = {
                'symbol': symbol,
                'side': side,
                'entry_price': entry_price,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'tp_order_id': None,
                'sl_order_id': None,
                'status': 'NEW',
                'create_time': int(time.time() * 1000)
            }
            
            self.logger.info(f"Added TP/SL order for {symbol} {side} order {order_id}")
            self.logger.debug(f"EXIT add_tpsl_order returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding TP/SL order: {str(e)}")
            self.logger.debug(f"EXIT add_tpsl_order returned False (error)")
            return False
    
    def add_trailing_stop(self, symbol: str, side: str, entry_price: float, 
                          activation_price: float, trail_value: float) -> bool:
        """
        Add a trailing stop for a position
        
        Args:
            symbol: Trading symbol
            side: Position side ("Buy" or "Sell")
            entry_price: Entry price
            activation_price: Price at which trailing begins
            trail_value: Amount to trail by
            
        Returns:
            True if added successfully, False otherwise
        """
        self.logger.debug(f"ENTER add_trailing_stop(symbol={symbol}, side={side}, entry_price={entry_price}, activation_price={activation_price}, trail_value={trail_value})")
        
        try:
            # Initialize symbol entry if needed
            if symbol not in self.trailing_stops:
                self.trailing_stops[symbol] = {}
                
            # Add trailing stop
            self.trailing_stops[symbol][side] = {
                'entry_price': entry_price,
                'activation_price': activation_price,
                'trail_value': trail_value,
                'highest_price': entry_price,
                'lowest_price': entry_price,
                'current_stop': None,
                'status': 'PENDING',
                'create_time': int(time.time() * 1000)
            }
            
            self.logger.info(f"Added trailing stop for {symbol} {side} position")
            self.logger.debug(f"EXIT add_trailing_stop returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding trailing stop: {str(e)}")
            self.logger.debug(f"EXIT add_trailing_stop returned False (error)")
            return False
    
    async def update(self) -> None:
        """
        Update all TP/SL orders and trailing stops
        """
        self.logger.debug(f"ENTER update()")
        
        try:
            # Process TP/SL orders
            await self._process_tpsl_orders()
            
            # Process trailing stops
            await self._process_trailing_stops()
            
        except Exception as e:
            self.logger.error(f"Error updating TP/SL: {str(e)}")
            
        finally:
            self.logger.debug(f"EXIT update completed")
    
    async def _process_tpsl_orders(self) -> None:
        """
        Process TP/SL orders
        """
        self.logger.debug(f"ENTER _process_tpsl_orders()")
        
        try:
            # Get all active orders to check status
            active_orders = await self.order_manager.get_active_orders()
            active_order_ids = {order.get('orderId') for order in active_orders}
            
            # Check each TP/SL order
            for order_id, order_data in list(self.tpsl_orders.items()):
                # Skip if already processed
                if order_data['status'] in ['FILLED', 'CANCELLED']:
                    continue
                    
                # Check if main order is still active
                if order_id not in active_order_ids:
                    # Main order is no longer active, check if it was filled
                    order_info = await self.order_manager._get_order_info(order_id)
                    
                    if order_info and order_info.get('orderStatus') == 'Filled':
                        # Main order was filled, place TP/SL orders if not done already
                        if not order_data['tp_order_id'] and order_data['tp_price']:
                            await self._place_tp_order(order_id)
                            
                        if not order_data['sl_order_id'] and order_data['sl_price']:
                            await self._place_sl_order(order_id)
                    else:
                        # Main order was cancelled or rejected
                        order_data['status'] = 'CANCELLED'
                        self.logger.info(f"TP/SL order {order_id} cancelled (main order not filled)")
            
        except Exception as e:
            self.logger.error(f"Error processing TP/SL orders: {str(e)}")
            
        finally:
            self.logger.debug(f"EXIT _process_tpsl_orders completed")
    
    async def _process_trailing_stops(self) -> None:
        """
        Process trailing stops
        """
        self.logger.debug(f"ENTER _process_trailing_stops()")
        
        try:
            # Get current positions
            positions = await self.order_manager.get_positions()
            
            # Process each symbol with trailing stops
            for symbol, side_data in list(self.trailing_stops.items()):
                # Find position for this symbol
                symbol_positions = [p for p in positions if p.get('symbol') == symbol]
                
                if not symbol_positions:
                    # No position for this symbol, remove trailing stops
                    self.logger.info(f"No position found for {symbol}, removing trailing stops")
                    self.trailing_stops.pop(symbol, None)
                    continue
                
                # Get current market price
                ticker = await self.order_manager.get_ticker(symbol)
                if not ticker or 'last_price' not in ticker:
                    self.logger.warning(f"Could not get current price for {symbol}")
                    continue
                    
                current_price = float(ticker['last_price'])
                
                # Process trailing stops for each side
                for side, stop_data in list(side_data.items()):
                    # Check if position still exists for this side
                    position_side = 'Buy' if side == 'Buy' else 'Sell'
                    matching_positions = [p for p in symbol_positions if p.get('side') == position_side]
                    
                    if not matching_positions:
                        # No position for this side, remove trailing stop
                        self.logger.info(f"No {side} position found for {symbol}, removing trailing stop")
                        side_data.pop(side, None)
                        continue
                    
                    # Check if stop is activated
                    if stop_data['status'] == 'PENDING':
                        # Check if price has reached activation level
                        if side == 'Buy' and current_price >= stop_data['activation_price']:
                            stop_data['status'] = 'ACTIVE'
                            stop_data['current_stop'] = current_price - stop_data['trail_value']
                            self.logger.info(f"Trailing stop activated for {symbol} {side} position at {current_price}")
                        elif side == 'Sell' and current_price <= stop_data['activation_price']:
                            stop_data['status'] = 'ACTIVE'
                            stop_data['current_stop'] = current_price + stop_data['trail_value']
                            self.logger.info(f"Trailing stop activated for {symbol} {side} position at {current_price}")
                    
                    # Update trailing stop if active
                    if stop_data['status'] == 'ACTIVE':
                        if side == 'Buy':
                            # For long positions, trail price upwards
                            if current_price > stop_data['highest_price']:
                                # Update highest price and stop level
                                old_stop = stop_data['current_stop']
                                stop_data['highest_price'] = current_price
                                stop_data['current_stop'] = current_price - stop_data['trail_value']
                                self.logger.info(f"Updated trailing stop for {symbol} {side} from {old_stop} to {stop_data['current_stop']}")
                                
                            # Check if price has hit stop level
                            if current_price <= stop_data['current_stop']:
                                # Trigger stop
                                await self._execute_trailing_stop(symbol, side, stop_data)
                                
                        elif side == 'Sell':
                            # For short positions, trail price downwards
                            if current_price < stop_data['lowest_price']:
                                # Update lowest price and stop level
                                old_stop = stop_data['current_stop']
                                stop_data['lowest_price'] = current_price
                                stop_data['current_stop'] = current_price + stop_data['trail_value']
                                self.logger.info(f"Updated trailing stop for {symbol} {side} from {old_stop} to {stop_data['current_stop']}")
                                
                            # Check if price has hit stop level
                            if current_price >= stop_data['current_stop']:
                                # Trigger stop
                                await self._execute_trailing_stop(symbol, side, stop_data)
            
        except Exception as e:
            self.logger.error(f"Error processing trailing stops: {str(e)}")
            
        finally:
            self.logger.debug(f"EXIT _process_trailing_stops completed")
    
    async def _place_tp_order(self, order_id: str) -> bool:
        """
        Place take profit order
        
        Args:
            order_id: Main order ID
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.debug(f"ENTER _place_tp_order(order_id={order_id})")
        
        try:
            # Get order data
            order_data = self.tpsl_orders.get(order_id)
            if not order_data:
                self.logger.warning(f"No TP/SL data found for order {order_id}")
                self.logger.debug(f"EXIT _place_tp_order returned False (no data)")
                return False
                
            # Get order details
            symbol = order_data['symbol']
            side = order_data['side']
            tp_price = order_data['tp_price']
            
            if not tp_price:
                self.logger.warning(f"No TP price set for order {order_id}")
                self.logger.debug(f"EXIT _place_tp_order returned False (no TP price)")
                return False
                
            # Determine close side (opposite of entry)
            close_side = "Sell" if side == "Buy" else "Buy"
            
            # Get position size
            positions = await self.order_manager.get_positions(symbol)
            if not positions:
                self.logger.warning(f"No position found for {symbol}")
                self.logger.debug(f"EXIT _place_tp_order returned False (no position)")
                return False
                
            position = positions[0]
            qty = abs(float(position.get('size', '0')))
            
            if qty <= 0:
                self.logger.warning(f"Invalid position size: {qty}")
                self.logger.debug(f"EXIT _place_tp_order returned False (invalid size)")
                return False
                
            # Place take profit order
            result = await self.order_manager.place_limit_order(
                symbol=symbol,
                side=close_side,
                qty=qty,
                price=tp_price,
                reduce_only=True
            )
            
            if 'error' in result:
                self.logger.error(f"Failed to place TP order: {result['error']}")
                self.logger.debug(f"EXIT _place_tp_order returned False (API error)")
                return False
                
            # Update tracking
            tp_order_id = result.get('orderId')
            order_data['tp_order_id'] = tp_order_id
            
            self.logger.info(f"Placed TP order {tp_order_id} for {symbol} at {tp_price}")
            self.logger.debug(f"EXIT _place_tp_order returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error placing TP order: {str(e)}")
            self.logger.debug(f"EXIT _place_tp_order returned False (exception)")
            return False
    
    async def _place_sl_order(self, order_id: str) -> bool:
        """
        Place stop loss order
        
        Args:
            order_id: Main order ID
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.debug(f"ENTER _place_sl_order(order_id={order_id})")
        
        try:
            # Get order data
            order_data = self.tpsl_orders.get(order_id)
            if not order_data:
                self.logger.warning(f"No TP/SL data found for order {order_id}")
                self.logger.debug(f"EXIT _place_sl_order returned False (no data)")
                return False
                
            # Get order details
            symbol = order_data['symbol']
            side = order_data['side']
            sl_price = order_data['sl_price']
            
            if not sl_price:
                self.logger.warning(f"No SL price set for order {order_id}")
                self.logger.debug(f"EXIT _place_sl_order returned False (no SL price)")
                return False
                
            # Determine close side (opposite of entry)
            close_side = "Sell" if side == "Buy" else "Buy"
            
            # Get position size
            positions = await self.order_manager.get_positions(symbol)
            if not positions:
                self.logger.warning(f"No position found for {symbol}")
                self.logger.debug(f"EXIT _place_sl_order returned False (no position)")
                return False
                
            position = positions[0]
            qty = abs(float(position.get('size', '0')))
            
            if qty <= 0:
                self.logger.warning(f"Invalid position size: {qty}")
                self.logger.debug(f"EXIT _place_sl_order returned False (invalid size)")
                return False
                
            # Place stop loss order
            result = await self.order_manager.place_stop_order(
                symbol=symbol,
                side=close_side,
                qty=qty,
                trigger_price=sl_price,
                reduce_only=True,
                close_on_trigger=True
            )
            
            if 'error' in result:
                self.logger.error(f"Failed to place SL order: {result['error']}")
                self.logger.debug(f"EXIT _place_sl_order returned False (API error)")
                return False
                
            # Update tracking
            sl_order_id = result.get('orderId')
            order_data['sl_order_id'] = sl_order_id
            
            self.logger.info(f"Placed SL order {sl_order_id} for {symbol} at {sl_price}")
            self.logger.debug(f"EXIT _place_sl_order returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error placing SL order: {str(e)}")
            self.logger.debug(f"EXIT _place_sl_order returned False (exception)")
            return False
    
    async def _execute_trailing_stop(self, symbol: str, side: str, stop_data: Dict[str, Any]) -> bool:
        """
        Execute a trailing stop
        
        Args:
            symbol: Trading symbol
            side: Position side
            stop_data: Trailing stop data
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.debug(f"ENTER _execute_trailing_stop(symbol={symbol}, side={side})")
        
        try:
            # Determine close side (opposite of position)
            close_side = "Sell" if side == "Buy" else "Buy"
            
            # Get position size
            positions = await self.order_manager.get_positions(symbol)
            matching_positions = [p for p in positions if p.get('side') == side]
            
            if not matching_positions:
                self.logger.warning(f"No {side} position found for {symbol}")
                self.logger.debug(f"EXIT _execute_trailing_stop returned False (no position)")
                return False
                
            position = matching_positions[0]
            qty = abs(float(position.get('size', '0')))
            
            # Place market order to close position
            result = await self.order_manager.place_market_order(
                symbol=symbol,
                side=close_side,
                qty=qty,
                reduce_only=True
            )
            
            if 'error' in result:
                self.logger.error(f"Failed to execute trailing stop: {result['error']}")
                self.logger.debug(f"EXIT _execute_trailing_stop returned False (API error)")
                return False
                
            # Update status
            stop_data['status'] = 'TRIGGERED'
            stop_data['trigger_time'] = int(time.time() * 1000)
            
            self.logger.info(f"Executed trailing stop for {symbol} {side} at {stop_data['current_stop']}")
            self.logger.debug(f"EXIT _execute_trailing_stop returned True")
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing trailing stop: {str(e)}")
            self.logger.debug(f"EXIT _execute_trailing_stop returned False (exception)")
            return False