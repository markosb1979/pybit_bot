"""
TPSL (Take-Profit/Stop-Loss) Manager 
Handles the placement and management of take-profit and stop-loss orders.
Implements OCO (One-Cancels-Other) functionality and trailing stops.
"""

import time
import logging
from typing import Dict, List, Optional, Union, Tuple
from enum import Enum
from threading import Thread, Event
import json


class OrderStatus(Enum):
    """Enum for the status of orders managed by TPSLManager"""
    PENDING = "PENDING"          # Entry order placed but not filled
    ACTIVE = "ACTIVE"            # Entry filled, TP/SL orders active
    COMPLETED = "COMPLETED"      # Position closed via TP or SL
    CANCELLED = "CANCELLED"      # Position cancelled before entry
    MANUAL_EXIT = "MANUAL_EXIT"  # Position closed manually


class TPSLPair:
    """
    Represents a pair of take-profit and stop-loss orders
    associated with an entry order.
    """
    
    def __init__(
        self,
        entry_order_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        trailing_stop: bool = False,
        trail_activation_pct: float = 0.5,
        trail_atr_mult: float = 2.0
    ):
        """
        Initialize a TPSL pair.
        
        Args:
            entry_order_id: ID of the entry order
            symbol: Trading symbol
            side: Order side ('Buy' or 'Sell')
            entry_price: Entry price
            quantity: Position size
            sl_price: Stop-loss price (optional)
            tp_price: Take-profit price (optional)
            trailing_stop: Whether to use trailing stop
            trail_activation_pct: Percentage of TP distance to activate trailing stop
            trail_atr_mult: ATR multiplier for trailing stop distance
        """
        self.entry_order_id = entry_order_id
        self.symbol = symbol
        self.side = side  # 'Buy' for long, 'Sell' for short
        self.entry_price = entry_price
        self.quantity = quantity
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.trailing_stop = trailing_stop
        self.trail_activation_pct = trail_activation_pct
        self.trail_atr_mult = trail_atr_mult
        
        # Order IDs
        self.tp_order_id: Optional[str] = None
        self.sl_order_id: Optional[str] = None
        
        # Trailing stop state
        self.is_trailing_active = False
        self.current_trail_price: Optional[float] = None
        
        # Status tracking
        self.status = OrderStatus.PENDING
        self.exit_price: Optional[float] = None
        self.exit_order_id: Optional[str] = None
        self.exit_timestamp: Optional[int] = None
        self.pnl: Optional[float] = None
        
        # Timestamps
        self.created_at = int(time.time() * 1000)
        self.filled_at: Optional[int] = None
        
        # Retry tracking
        self.tp_placement_attempts = 0
        self.sl_placement_attempts = 0
    
    def to_dict(self) -> Dict:
        """
        Convert TPSLPair to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the TPSLPair
        """
        return {
            'entry_order_id': self.entry_order_id,
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'sl_price': self.sl_price,
            'tp_price': self.tp_price,
            'trailing_stop': self.trailing_stop,
            'trail_activation_pct': self.trail_activation_pct,
            'trail_atr_mult': self.trail_atr_mult,
            'tp_order_id': self.tp_order_id,
            'sl_order_id': self.sl_order_id,
            'is_trailing_active': self.is_trailing_active,
            'current_trail_price': self.current_trail_price,
            'status': self.status.value,
            'exit_price': self.exit_price,
            'exit_order_id': self.exit_order_id,
            'exit_timestamp': self.exit_timestamp,
            'pnl': self.pnl,
            'created_at': self.created_at,
            'filled_at': self.filled_at,
            'tp_placement_attempts': self.tp_placement_attempts,
            'sl_placement_attempts': self.sl_placement_attempts
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TPSLPair':
        """
        Create a TPSLPair from a dictionary.
        
        Args:
            data: Dictionary containing TPSLPair data
            
        Returns:
            TPSLPair instance
        """
        tpsl = cls(
            entry_order_id=data['entry_order_id'],
            symbol=data['symbol'],
            side=data['side'],
            entry_price=data['entry_price'],
            quantity=data['quantity'],
            sl_price=data.get('sl_price'),
            tp_price=data.get('tp_price'),
            trailing_stop=data.get('trailing_stop', False),
            trail_activation_pct=data.get('trail_activation_pct', 0.5),
            trail_atr_mult=data.get('trail_atr_mult', 2.0)
        )
        
        # Restore additional fields
        tpsl.tp_order_id = data.get('tp_order_id')
        tpsl.sl_order_id = data.get('sl_order_id')
        tpsl.is_trailing_active = data.get('is_trailing_active', False)
        tpsl.current_trail_price = data.get('current_trail_price')
        tpsl.status = OrderStatus(data.get('status', 'PENDING'))
        tpsl.exit_price = data.get('exit_price')
        tpsl.exit_order_id = data.get('exit_order_id')
        tpsl.exit_timestamp = data.get('exit_timestamp')
        tpsl.pnl = data.get('pnl')
        tpsl.created_at = data.get('created_at', int(time.time() * 1000))
        tpsl.filled_at = data.get('filled_at')
        tpsl.tp_placement_attempts = data.get('tp_placement_attempts', 0)
        tpsl.sl_placement_attempts = data.get('sl_placement_attempts', 0)
        
        return tpsl


class TPSLManager:
    """
    Manager for take-profit and stop-loss orders.
    Handles OCO order placement and management.
    """
    
    def __init__(
        self,
        config: Dict,
        order_manager,
        data_manager,
        state_persistence=None
    ):
        """
        Initialize the TPSL manager.
        
        Args:
            config: Configuration dictionary
            order_manager: OrderManager instance
            data_manager: DataManager instance
            state_persistence: StatePersistence instance (optional)
        """
        self.config = config
        self.order_manager = order_manager
        self.data_manager = data_manager
        self.state_persistence = state_persistence
        
        self.logger = logging.getLogger(__name__)
        
        # TPSL tracking
        self.active_tpsl_pairs: Dict[str, TPSLPair] = {}  # entry_order_id -> TPSLPair
        self.completed_tpsl_pairs: Dict[str, TPSLPair] = {}  # entry_order_id -> TPSLPair
        
        # Thread control
        self.running = False
        self.stop_event = Event()
        self.tpsl_thread = None
        self.check_interval = self.config.get('tpsl_check_interval', 5)  # seconds
        
        # Retry configuration
        self.max_placement_attempts = self.config.get('max_placement_attempts', 3)
        self.retry_delay = self.config.get('retry_delay', 5)  # seconds
    
    def register_entry_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        trailing_stop: bool = False,
        trail_activation_pct: float = 0.5,
        trail_atr_mult: float = 2.0
    ) -> bool:
        """
        Register an entry order to be managed by TPSL manager.
        
        Args:
            order_id: Entry order ID
            symbol: Trading symbol
            side: Order side ('Buy' or 'Sell')
            entry_price: Entry price
            quantity: Position size
            sl_price: Stop-loss price (optional)
            tp_price: Take-profit price (optional)
            trailing_stop: Whether to use trailing stop
            trail_activation_pct: Percentage of TP distance to activate trailing stop
            trail_atr_mult: ATR multiplier for trailing stop distance
            
        Returns:
            Boolean indicating success
        """
        if order_id in self.active_tpsl_pairs:
            self.logger.warning(f"Order {order_id} already registered with TPSL manager")
            return False
        
        # Create new TPSL pair
        tpsl_pair = TPSLPair(
            entry_order_id=order_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            sl_price=sl_price,
            tp_price=tp_price,
            trailing_stop=trailing_stop,
            trail_activation_pct=trail_activation_pct,
            trail_atr_mult=trail_atr_mult
        )
        
        # Add to active pairs
        self.active_tpsl_pairs[order_id] = tpsl_pair
        self.logger.info(f"Registered entry order {order_id} with TPSL manager")
        
        # Save state
        self._save_state()
        
        return True
    
    def handle_order_filled(self, order_id: str, fill_price: float, timestamp: int) -> None:
        """
        Handle an order being filled.
        
        Args:
            order_id: Order ID that was filled
            fill_price: Price at which the order was filled
            timestamp: Timestamp of the fill
        """
        # Check if this is an entry order we're tracking
        if order_id in self.active_tpsl_pairs:
            tpsl_pair = self.active_tpsl_pairs[order_id]
            tpsl_pair.status = OrderStatus.ACTIVE
            tpsl_pair.filled_at = timestamp
            
            # Update entry price with actual fill price
            tpsl_pair.entry_price = fill_price
            
            # Place TP/SL orders
            self._place_tpsl_orders(tpsl_pair)
            
            self.logger.info(f"Entry order {order_id} filled at {fill_price}")
            self._save_state()
            return
        
        # Check if this is a TP or SL order
        for entry_id, tpsl_pair in list(self.active_tpsl_pairs.items()):
            if order_id == tpsl_pair.tp_order_id:
                # Take profit hit
                self._handle_tp_fill(tpsl_pair, fill_price, timestamp)
                return
            
            if order_id == tpsl_pair.sl_order_id:
                # Stop loss hit
                self._handle_sl_fill(tpsl_pair, fill_price, timestamp)
                return
    
    def handle_order_cancelled(self, order_id: str) -> None:
        """
        Handle an order being cancelled.
        
        Args:
            order_id: Order ID that was cancelled
        """
        # Check if this is an entry order we're tracking
        if order_id in self.active_tpsl_pairs:
            tpsl_pair = self.active_tpsl_pairs[order_id]
            tpsl_pair.status = OrderStatus.CANCELLED
            
            # Move to completed pairs
            self.completed_tpsl_pairs[order_id] = tpsl_pair
            del self.active_tpsl_pairs[order_id]
            
            self.logger.info(f"Entry order {order_id} cancelled")
            self._save_state()
            return
    
    def handle_manual_exit(self, symbol: str, side: str, order_id: str) -> None:
        """
        Handle a manual exit of a position.
        
        Args:
            symbol: Trading symbol
            side: Order side ('Buy' or 'Sell')
            order_id: Order ID of the exit order
        """
        # Find the TPSL pair for this symbol and opposite side
        for entry_id, tpsl_pair in list(self.active_tpsl_pairs.items()):
            if tpsl_pair.symbol == symbol and tpsl_pair.status == OrderStatus.ACTIVE:
                # Check if the exit side is opposite to the entry side
                entry_is_long = tpsl_pair.side == "Buy"
                exit_is_sell = side == "Sell"
                
                if (entry_is_long and exit_is_sell) or (not entry_is_long and not exit_is_sell):
                    # This is a manual exit for this position
                    tpsl_pair.status = OrderStatus.MANUAL_EXIT
                    tpsl_pair.exit_order_id = order_id
                    
                    # Cancel any active TP/SL orders
                    self._cancel_tpsl_orders(tpsl_pair)
                    
                    # Move to completed pairs
                    self.completed_tpsl_pairs[entry_id] = tpsl_pair
                    del self.active_tpsl_pairs[entry_id]
                    
                    self.logger.info(f"Position for {symbol} manually exited")
                    self._save_state()
                    return
    
    def update_trailing_stops(self, current_prices: Dict[str, float], atr_values: Dict[str, float]) -> None:
        """
        Update trailing stops for all active positions.
        
        Args:
            current_prices: Dictionary of current prices (symbol -> price)
            atr_values: Dictionary of current ATR values (symbol -> atr)
        """
        for tpsl_pair in self.active_tpsl_pairs.values():
            if (tpsl_pair.status != OrderStatus.ACTIVE or 
                not tpsl_pair.trailing_stop or 
                tpsl_pair.symbol not in current_prices):
                continue
            
            current_price = current_prices[tpsl_pair.symbol]
            atr = atr_values.get(tpsl_pair.symbol, 0)
            
            # Check if trailing stop should be activated
            if not tpsl_pair.is_trailing_active:
                # Calculate activation threshold
                if tpsl_pair.side == "Buy":  # Long position
                    # TP is above entry
                    if tpsl_pair.tp_price is None:
                        continue
                    
                    activation_price = tpsl_pair.entry_price + (
                        (tpsl_pair.tp_price - tpsl_pair.entry_price) * tpsl_pair.trail_activation_pct
                    )
                    
                    if current_price >= activation_price:
                        # Activate trailing stop
                        tpsl_pair.is_trailing_active = True
                        tpsl_pair.current_trail_price = current_price - (atr * tpsl_pair.trail_atr_mult)
                        self.logger.info(f"Activated trailing stop for {tpsl_pair.symbol} at {tpsl_pair.current_trail_price}")
                
                else:  # Short position
                    # TP is below entry
                    if tpsl_pair.tp_price is None:
                        continue
                    
                    activation_price = tpsl_pair.entry_price - (
                        (tpsl_pair.entry_price - tpsl_pair.tp_price) * tpsl_pair.trail_activation_pct
                    )
                    
                    if current_price <= activation_price:
                        # Activate trailing stop
                        tpsl_pair.is_trailing_active = True
                        tpsl_pair.current_trail_price = current_price + (atr * tpsl_pair.trail_atr_mult)
                        self.logger.info(f"Activated trailing stop for {tpsl_pair.symbol} at {tpsl_pair.current_trail_price}")
            
            # Update trailing stop if active
            if tpsl_pair.is_trailing_active and tpsl_pair.current_trail_price is not None:
                if tpsl_pair.side == "Buy":  # Long position
                    # Move stop up if price increases
                    new_stop = current_price - (atr * tpsl_pair.trail_atr_mult)
                    if new_stop > tpsl_pair.current_trail_price:
                        tpsl_pair.current_trail_price = new_stop
                        # Update stop order
                        self._update_stop_order(tpsl_pair)
                
                else:  # Short position
                    # Move stop down if price decreases
                    new_stop = current_price + (atr * tpsl_pair.trail_atr_mult)
                    if new_stop < tpsl_pair.current_trail_price:
                        tpsl_pair.current_trail_price = new_stop
                        # Update stop order
                        self._update_stop_order(tpsl_pair)
        
        # Save state after updates
        self._save_state()
    
    def _place_tpsl_orders(self, tpsl_pair: TPSLPair) -> None:
        """
        Place take-profit and stop-loss orders for a filled entry.
        
        Args:
            tpsl_pair: TPSLPair instance
        """
        # Place take-profit order if specified
        if tpsl_pair.tp_price is not None:
            self._place_tp_order(tpsl_pair)
        
        # Place stop-loss order if specified
        if tpsl_pair.sl_price is not None or (tpsl_pair.trailing_stop and tpsl_pair.is_trailing_active):
            self._place_sl_order(tpsl_pair)
    
    def _place_tp_order(self, tpsl_pair: TPSLPair) -> bool:
        """
        Place a take-profit order.
        
        Args:
            tpsl_pair: TPSLPair instance
            
        Returns:
            Boolean indicating success
        """
        if tpsl_pair.tp_placement_attempts >= self.max_placement_attempts:
            self.logger.error(f"Max TP placement attempts reached for {tpsl_pair.entry_order_id}")
            return False
        
        # Determine order side (opposite of entry)
        side = "Sell" if tpsl_pair.side == "Buy" else "Buy"
        
        try:
            # Place limit order at TP price
            order_result = self.order_manager.place_limit_order(
                symbol=tpsl_pair.symbol,
                side=side,
                quantity=tpsl_pair.quantity,
                price=tpsl_pair.tp_price,
                reduce_only=True
            )
            
            if order_result and 'order_id' in order_result:
                tpsl_pair.tp_order_id = order_result['order_id']
                self.logger.info(f"Placed TP order {tpsl_pair.tp_order_id} at {tpsl_pair.tp_price}")
                return True
            else:
                tpsl_pair.tp_placement_attempts += 1
                self.logger.warning(f"Failed to place TP order, attempt {tpsl_pair.tp_placement_attempts}")
                return False
                
        except Exception as e:
            tpsl_pair.tp_placement_attempts += 1
            self.logger.error(f"Error placing TP order: {str(e)}")
            return False
    
    def _place_sl_order(self, tpsl_pair: TPSLPair) -> bool:
        """
        Place a stop-loss order.
        
        Args:
            tpsl_pair: TPSLPair instance
            
        Returns:
            Boolean indicating success
        """
        if tpsl_pair.sl_placement_attempts >= self.max_placement_attempts:
            self.logger.error(f"Max SL placement attempts reached for {tpsl_pair.entry_order_id}")
            return False
        
        # Determine order side (opposite of entry)
        side = "Sell" if tpsl_pair.side == "Buy" else "Buy"
        
        # Determine stop price
        stop_price = tpsl_pair.current_trail_price if tpsl_pair.is_trailing_active else tpsl_pair.sl_price
        
        if stop_price is None:
            self.logger.error(f"No stop price available for {tpsl_pair.entry_order_id}")
            return False
        
        try:
            # Place stop market order
            order_result = self.order_manager.place_stop_market_order(
                symbol=tpsl_pair.symbol,
                side=side,
                quantity=tpsl_pair.quantity,
                stop_price=stop_price,
                reduce_only=True
            )
            
            if order_result and 'order_id' in order_result:
                tpsl_pair.sl_order_id = order_result['order_id']
                self.logger.info(f"Placed SL order {tpsl_pair.sl_order_id} at {stop_price}")
                return True
            else:
                tpsl_pair.sl_placement_attempts += 1
                self.logger.warning(f"Failed to place SL order, attempt {tpsl_pair.sl_placement_attempts}")
                return False
                
        except Exception as e:
            tpsl_pair.sl_placement_attempts += 1
            self.logger.error(f"Error placing SL order: {str(e)}")
            return False
    
    def _update_stop_order(self, tpsl_pair: TPSLPair) -> bool:
        """
        Update a stop-loss order for trailing stop.
        
        Args:
            tpsl_pair: TPSLPair instance
            
        Returns:
            Boolean indicating success
        """
        if not tpsl_pair.sl_order_id or not tpsl_pair.current_trail_price:
            return False
        
        try:
            # Cancel existing stop order
            cancel_result = self.order_manager.cancel_order(
                symbol=tpsl_pair.symbol,
                order_id=tpsl_pair.sl_order_id
            )
            
            if not cancel_result:
                self.logger.warning(f"Failed to cancel existing SL order {tpsl_pair.sl_order_id}")
                return False
            
            # Place new stop order at updated price
            side = "Sell" if tpsl_pair.side == "Buy" else "Buy"
            
            order_result = self.order_manager.place_stop_market_order(
                symbol=tpsl_pair.symbol,
                side=side,
                quantity=tpsl_pair.quantity,
                stop_price=tpsl_pair.current_trail_price,
                reduce_only=True
            )
            
            if order_result and 'order_id' in order_result:
                tpsl_pair.sl_order_id = order_result['order_id']
                self.logger.info(f"Updated trailing stop to {tpsl_pair.current_trail_price}")
                return True
            else:
                self.logger.warning(f"Failed to place updated SL order")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating stop order: {str(e)}")
            return False
    
    def _handle_tp_fill(self, tpsl_pair: TPSLPair, fill_price: float, timestamp: int) -> None:
        """
        Handle a take-profit order being filled.
        
        Args:
            tpsl_pair: TPSLPair instance
            fill_price: Fill price
            timestamp: Fill timestamp
        """
        # Update TPSL pair
        tpsl_pair.status = OrderStatus.COMPLETED
        tpsl_pair.exit_price = fill_price
        tpsl_pair.exit_timestamp = timestamp
        
        # Calculate PnL
        if tpsl_pair.side == "Buy":  # Long position
            tpsl_pair.pnl = (fill_price - tpsl_pair.entry_price) * tpsl_pair.quantity
        else:  # Short position
            tpsl_pair.pnl = (tpsl_pair.entry_price - fill_price) * tpsl_pair.quantity
        
        # Cancel stop-loss order
        if tpsl_pair.sl_order_id:
            self.order_manager.cancel_order(
                symbol=tpsl_pair.symbol,
                order_id=tpsl_pair.sl_order_id
            )
        
        # Move to completed pairs
        self.completed_tpsl_pairs[tpsl_pair.entry_order_id] = tpsl_pair
        del self.active_tpsl_pairs[tpsl_pair.entry_order_id]
        
        self.logger.info(f"TP hit for {tpsl_pair.symbol} at {fill_price}, PnL: {tpsl_pair.pnl}")
        self._save_state()
    
    def _handle_sl_fill(self, tpsl_pair: TPSLPair, fill_price: float, timestamp: int) -> None:
        """
        Handle a stop-loss order being filled.
        
        Args:
            tpsl_pair: TPSLPair instance
            fill_price: Fill price
            timestamp: Fill timestamp
        """
        # Update TPSL pair
        tpsl_pair.status = OrderStatus.COMPLETED
        tpsl_pair.exit_price = fill_price
        tpsl_pair.exit_timestamp = timestamp
        
        # Calculate PnL
        if tpsl_pair.side == "Buy":  # Long position
            tpsl_pair.pnl = (fill_price - tpsl_pair.entry_price) * tpsl_pair.quantity
        else:  # Short position
            tpsl_pair.pnl = (tpsl_pair.entry_price - fill_price) * tpsl_pair.quantity
        
        # Cancel take-profit order
        if tpsl_pair.tp_order_id:
            self.order_manager.cancel_order(
                symbol=tpsl_pair.symbol,
                order_id=tpsl_pair.tp_order_id
            )
        
        # Move to completed pairs
        self.completed_tpsl_pairs[tpsl_pair.entry_order_id] = tpsl_pair
        del self.active_tpsl_pairs[tpsl_pair.entry_order_id]
        
        self.logger.info(f"SL hit for {tpsl_pair.symbol} at {fill_price}, PnL: {tpsl_pair.pnl}")
        self._save_state()
    
    def _cancel_tpsl_orders(self, tpsl_pair: TPSLPair) -> None:
        """
        Cancel both take-profit and stop-loss orders.
        
        Args:
            tpsl_pair: TPSLPair instance
        """
        # Cancel take-profit order
        if tpsl_pair.tp_order_id:
            self.order_manager.cancel_order(
                symbol=tpsl_pair.symbol,
                order_id=tpsl_pair.tp_order_id
            )
            tpsl_pair.tp_order_id = None
        
        # Cancel stop-loss order
        if tpsl_pair.sl_order_id:
            self.order_manager.cancel_order(
                symbol=tpsl_pair.symbol,
                order_id=tpsl_pair.sl_order_id
            )
            tpsl_pair.sl_order_id = None
    
    def _save_state(self) -> None:
        """
        Save current state to persistence.
        """
        if not self.state_persistence:
            return
        
        state = {
            'active_tpsl_pairs': {
                order_id: tpsl_pair.to_dict() 
                for order_id, tpsl_pair in self.active_tpsl_pairs.items()
            },
            'completed_tpsl_pairs': {
                order_id: tpsl_pair.to_dict() 
                for order_id, tpsl_pair in self.completed_tpsl_pairs.items()
            },
            'timestamp': int(time.time())
        }
        
        self.state_persistence.save_state('tpsl_manager', state)
    
    def restore_state(self) -> None:
        """
        Restore state from persistence.
        """
        if not self.state_persistence:
            return
        
        state = self.state_persistence.load_state('tpsl_manager')
        if not state:
            self.logger.info("No TPSL state to restore")
            return
        
        # Restore active TPSL pairs
        for order_id, tpsl_data in state.get('active_tpsl_pairs', {}).items():
            self.active_tpsl_pairs[order_id] = TPSLPair.from_dict(tpsl_data)
        
        # Restore completed TPSL pairs
        for order_id, tpsl_data in state.get('completed_tpsl_pairs', {}).items():
            self.completed_tpsl_pairs[order_id] = TPSLPair.from_dict(tpsl_data)
        
        self.logger.info(f"Restored TPSL manager state from {state.get('timestamp', 'unknown')}")
    
    def start(self) -> None:
        """
        Start the TPSL manager loop in a separate thread.
        """
        if self.running:
            self.logger.warning("TPSL manager is already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.tpsl_thread = Thread(target=self._tpsl_loop, daemon=True)
        self.tpsl_thread.start()
        self.logger.info("TPSL manager started")
    
    def stop(self) -> None:
        """
        Stop the TPSL manager loop.
        """
        if not self.running:
            return
        
        self.logger.info("Stopping TPSL manager")
        self.running = False
        self.stop_event.set()
        
        if self.tpsl_thread and self.tpsl_thread.is_alive():
            self.tpsl_thread.join(timeout=5.0)
        
        # Save final state
        self._save_state()
    
    def _tpsl_loop(self) -> None:
        """
        Main loop for the TPSL manager.
        Periodically checks for order updates and updates trailing stops.
        """
        self.logger.info("TPSL loop started")
        
        while not self.stop_event.is_set() and self.running:
            try:
                # Get current prices and ATR values for symbols with active positions
                symbols = {tpsl.symbol for tpsl in self.active_tpsl_pairs.values()}
                
                if symbols:
                    # Get current prices
                    current_prices = {}
                    atr_values = {}
                    
                    for symbol in symbols:
                        # Get latest ticker
                        ticker = self.data_manager.get_ticker(symbol)
                        if ticker and 'last_price' in ticker:
                            current_prices[symbol] = float(ticker['last_price'])
                        
                        # Get latest ATR for trailing stop calculations
                        df = self.data_manager.get_candles(
                            symbol=symbol,
                            interval='1m',
                            limit=20
                        )
                        
                        if df is not None and not df.empty:
                            from indicators.atr import calculate_atr
                            atr = calculate_atr(df, length=14).iloc[-1]
                            atr_values[symbol] = atr
                    
                    # Update trailing stops
                    self.update_trailing_stops(current_prices, atr_values)
                
                # Retry any failed TP/SL placements
                self._retry_failed_placements()
                
            except Exception as e:
                self.logger.error(f"Error in TPSL loop: {str(e)}", exc_info=True)
            
            # Sleep until next check
            time.sleep(self.check_interval)
        
        self.logger.info("TPSL loop stopped")
    
    def _retry_failed_placements(self) -> None:
        """
        Retry placing any failed TP/SL orders.
        """
        for tpsl_pair in self.active_tpsl_pairs.values():
            if tpsl_pair.status != OrderStatus.ACTIVE:
                continue
            
            # Retry TP placement if needed
            if tpsl_pair.tp_price is not None and tpsl_pair.tp_order_id is None:
                if tpsl_pair.tp_placement_attempts < self.max_placement_attempts:
                    self._place_tp_order(tpsl_pair)
            
            # Retry SL placement if needed
            if ((tpsl_pair.sl_price is not None or 
                (tpsl_pair.trailing_stop and tpsl_pair.is_trailing_active)) and 
                tpsl_pair.sl_order_id is None):
                if tpsl_pair.sl_placement_attempts < self.max_placement_attempts:
                    self._place_sl_order(tpsl_pair)