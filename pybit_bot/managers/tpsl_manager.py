"""
TPSL Manager - Manages take-profit and stop-loss levels for active positions.
Responsible for tracking positions, updating trailing stops, and executing
TP/SL orders when conditions are met.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import threading
import pandas as pd


class PositionSide(Enum):
    """Enum representing position sides"""
    LONG = "LONG"
    SHORT = "SHORT"


class StopType(Enum):
    """Enum representing different types of stops"""
    FIXED = "FIXED"         # Fixed stop-loss level
    TRAILING = "TRAILING"   # Trailing stop that moves with price
    BREAKEVEN = "BREAKEVEN" # Stop moved to breakeven after certain threshold


class Position:
    """
    Class representing an active position with TP/SL settings.
    """
    
    def __init__(
        self,
        symbol: str,
        side: PositionSide,
        entry_price: float,
        quantity: float,
        timestamp: int,
        position_id: str,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        stop_type: StopType = StopType.FIXED,
        trail_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a position with its TP/SL settings.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            side: Position side (LONG or SHORT)
            entry_price: Average entry price
            quantity: Position size
            timestamp: Entry timestamp (ms)
            position_id: Unique ID for the position
            sl_price: Initial stop-loss price
            tp_price: Take-profit price
            stop_type: Type of stop-loss (FIXED, TRAILING, BREAKEVEN)
            trail_config: Configuration for trailing stops
                {
                    'activation_pct': 0.5,  # Activation threshold as % of TP distance
                    'callback_rate': 0.3,   # How tightly the stop follows price
                    'atr_multiplier': 2.0,  # For ATR-based stops
                    'current_atr': 100.0    # Current ATR value
                }
        """
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.timestamp = timestamp
        self.position_id = position_id
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.stop_type = stop_type
        self.trail_config = trail_config or {}
        
        # Tracking state
        self.current_price = entry_price
        self.highest_price = entry_price if side == PositionSide.LONG else float('inf')
        self.lowest_price = entry_price if side == PositionSide.SHORT else 0.0
        self.current_sl_price = sl_price
        self.is_trailing_activated = False
        self.is_breakeven_activated = False
        self.close_price = None
        self.close_timestamp = None
        self.realized_pnl = None
        self.is_active = True
        
        # Calculate activation levels for trailing stop
        self.trail_activation_level = self._calculate_trail_activation_level()
    
    def _calculate_trail_activation_level(self) -> Optional[float]:
        """
        Calculate the price level at which trailing stop should activate.
        
        Returns:
            Activation price level or None if trailing not configured
        """
        if not self.trail_config or not self.tp_price or not self.sl_price:
            return None
            
        activation_pct = self.trail_config.get('activation_pct', 0.5)
        
        if self.side == PositionSide.LONG:
            # For long positions, activation is entry + X% of (TP - entry)
            tp_distance = self.tp_price - self.entry_price
            return self.entry_price + (tp_distance * activation_pct)
        else:
            # For short positions, activation is entry - X% of (entry - TP)
            tp_distance = self.entry_price - self.tp_price
            return self.entry_price - (tp_distance * activation_pct)
    
    def update_price(self, current_price: float, atr_value: Optional[float] = None) -> Tuple[bool, bool]:
        """
        Update the current price and check if any TP/SL conditions are met.
        Also updates trailing stops if configured.
        
        Args:
            current_price: Current market price
            atr_value: Current ATR value (optional)
            
        Returns:
            Tuple of (stop_loss_triggered, take_profit_triggered)
        """
        if not self.is_active:
            return False, False
            
        self.current_price = current_price
        
        # Update ATR value if provided
        if atr_value is not None and self.trail_config:
            self.trail_config['current_atr'] = atr_value
        
        # Update highest/lowest prices
        if self.side == PositionSide.LONG:
            self.highest_price = max(self.highest_price, current_price)
        else:
            self.lowest_price = min(self.lowest_price, current_price)
        
        # Check for trailing stop activation
        if (self.stop_type == StopType.TRAILING and 
            self.trail_activation_level is not None and 
            not self.is_trailing_activated):
            
            if ((self.side == PositionSide.LONG and current_price >= self.trail_activation_level) or
                (self.side == PositionSide.SHORT and current_price <= self.trail_activation_level)):
                
                self.is_trailing_activated = True
        
        # Update trailing stop if activated
        if self.is_trailing_activated and self.sl_price is not None:
            self._update_trailing_stop()
        
        # Check if TP/SL conditions are met
        sl_triggered = False
        tp_triggered = False
        
        if self.sl_price is not None:
            if ((self.side == PositionSide.LONG and current_price <= self.sl_price) or
                (self.side == PositionSide.SHORT and current_price >= self.sl_price)):
                sl_triggered = True
        
        if self.tp_price is not None:
            if ((self.side == PositionSide.LONG and current_price >= self.tp_price) or
                (self.side == PositionSide.SHORT and current_price <= self.tp_price)):
                tp_triggered = True
        
        return sl_triggered, tp_triggered
    
    def _update_trailing_stop(self):
        """
        Update trailing stop based on current price and configuration.
        """
        if not self.trail_config or self.sl_price is None:
            return
            
        callback_rate = self.trail_config.get('callback_rate', 0.3)
        
        if self.side == PositionSide.LONG:
            # For long positions, trail follows the highest price
            # New SL = Highest price - (callback rate * ATR or % distance)
            if 'current_atr' in self.trail_config and self.trail_config['current_atr'] > 0:
                atr_multiplier = self.trail_config.get('atr_multiplier', 2.0)
                distance = atr_multiplier * self.trail_config['current_atr']
            else:
                distance = (self.highest_price - self.entry_price) * callback_rate
                
            new_sl = self.highest_price - distance
            
            # Only update if new SL is higher
            if new_sl > self.sl_price:
                self.sl_price = new_sl
                self.current_sl_price = new_sl
        
        else:  # SHORT position
            # For short positions, trail follows the lowest price
            # New SL = Lowest price + (callback rate * ATR or % distance)
            if 'current_atr' in self.trail_config and self.trail_config['current_atr'] > 0:
                atr_multiplier = self.trail_config.get('atr_multiplier', 2.0)
                distance = atr_multiplier * self.trail_config['current_atr']
            else:
                distance = (self.entry_price - self.lowest_price) * callback_rate
                
            new_sl = self.lowest_price + distance
            
            # Only update if new SL is lower
            if new_sl < self.sl_price:
                self.sl_price = new_sl
                self.current_sl_price = new_sl
    
    def close_position(self, close_price: float, close_timestamp: int, realized_pnl: float):
        """
        Close the position and record the result.
        
        Args:
            close_price: Closing price
            close_timestamp: Closing timestamp (ms)
            realized_pnl: Realized profit/loss
        """
        self.close_price = close_price
        self.close_timestamp = close_timestamp
        self.realized_pnl = realized_pnl
        self.is_active = False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert position to dictionary for serialization.
        
        Returns:
            Dictionary representation of the position
        """
        return {
            'symbol': self.symbol,
            'side': self.side.value,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'quantity': self.quantity,
            'timestamp': self.timestamp,
            'position_id': self.position_id,
            'sl_price': self.sl_price,
            'current_sl_price': self.current_sl_price,
            'tp_price': self.tp_price,
            'stop_type': self.stop_type.value,
            'is_trailing_activated': self.is_trailing_activated,
            'is_breakeven_activated': self.is_breakeven_activated,
            'highest_price': self.highest_price,
            'lowest_price': self.lowest_price,
            'is_active': self.is_active,
            'close_price': self.close_price,
            'close_timestamp': self.close_timestamp,
            'realized_pnl': self.realized_pnl
        }
    
    def __str__(self) -> str:
        """String representation of the position."""
        status = "ACTIVE" if self.is_active else "CLOSED"
        return (f"Position({self.position_id}, {self.symbol}, {self.side.value}, "
                f"entry={self.entry_price}, qty={self.quantity}, status={status})")


class TPSLManager:
    """
    Manager for take-profit and stop-loss handling across all positions.
    """
    
    def __init__(self, config: Dict[str, Any], order_executor=None):
        """
        Initialize the TPSL Manager.
        
        Args:
            config: Configuration dictionary
            order_executor: Object responsible for executing orders (must have execute_order method)
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.order_executor = order_executor
        
        # Position tracking
        self.positions: Dict[str, Position] = {}  # position_id -> Position
        self.positions_by_symbol: Dict[str, List[str]] = {}  # symbol -> [position_id, ...]
        
        # Settings
        self.check_interval_ms = config.get('tpsl_manager', {}).get('check_interval_ms', 1000)
        self.max_positions_per_symbol = config.get('risk_management', {}).get('max_positions_per_symbol', 1)
        self.default_stop_type = StopType[config.get('tpsl_manager', {}).get('default_stop_type', 'TRAILING')]
        
        # Position history
        self.closed_positions: List[Dict[str, Any]] = []
        
        # Threading
        self._stop_event = threading.Event()
        self._check_thread = None
        self.lock = threading.RLock()
    
    def start(self):
        """
        Start the TPSL manager background thread.
        """
        if self._check_thread is not None and self._check_thread.is_alive():
            self.logger.warning("TPSL Manager thread already running")
            return
            
        self._stop_event.clear()
        self._check_thread = threading.Thread(target=self._check_positions_loop, daemon=True)
        self._check_thread.start()
        self.logger.info("TPSL Manager started")
    
    def stop(self):
        """
        Stop the TPSL manager background thread.
        """
        self._stop_event.set()
        if self._check_thread is not None:
            self._check_thread.join(timeout=5.0)
        self.logger.info("TPSL Manager stopped")
    
    def _check_positions_loop(self):
        """
        Background thread that checks position status and updates TP/SL.
        """
        self.logger.info("TPSL check loop starting")
        
        while not self._stop_event.is_set():
            try:
                # Get all active positions
                with self.lock:
                    active_positions = [p for p in self.positions.values() if p.is_active]
                
                # No need to check if no active positions
                if not active_positions:
                    time.sleep(self.check_interval_ms / 1000)
                    continue
                
                # Group positions by symbol for efficient market data lookup
                positions_by_symbol = {}
                for position in active_positions:
                    if position.symbol not in positions_by_symbol:
                        positions_by_symbol[position.symbol] = []
                    positions_by_symbol[position.symbol].append(position)
                
                # Process each symbol
                for symbol, symbol_positions in positions_by_symbol.items():
                    # Get current price and ATR for this symbol
                    # In a real implementation, you would get this from market data
                    # For now, we'll use a placeholder that assumes the caller updates
                    # position prices via update_market_data()
                    pass
                
            except Exception as e:
                self.logger.error(f"Error in TPSL check loop: {str(e)}", exc_info=True)
            
            # Sleep for the check interval
            time.sleep(self.check_interval_ms / 1000)
    
    def add_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        timestamp: int,
        position_id: str,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        stop_type: Optional[str] = None,
        trail_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a new position to be tracked by the TPSL manager.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            side: Position side ('LONG' or 'SHORT')
            entry_price: Average entry price
            quantity: Position size
            timestamp: Entry timestamp (ms)
            position_id: Unique ID for the position
            sl_price: Initial stop-loss price
            tp_price: Take-profit price
            stop_type: Type of stop-loss ('FIXED', 'TRAILING', 'BREAKEVEN')
            trail_config: Configuration for trailing stops
            
        Returns:
            True if the position was added, False otherwise
        """
        try:
            with self.lock:
                # Check if position already exists
                if position_id in self.positions:
                    self.logger.warning(f"Position {position_id} already exists")
                    return False
                
                # Check if we've reached the maximum positions for this symbol
                if symbol in self.positions_by_symbol:
                    active_count = sum(
                        1 for pid in self.positions_by_symbol[symbol]
                        if self.positions[pid].is_active
                    )
                    if active_count >= self.max_positions_per_symbol:
                        self.logger.warning(
                            f"Maximum active positions ({self.max_positions_per_symbol}) "
                            f"reached for {symbol}"
                        )
                        return False
                
                # Create position object
                position_side = PositionSide[side]
                position_stop_type = StopType[stop_type] if stop_type else self.default_stop_type
                
                position = Position(
                    symbol=symbol,
                    side=position_side,
                    entry_price=entry_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    position_id=position_id,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    stop_type=position_stop_type,
                    trail_config=trail_config
                )
                
                # Add to tracking collections
                self.positions[position_id] = position
                
                if symbol not in self.positions_by_symbol:
                    self.positions_by_symbol[symbol] = []
                self.positions_by_symbol[symbol].append(position_id)
                
                self.logger.info(f"Added position: {position}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error adding position: {str(e)}", exc_info=True)
            return False
    
    def update_market_data(self, symbol: str, current_price: float, atr_value: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Update market data for a symbol and check if any TP/SL conditions are met.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            current_price: Current market price
            atr_value: Current ATR value (optional)
            
        Returns:
            List of actions that need to be taken (e.g., SL hit, TP hit)
        """
        actions = []
        
        try:
            with self.lock:
                # Skip if no positions for this symbol
                if symbol not in self.positions_by_symbol:
                    return actions
                
                # Process each position for this symbol
                for position_id in self.positions_by_symbol[symbol]:
                    position = self.positions.get(position_id)
                    
                    if not position or not position.is_active:
                        continue
                    
                    # Update position with current price
                    sl_triggered, tp_triggered = position.update_price(current_price, atr_value)
                    
                    # Handle SL/TP triggers
                    if sl_triggered:
                        actions.append({
                            'action': 'STOP_LOSS',
                            'position_id': position_id,
                            'symbol': symbol,
                            'side': 'SELL' if position.side == PositionSide.LONG else 'BUY',
                            'quantity': position.quantity,
                            'price': position.sl_price,
                            'trigger_price': current_price
                        })
                        
                        # If order executor is available, execute the SL order
                        if self.order_executor:
                            self._execute_stop_loss(position, current_price)
                    
                    if tp_triggered:
                        actions.append({
                            'action': 'TAKE_PROFIT',
                            'position_id': position_id,
                            'symbol': symbol,
                            'side': 'SELL' if position.side == PositionSide.LONG else 'BUY',
                            'quantity': position.quantity,
                            'price': position.tp_price,
                            'trigger_price': current_price
                        })
                        
                        # If order executor is available, execute the TP order
                        if self.order_executor:
                            self._execute_take_profit(position, current_price)
        
        except Exception as e:
            self.logger.error(f"Error updating market data: {str(e)}", exc_info=True)
        
        return actions
    
    def _execute_stop_loss(self, position: Position, current_price: float):
        """
        Execute a stop-loss order for a position.
        
        Args:
            position: Position object
            current_price: Current market price
        """
        try:
            # Determine order side (opposite of position side)
            order_side = "SELL" if position.side == PositionSide.LONG else "BUY"
            
            # Calculate estimated PnL
            if position.side == PositionSide.LONG:
                pnl = (position.sl_price - position.entry_price) * position.quantity
            else:
                pnl = (position.entry_price - position.sl_price) * position.quantity
            
            # Execute the order using the order executor
            order_result = self.order_executor.execute_order(
                symbol=position.symbol,
                side=order_side,
                order_type="MARKET",
                quantity=position.quantity,
                price=None,  # Market order
                reduce_only=True,
                position_idx=0,  # One-way mode
                close_on_trigger=True
            )
            
            # Record the position close
            position.close_position(
                close_price=position.sl_price,
                close_timestamp=int(time.time() * 1000),
                realized_pnl=pnl
            )
            
            # Add to closed positions history
            self.closed_positions.append(position.to_dict())
            
            self.logger.info(
                f"Stop-loss executed for {position.position_id}, "
                f"price: {position.sl_price}, PnL: {pnl}"
            )
            
        except Exception as e:
            self.logger.error(f"Error executing stop-loss: {str(e)}", exc_info=True)
    
    def _execute_take_profit(self, position: Position, current_price: float):
        """
        Execute a take-profit order for a position.
        
        Args:
            position: Position object
            current_price: Current market price
        """
        try:
            # Determine order side (opposite of position side)
            order_side = "SELL" if position.side == PositionSide.LONG else "BUY"
            
            # Calculate estimated PnL
            if position.side == PositionSide.LONG:
                pnl = (position.tp_price - position.entry_price) * position.quantity
            else:
                pnl = (position.entry_price - position.tp_price) * position.quantity
            
            # Execute the order using the order executor
            order_result = self.order_executor.execute_order(
                symbol=position.symbol,
                side=order_side,
                order_type="MARKET",
                quantity=position.quantity,
                price=None,  # Market order
                reduce_only=True,
                position_idx=0,  # One-way mode
                close_on_trigger=True
            )
            
            # Record the position close
            position.close_position(
                close_price=position.tp_price,
                close_timestamp=int(time.time() * 1000),
                realized_pnl=pnl
            )
            
            # Add to closed positions history
            self.closed_positions.append(position.to_dict())
            
            self.logger.info(
                f"Take-profit executed for {position.position_id}, "
                f"price: {position.tp_price}, PnL: {pnl}"
            )
            
        except Exception as e:
            self.logger.error(f"Error executing take-profit: {str(e)}", exc_info=True)
    
    def update_position(self, position_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing position's parameters.
        
        Args:
            position_id: Unique ID of the position to update
            updates: Dictionary of attributes to update
            
        Returns:
            True if the position was updated, False otherwise
        """
        try:
            with self.lock:
                # Check if position exists
                if position_id not in self.positions:
                    self.logger.warning(f"Cannot update position {position_id}: not found")
                    return False
                
                position = self.positions[position_id]
                
                # Update attributes
                for attr, value in updates.items():
                    if hasattr(position, attr) and attr not in ['symbol', 'position_id', 'side']:
                        setattr(position, attr, value)
                
                self.logger.info(f"Updated position {position_id}: {updates}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating position: {str(e)}", exc_info=True)
            return False
    
    def close_position(self, position_id: str, close_price: float, close_timestamp: int, realized_pnl: float) -> bool:
        """
        Mark a position as closed (e.g., when closed externally).
        
        Args:
            position_id: Unique ID of the position to close
            close_price: Closing price
            close_timestamp: Closing timestamp (ms)
            realized_pnl: Realized profit/loss
            
        Returns:
            True if the position was closed, False otherwise
        """
        try:
            with self.lock:
                # Check if position exists
                if position_id not in self.positions:
                    self.logger.warning(f"Cannot close position {position_id}: not found")
                    return False
                
                position = self.positions[position_id]
                
                # Close the position
                position.close_position(close_price, close_timestamp, realized_pnl)
                
                # Add to closed positions history
                self.closed_positions.append(position.to_dict())
                
                self.logger.info(
                    f"Position {position_id} closed, "
                    f"price: {close_price}, PnL: {realized_pnl}"
                )
                return True
                
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}", exc_info=True)
            return False
    
    def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a position by ID.
        
        Args:
            position_id: Unique ID of the position
            
        Returns:
            Position data as dictionary or None if not found
        """
        with self.lock:
            position = self.positions.get(position_id)
            return position.to_dict() if position else None
    
    def get_active_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all active positions, optionally filtered by symbol.
        
        Args:
            symbol: Trading symbol to filter by (optional)
            
        Returns:
            List of active position data
        """
        with self.lock:
            if symbol:
                # Get positions for a specific symbol
                if symbol not in self.positions_by_symbol:
                    return []
                
                position_ids = self.positions_by_symbol[symbol]
                return [
                    self.positions[pid].to_dict()
                    for pid in position_ids
                    if pid in self.positions and self.positions[pid].is_active
                ]
            else:
                # Get all active positions
                return [
                    p.to_dict()
                    for p in self.positions.values()
                    if p.is_active
                ]
    
    def get_closed_positions(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get closed position history, optionally filtered by symbol.
        
        Args:
            symbol: Trading symbol to filter by (optional)
            limit: Maximum number of positions to return
            
        Returns:
            List of closed position data
        """
        with self.lock:
            # Filter by symbol if provided
            if symbol:
                filtered = [p for p in self.closed_positions if p['symbol'] == symbol]
            else:
                filtered = self.closed_positions
            
            # Sort by close timestamp (most recent first) and apply limit
            return sorted(filtered, key=lambda p: p.get('close_timestamp', 0), reverse=True)[:limit]
    
    def get_position_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get position statistics, optionally filtered by symbol.
        
        Args:
            symbol: Trading symbol to filter by (optional)
            
        Returns:
            Dictionary of position statistics
        """
        with self.lock:
            # Get positions to analyze
            if symbol:
                if symbol not in self.positions_by_symbol:
                    return {
                        'active_count': 0,
                        'closed_count': 0,
                        'win_count': 0,
                        'loss_count': 0,
                        'win_rate': 0.0,
                        'total_pnl': 0.0,
                        'average_pnl': 0.0
                    }
                
                active_positions = [
                    self.positions[pid] for pid in self.positions_by_symbol[symbol]
                    if pid in self.positions and self.positions[pid].is_active
                ]
                
                closed_positions = [
                    p for p in self.closed_positions
                    if p['symbol'] == symbol
                ]
            else:
                active_positions = [p for p in self.positions.values() if p.is_active]
                closed_positions = self.closed_positions
            
            # Calculate statistics
            active_count = len(active_positions)
            closed_count = len(closed_positions)
            
            # PnL analysis
            total_pnl = sum(p.get('realized_pnl', 0.0) for p in closed_positions)
            average_pnl = total_pnl / closed_count if closed_count > 0 else 0.0
            
            win_count = sum(1 for p in closed_positions if p.get('realized_pnl', 0.0) > 0)
            loss_count = sum(1 for p in closed_positions if p.get('realized_pnl', 0.0) <= 0)
            win_rate = win_count / closed_count if closed_count > 0 else 0.0
            
            return {
                'active_count': active_count,
                'closed_count': closed_count,
                'win_count': win_count,
                'loss_count': loss_count,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'average_pnl': average_pnl
            }
    
    def export_positions_history(self, filepath: str) -> bool:
        """
        Export position history to a CSV file.
        
        Args:
            filepath: Path to the output CSV file
            
        Returns:
            True if the export was successful, False otherwise
        """
        try:
            with self.lock:
                # Convert to DataFrame
                df = pd.DataFrame(self.closed_positions)
                
                # Add additional columns for analysis
                if not df.empty:
                    df['duration_ms'] = df['close_timestamp'] - df['timestamp']
                    df['duration_minutes'] = df['duration_ms'] / (1000 * 60)
                    df['return_pct'] = df.apply(
                        lambda row: (
                            (row['close_price'] - row['entry_price']) / row['entry_price'] * 100
                            if row['side'] == 'LONG' else
                            (row['entry_price'] - row['close_price']) / row['entry_price'] * 100
                        ),
                        axis=1
                    )
                
                # Save to CSV
                df.to_csv(filepath, index=False)
                self.logger.info(f"Exported {len(df)} positions to {filepath}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error exporting positions: {str(e)}", exc_info=True)
            return False