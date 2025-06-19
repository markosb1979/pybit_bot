"""
Order Manager - Handles order creation, tracking, and execution
"""

import logging
import time
import uuid
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from pybit_bot.core.client import BybitClient
from pybit_bot.core.order_manager_client import OrderManagerClient
from pybit_bot.utils.logger import Logger
from pybit_bot.exceptions import InvalidOrderError  # Remove OrderExecutionError

# Define OrderExecutionError locally
class OrderExecutionError(Exception):
    """Exception raised when an order fails to execute"""
    pass


class OrderManager:
    """
    OrderManager handles all trading execution, order placement,
    and position tracking
    """
    
    def __init__(self, client: BybitClient, config: Dict, logger=None):
        """
        Initialize the order manager.
        
        Args:
            client: BybitClient instance
            config: Configuration dictionary for execution settings
            logger: Optional logger instance
        """
        self.client = client
        self.config = config
        self.logger = logger or Logger("OrderManager")
        
        # Initialize OrderManagerClient
        self.order_client = OrderManagerClient(client, logger, config)
        
        self.active_orders = {}  # Track active orders
        self.order_history = {}  # Track order history
        self.positions = {}      # Track current positions
        self.pending_tpsl = {}   # Track orders waiting for TP/SL to be set
        
        # Extract configuration
        self.position_config = config.get('position_sizing', {})
        self.risk_config = config.get('risk_management', {})
        self.order_config = config.get('order_execution', {})
        
        self.logger.info("OrderManager initialized")
    
    async def initialize(self):
        """
        Initialize order manager, load existing positions and orders.
        """
        try:
            # Load existing positions
            self.logger.info("Loading existing positions...")
            # Make sure to provide a symbol to get_positions
            symbols = self.config.get('general', {}).get('trading', {}).get('symbols', ["BTCUSDT"])
            default_symbol = symbols[0] if symbols else "BTCUSDT"
            positions = self.order_client.get_positions(default_symbol)
            
            for position in positions:
                symbol = position.get('symbol')
                if symbol:
                    self.positions[symbol] = position
                    
            self.logger.info(f"Loaded {len(self.positions)} existing positions")
            
            # Load open orders
            self.logger.info("Loading open orders...")
            open_orders = self.order_client.get_open_orders(default_symbol)
            
            for order in open_orders:
                order_id = order.get('orderId')
                if order_id:
                    self.active_orders[order_id] = order
            
            self.logger.info(f"Loaded {len(self.active_orders)} open orders")
            
            return True
        except Exception as e:
            self.logger.error(f"Error initializing OrderManager: {str(e)}")
            return False
    
    async def get_account_balance(self):
        """
        Get account balance.
        
        Returns:
            Dictionary containing balance information
        """
        try:
            self.logger.info("Getting account balance...")
            balance_data = self.order_client.get_account_balance()
            
            # Debug log the result
            self.logger.info(f"Balance data received: {balance_data}")
            
            return balance_data
            
        except Exception as e:
            self.logger.error(f"Error getting account balance: {str(e)}")
            # For testing, return a valid default
            return {"totalAvailableBalance": "1000.0"}
    
    async def get_current_price(self, symbol: str) -> float:
        """
        Get the current price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price as float
        """
        try:
            # Get ticker from the client
            ticker = self.client.get_ticker(symbol)
            price = float(ticker.get('lastPrice', 0))
            
            if price <= 0:
                self.logger.error(f"Invalid price for {symbol}: {price}")
                return 0.0
                
            self.logger.info(f"Current price for {symbol}: {price}")
            return price
        except Exception as e:
            self.logger.error(f"Error getting current price for {symbol}: {str(e)}")
            return 0.0
    
    async def calculate_position_size(self, symbol: str, amount_usdt: float) -> float:
        """
        Calculate position size in coins based on USDT amount.
        
        Args:
            symbol: Trading symbol
            amount_usdt: Amount in USDT
            
        Returns:
            Position size in coins
        """
        try:
            # Use OrderManagerClient to calculate position size
            size_str = self.order_client.calculate_position_size(symbol, amount_usdt)
            position_size = float(size_str)
            
            self.logger.info(f"Calculated position size for {symbol}: {position_size}")
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            return 0.0
    
    async def enter_position_market(
        self,
        symbol: str,
        side: str,
        qty: float = None,
        usdt_amount: float = None
    ) -> Dict:
        """
        Enter a position with a market order WITHOUT TP/SL.
        
        Args:
            symbol: Trading symbol
            side: "Buy" or "Sell"
            qty: Position size (optional if usdt_amount provided)
            usdt_amount: Amount in USDT to use for position (optional if qty provided)
            
        Returns:
            Dictionary with order results including fill information
        """
        try:
            direction = "LONG" if side == "Buy" else "SHORT"
            
            # Check if at least one of qty or usdt_amount is provided
            if qty is None and usdt_amount is None:
                error_msg = "Either qty or usdt_amount must be provided"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Calculate position size if qty is not provided
            if qty is None:
                self.logger.info(f"Entering {direction} position for {symbol}, amount={usdt_amount} USDT (without TP/SL)")
                qty = float(self.order_client.calculate_position_size(symbol, usdt_amount))
            else:
                self.logger.info(f"Entering {direction} position for {symbol}, qty={qty} (without TP/SL)")
            
            # Place order using OrderManagerClient
            order = self.order_client.place_active_order(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=str(qty)
            )
            
            self.logger.info(f"{direction} order result: {order}")
            
            # Track the order
            if 'orderId' in order:
                order_id = order['orderId']
                self.active_orders[order_id] = {
                    'symbol': symbol,
                    'side': side,
                    'direction': direction,
                    'quantity': qty,
                    'order_type': 'Market',
                    'status': 'Created',
                    'order_id': order_id,
                    'timestamp': int(time.time() * 1000),
                    'needs_tpsl': True  # Flag to indicate TP/SL needed
                }
                
                # Add to pending TP/SL tracking
                self.pending_tpsl[order_id] = {
                    'symbol': symbol,
                    'side': side,
                    'direction': direction,
                    'quantity': qty,
                    'order_id': order_id
                }
            
            return order
            
        except Exception as e:
            self.logger.error(f"Error entering {side} position: {str(e)}")
            return {"error": str(e)}
    
    async def set_position_tpsl(self, symbol: str, position_idx: int, tp_price: str, sl_price: str) -> Dict:
        """
        Set TP/SL for an existing position.
        
        Args:
            symbol: Trading symbol
            position_idx: Position index (0 for one-way mode)
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with TP/SL setting result
        """
        try:
            self.logger.info(f"Setting TP/SL for {symbol} position: TP={tp_price}, SL={sl_price}")
            
            # Get mark price for validation
            mark_price = 0
            try:
                positions = self.order_client.get_positions(symbol)
                if positions:
                    mark_price = float(positions[0].get("markPrice", 0))
                
                if mark_price <= 0:
                    # Fallback to current price
                    mark_price = await self.get_current_price(symbol)
            except Exception as e:
                self.logger.error(f"Error getting mark price: {str(e)}")
                # Fallback to current price
                mark_price = await self.get_current_price(symbol)
                
            # Convert prices to float for validation
            tp_price_float = float(tp_price)
            sl_price_float = float(sl_price)
            
            # Get position side
            position_side = "UNKNOWN"
            if positions and len(positions) > 0:
                side_raw = positions[0].get("side", "")
                position_side = "LONG" if side_raw == "Buy" else "SHORT"
            
            # Validate against mark price
            if position_side == "LONG":
                # Clamp against mark price for LONG
                if tp_price_float <= mark_price:
                    tp_price_float = mark_price * 1.002
                    tp_price = self.order_client._round_price(symbol, tp_price_float)
                    self.logger.warning(f"Adjusted TP above mark: {tp_price}")
                if sl_price_float >= mark_price:
                    sl_price_float = mark_price * 0.998
                    sl_price = self.order_client._round_price(symbol, sl_price_float)
                    self.logger.warning(f"Adjusted SL below mark: {sl_price}")
            elif position_side == "SHORT":
                # Clamp against mark price for SHORT
                if tp_price_float >= mark_price:
                    tp_price_float = mark_price * 0.998
                    tp_price = self.order_client._round_price(symbol, tp_price_float)
                    self.logger.warning(f"Adjusted TP below mark: {tp_price}")
                if sl_price_float <= mark_price:
                    sl_price_float = mark_price * 1.002
                    sl_price = self.order_client._round_price(symbol, sl_price_float)
                    self.logger.warning(f"Adjusted SL above mark: {sl_price}")
            
            # Use OrderManagerClient to set TP/SL
            result = self.order_client.set_trading_stop(
                symbol=symbol,
                positionIdx=position_idx,
                takeProfit=tp_price,
                stopLoss=sl_price,
                tpTriggerBy="MarkPrice",
                slTriggerBy="MarkPrice"
            )
            
            self.logger.info(f"Set TP/SL result: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error setting TP/SL: {str(e)}")
            return {"error": str(e)}
    
    async def get_position_fill_info(self, symbol: str, order_id: str) -> Dict:
        """
        Get fill information for a position by order ID.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID that created the position
            
        Returns:
            Dictionary with fill information including price
        """
        try:
            # Use OrderManagerClient to get fill info
            fill = self.order_client.get_order_fill_info(symbol, order_id)
            
            self.logger.info(f"Fill info for {order_id}: {fill}")
            return fill
                
        except Exception as e:
            self.logger.error(f"Error getting position fill info: {str(e)}")
            return {'filled': False, 'error': str(e)}
    
    async def enter_long_with_tp_sl(self, symbol: str, qty: float, tp_price: str, sl_price: str) -> Dict:
        """
        Enter a long position with take profit and stop loss.
        THIS METHOD IS MAINTAINED FOR BACKWARDS COMPATIBILITY
        New code should use enter_position_market followed by set_position_tpsl
        
        Args:
            symbol: Trading symbol
            qty: Position size
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with order results
        """
        try:
            self.logger.info(f"Entering LONG position for {symbol}, qty={qty}, TP={tp_price}, SL={sl_price}")
            self.logger.warning("Using deprecated method enter_long_with_tp_sl, consider using post-fill approach")
            
            # Use OrderManagerClient to place order with TP/SL
            order_result = self.order_client.place_active_order(
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=str(qty),
                take_profit=tp_price,
                stop_loss=sl_price
            )
            
            self.logger.info(f"Long order result: {order_result}")
            
            # Track the order
            if 'orderId' in order_result:
                order_id = order_result['orderId']
                self.active_orders[order_id] = {
                    'symbol': symbol,
                    'side': 'Buy',
                    'quantity': qty,
                    'order_type': 'Market',
                    'take_profit': tp_price,
                    'stop_loss': sl_price,
                    'status': 'Created',
                    'order_id': order_id,
                    'timestamp': int(time.time() * 1000)
                }
            
            return {
                "entry_order": order_result,
                "tp_order": None,
                "sl_order": None
            }
            
        except Exception as e:
            self.logger.error(f"Error entering long position: {str(e)}")
            return {
                "entry_order": {"error": str(e)},
                "tp_order": None,
                "sl_order": None
            }
    
    async def enter_short_with_tp_sl(self, symbol: str, qty: float, tp_price: str, sl_price: str) -> Dict:
        """
        Enter a short position with take profit and stop loss.
        THIS METHOD IS MAINTAINED FOR BACKWARDS COMPATIBILITY
        New code should use enter_position_market followed by set_position_tpsl
        
        Args:
            symbol: Trading symbol
            qty: Position size
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Dictionary with order results
        """
        try:
            self.logger.info(f"Entering SHORT position for {symbol}, qty={qty}, TP={tp_price}, SL={sl_price}")
            self.logger.warning("Using deprecated method enter_short_with_tp_sl, consider using post-fill approach")
            
            # Use OrderManagerClient to place order with TP/SL
            order_result = self.order_client.place_active_order(
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=str(qty),
                take_profit=tp_price,
                stop_loss=sl_price
            )
            
            self.logger.info(f"Short order result: {order_result}")
            
            # Track the order
            if 'orderId' in order_result:
                order_id = order_result['orderId']
                self.active_orders[order_id] = {
                    'symbol': symbol,
                    'side': 'Sell',
                    'quantity': qty,
                    'order_type': 'Market',
                    'take_profit': tp_price,
                    'stop_loss': sl_price,
                    'status': 'Created',
                    'order_id': order_id,
                    'timestamp': int(time.time() * 1000)
                }
            
            return {
                "entry_order": order_result,
                "tp_order": None,
                "sl_order": None
            }
            
        except Exception as e:
            self.logger.error(f"Error entering short position: {str(e)}")
            return {
                "entry_order": {"error": str(e)},
                "tp_order": None,
                "sl_order": None
            }
    
    async def close_position(self, symbol: str) -> Dict:
        """
        Close an open position.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with close result
        """
        try:
            self.logger.info(f"Closing position for {symbol}")
            
            # Use OrderManagerClient to close position
            result = self.order_client.close_position(symbol)
            
            self.logger.info(f"Close position result: {result}")
            
            return {"success": True, "result": result}
            
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def update_tp_sl(self, symbol: str, tp_price: Optional[str] = None, sl_price: Optional[str] = None) -> Dict:
        """
        Update take profit and stop loss for an open position.
        
        Args:
            symbol: Trading symbol
            tp_price: New take profit price
            sl_price: New stop loss price
            
        Returns:
            Dictionary with update result
        """
        try:
            self.logger.info(f"Updating TP/SL for {symbol}: TP={tp_price}, SL={sl_price}")
            
            if not tp_price and not sl_price:
                return {"success": False, "message": "No TP or SL provided"}
            
            # Get position
            positions = self.order_client.get_positions(symbol)
            position = None
            
            for pos in positions:
                if pos.get('symbol') == symbol:
                    position = pos
                    break
            
            if not position or float(position.get('size', '0')) == 0:
                self.logger.warning(f"No position to update TP/SL for {symbol}")
                return {"success": False, "message": "No position found"}
            
            # Position ID
            position_idx = position.get('positionIdx', 0)
            
            # Use OrderManagerClient to set TP/SL
            params = {
                "symbol": symbol,
                "positionIdx": position_idx
            }
            
            if tp_price:
                params["takeProfit"] = tp_price
                params["tpTriggerBy"] = "MarkPrice"
                
            if sl_price:
                params["stopLoss"] = sl_price
                params["slTriggerBy"] = "MarkPrice"
            
            result = self.order_client.set_trading_stop(**params)
            
            self.logger.info(f"Update TP/SL result: {result}")
            
            return {"success": True, "result": result}
            
        except Exception as e:
            self.logger.error(f"Error updating TP/SL: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get current positions.
        
        Args:
            symbol: Optional trading symbol to filter
            
        Returns:
            List of position dictionaries
        """
        try:
            # Use OrderManagerClient to get positions
            positions = self.order_client.get_positions(symbol)
            
            # Cache the positions
            for position in positions:
                pos_symbol = position.get('symbol')
                if pos_symbol:
                    self.positions[pos_symbol] = position
            
            # Filter by symbol if provided
            filtered_positions = []
            for position in positions:
                if position.get('symbol') == symbol or symbol is None:
                    filtered_positions.append(position)
            
            return filtered_positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            return []
    
    def get_open_orders_sync(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open orders (synchronous version).
        
        Args:
            symbol: Optional trading symbol to filter
            
        Returns:
            List of order dictionaries
        """
        try:
            # Use OrderManagerClient to get open orders
            orders = self.order_client.get_open_orders(symbol)
            
            # Cache the orders
            for order in orders:
                order_id = order.get('orderId')
                if order_id:
                    self.active_orders[order_id] = order
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Error getting open orders: {str(e)}")
            return []
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open orders (async version).
        
        Returns:
            List of order dictionaries
        """
        return self.get_open_orders_sync(symbol)
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """
        Cancel an open order.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            Dictionary with cancel result
        """
        try:
            self.logger.info(f"Cancelling order {order_id} for {symbol}")
            
            # Use OrderManagerClient to cancel order
            cancel_result = self.order_client.cancel_order(symbol, order_id)
            
            self.logger.info(f"Cancel order result: {cancel_result}")
            
            # Remove from active orders
            if order_id in self.active_orders:
                # Move to history
                self.order_history[order_id] = {
                    **self.active_orders[order_id],
                    'status': 'Cancelled',
                    'cancel_time': int(time.time() * 1000)
                }
                # Remove from active
                del self.active_orders[order_id]
            
            # Also remove from pending TP/SL if present
            if order_id in self.pending_tpsl:
                del self.pending_tpsl[order_id]
            
            return {"success": True, "result": cancel_result}
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict:
        """
        Cancel all open orders.
        
        Args:
            symbol: Optional trading symbol to filter
            
        Returns:
            Dictionary with cancel results
        """
        try:
            self.logger.info(f"Cancelling all orders{f' for {symbol}' if symbol else ''}")
            
            # Use OrderManagerClient to cancel all orders
            if symbol:
                result = self.order_client.cancel_all_orders(symbol)
                self.logger.info(f"Cancel all orders result: {result}")
                
                # Update our tracking
                for order_id in list(self.active_orders.keys()):
                    order = self.active_orders[order_id]
                    if order.get('symbol') == symbol:
                        # Move to history
                        self.order_history[order_id] = {
                            **order,
                            'status': 'Cancelled',
                            'cancel_time': int(time.time() * 1000)
                        }
                        # Remove from active
                        del self.active_orders[order_id]
                        
                        # Also remove from pending TP/SL if present
                        if order_id in self.pending_tpsl:
                            del self.pending_tpsl[order_id]
                
                return {"success": True, "result": result}
            else:
                # Cancel for each symbol we know about
                results = []
                symbols = set()
                
                # Get symbols from active orders
                for order in self.active_orders.values():
                    symbols.add(order.get('symbol'))
                
                # Add symbols from positions
                for symbol in self.positions.keys():
                    symbols.add(symbol)
                
                # Default symbol
                if not symbols:
                    symbols.add(self.config.get('general', {}).get('trading', {}).get('symbols', ["BTCUSDT"])[0])
                
                # Cancel all orders for each symbol
                for symbol in symbols:
                    result = self.order_client.cancel_all_orders(symbol)
                    results.append(result)
                
                # Update our tracking
                for order_id in list(self.active_orders.keys()):
                    # Move to history
                    self.order_history[order_id] = {
                        **self.active_orders[order_id],
                        'status': 'Cancelled',
                        'cancel_time': int(time.time() * 1000)
                    }
                    # Remove from active
                    del self.active_orders[order_id]
                    
                    # Also remove from pending TP/SL if present
                    if order_id in self.pending_tpsl:
                        del self.pending_tpsl[order_id]
                
                return {"success": True, "cancelled_count": len(results), "results": results}
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def check_pending_tpsl_orders(self) -> None:
        """
        Check and process any orders waiting for TP/SL to be set.
        This should be called periodically from the main loop.
        """
        if not self.pending_tpsl:
            return
            
        self.logger.info(f"Checking {len(self.pending_tpsl)} pending TP/SL orders")
        
        # Process each pending order
        for order_id, order_data in list(self.pending_tpsl.items()):
            try:
                symbol = order_data['symbol']
                
                # Get fill information using OrderManagerClient
                fill_info = self.order_client.get_order_fill_info(symbol, order_id)
                
                # Always remove from pending_tpsl regardless of outcome
                if order_id in self.pending_tpsl:
                    del self.pending_tpsl[order_id]
                
                # Check if order is filled
                if fill_info.get('filled', False):
                    self.logger.info(f"Order {order_id} filled, setting TP/SL")
                    
                    # Check if position still exists
                    pos = self.order_client.get_positions(symbol)
                    if not pos or float(pos[0].get("size", 0)) == 0:
                        self.logger.warning(f"No open position for {order_id}, skipping TP/SL")
                        continue
                    
                    # Get ATR value for TP/SL calculation from DataManager
                    atr = None
                    try:
                        if hasattr(self.data_manager, 'get_atr'):
                            atr = await self.data_manager.get_atr(symbol, timeframe="1m", length=14)
                            self.logger.info(f"Retrieved ATR from data_manager: {atr}")
                        elif hasattr(self.data_manager, 'get_historical_data'):
                            # Calculate ATR from recent price data
                            hist_data = await self.data_manager.get_historical_data(symbol, interval="1m", limit=20)
                            if not hist_data.empty and len(hist_data) > 14:
                                # Simple TR and ATR calculation
                                tr_values = []
                                for i in range(1, len(hist_data)):
                                    high = hist_data['high'].iloc[i]
                                    low = hist_data['low'].iloc[i]
                                    prev_close = hist_data['close'].iloc[i-1]
                                    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                                    tr_values.append(tr)
                                atr = sum(tr_values[-14:]) / 14  # Simple average of last 14 TR values
                                self.logger.info(f"Calculated ATR from historical data: {atr}")
                    except Exception as e:
                        self.logger.error(f"Error calculating ATR: {str(e)}")
                    
                    # If ATR couldn't be calculated, use a dynamic fallback
                    if not atr or atr <= 0:
                        # Use recent price action volatility as fallback
                        current_price = await self.get_current_price(symbol)
                        atr = current_price * 0.01  # 1% of current price as fallback
                        self.logger.warning(f"Using fallback ATR calculation: {atr}")
                    
                    # Set TP/SL
                    await self.set_tpsl_for_filled_order(symbol, order_id, atr)
                else:
                    # Check if order is too old and should be cancelled
                    order_age = int(time.time() * 1000) - order_data.get('timestamp', 0)
                    timeout = self.order_config.get('order_timeout_seconds', 60) * 1000
                    
                    if order_age > timeout:
                        self.logger.warning(f"Order {order_id} timed out after {order_age/1000} seconds, cancelling")
                        await self.cancel_order(symbol, order_id)
                
            except Exception as e:
                self.logger.error(f"Error processing pending TP/SL for order {order_id}: {str(e)}")
    
    async def set_tpsl_for_filled_order(self, symbol: str, order_id: str, atr_value: float) -> Dict:
        """
        Calculate and set TP/SL for a filled order based on actual fill price.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            atr_value: ATR value for risk calculation
            
        Returns:
            Dictionary with TP/SL setting result
        """
        try:
            self.logger.info(f"Setting TP/SL for filled order {order_id}")
            
            # Get fill information
            fill_info = await self.get_position_fill_info(symbol, order_id)
            
            # Check if order is filled
            if not fill_info.get('filled', False):
                self.logger.warning(f"Order {order_id} not filled yet, status: {fill_info.get('status', 'unknown')}")
                return {"error": "Order not filled", "status": fill_info.get('status', 'unknown')}
                
            # Extract fill information
            fill_price = fill_info.get('fill_price', 0)
            side = fill_info.get('side', '')
            position_idx = fill_info.get('position_idx', 0)
            
            if fill_price <= 0:
                self.logger.error(f"Invalid fill price for {order_id}: {fill_price}")
                return {"error": "Invalid fill price"}
                
            # Determine direction
            direction = "LONG" if side == "Buy" else "SHORT"
            
            # Calculate TP/SL levels based on ATR
            tp_multiplier = self.risk_config.get('take_profit_multiplier', 4.0)
            sl_multiplier = self.risk_config.get('stop_loss_multiplier', 2.0)
            
            # Get current mark price for validation
            mark_price = 0
            try:
                positions = self.order_client.get_positions(symbol)
                if positions:
                    mark_price = float(positions[0].get("markPrice", 0))
                
                if mark_price <= 0:
                    # Fallback to current price
                    mark_price = await self.get_current_price(symbol)
            except Exception as e:
                self.logger.error(f"Error getting mark price: {str(e)}")
                # Use fill price as fallback
                mark_price = fill_price
            
            # For long positions
            if direction == "LONG":
                tp_price = fill_price + (atr_value * tp_multiplier)
                sl_price = fill_price - (atr_value * sl_multiplier)
                
                # Clamp against mark price
                if tp_price <= mark_price:
                    tp_price = mark_price * 1.002
                    self.logger.warning(f"Adjusted TP above mark: {tp_price}")
                if sl_price >= mark_price:
                    sl_price = mark_price * 0.998
                    self.logger.warning(f"Adjusted SL below mark: {sl_price}")
            
            # For short positions
            else:
                tp_price = fill_price - (atr_value * tp_multiplier)
                sl_price = fill_price + (atr_value * sl_multiplier)
                
                # Clamp against mark price
                if tp_price >= mark_price:
                    tp_price = mark_price * 0.998
                    self.logger.warning(f"Adjusted TP below mark: {tp_price}")
                if sl_price <= mark_price:
                    sl_price = mark_price * 1.002
                    self.logger.warning(f"Adjusted SL above mark: {sl_price}")
            
            # Round to appropriate precision
            tp_price_str = self.order_client._round_price(symbol, tp_price)
            sl_price_str = self.order_client._round_price(symbol, sl_price)
            
            self.logger.info(f"Final TP/SL for {symbol} {direction}: TP={tp_price_str}, SL={sl_price_str}, Mark Price={mark_price}")
            
            # Set TP/SL for the position using OrderManagerClient
            result = self.order_client.set_trading_stop(
                symbol=symbol,
                positionIdx=position_idx,
                takeProfit=tp_price_str,
                stopLoss=sl_price_str,
                tpTriggerBy="MarkPrice",
                slTriggerBy="MarkPrice"
            )
            
            # Update the order in active orders
            if order_id in self.active_orders:
                self.active_orders[order_id]['take_profit'] = tp_price_str
                self.active_orders[order_id]['stop_loss'] = sl_price_str
                self.active_orders[order_id]['needs_tpsl'] = False
            
            return {
                **result,
                "fill_price": fill_price,
                "tp_price": tp_price_str,
                "sl_price": sl_price_str
            }
            
        except Exception as e:
            self.logger.error(f"Error setting TP/SL for filled order: {str(e)}")
            return {"error": str(e)}
    
    def save_order_history(self, filepath: str) -> bool:
        """
        Save order history to a CSV file.
        """
        try:
            self.logger.info(f"Saving order history to {filepath}")
            
            # Create the directory if it doesn't exist
            import os
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Convert order history to list of dicts
            orders = []
            for order_id, order in self.order_history.items():
                order_copy = order.copy()
                order_copy['order_id'] = order_id
                orders.append(order_copy)
            
            # Write out to CSV
            import pandas as pd
            df = pd.DataFrame(orders)
            df.to_csv(filepath, index=False)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving order history: {str(e)}")
            return False
