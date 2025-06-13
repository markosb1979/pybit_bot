"""
Position simulator for backtesting.
Simulates position management including entries, exits, and TPSL.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from datetime import datetime


class PositionState(Enum):
    """Position state enumeration."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELED = "CANCELED"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    TAKE_PROFIT = "TAKE_PROFIT"


class ExitReason(Enum):
    """Exit reason enumeration."""
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    MANUAL = "MANUAL"
    EXPIRED = "EXPIRED"


class Position:
    """
    Simulated trading position for backtesting.
    """
    
    def __init__(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        entry_time: datetime,
        quantity: float,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        use_trailing_stop: bool = False,
        trailing_stop_activation_pct: float = 0.5,
        trailing_stop_callback_rate: float = 0.3,
        position_id: Optional[str] = None
    ):
        """
        Initialize a simulated position.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            side: Position side ('LONG' or 'SHORT')
            entry_price: Entry price
            entry_time: Entry timestamp
            quantity: Position size
            sl_price: Stop-loss price
            tp_price: Take-profit price
            use_trailing_stop: Whether to use trailing stop
            trailing_stop_activation_pct: Activation threshold for trailing stop
            trailing_stop_callback_rate: Callback rate for trailing stop
            position_id: Unique position ID (optional)
        """
        self.symbol = symbol
        self.side = side.upper()
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.quantity = quantity
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.use_trailing_stop = use_trailing_stop
        self.trailing_stop_activation_pct = trailing_stop_activation_pct
        self.trailing_stop_callback_rate = trailing_stop_callback_rate
        self.position_id = position_id or f"{symbol}_{side}_{entry_time.timestamp()}"
        
        # Position state tracking
        self.state = PositionState.OPEN
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        
        # Trailing stop tracking
        self.trailing_stop_activated = False
        self.current_stop_price = sl_price
        self.peak_price = entry_price
        self.trailing_activation_price = self._calculate_trailing_activation_price()
        
        # Performance tracking
        self.realized_pnl = 0.0
        self.max_favorable_excursion = 0.0
        self.max_adverse_excursion = 0.0
    
    def _calculate_trailing_activation_price(self) -> Optional[float]:
        """
        Calculate the price at which trailing stop activates.
        
        Returns:
            Activation price or None if trailing stop not configured
        """
        if not self.use_trailing_stop or not self.tp_price:
            return None
            
        tp_distance = abs(self.tp_price - self.entry_price)
        
        if self.side == "LONG":
            return self.entry_price + (tp_distance * self.trailing_stop_activation_pct)
        else:  # SHORT
            return self.entry_price - (tp_distance * self.trailing_stop_activation_pct)
    
    def update(self, price: float, timestamp: datetime) -> Optional[Dict[str, Any]]:
        """
        Update the position with a new price.
        
        Args:
            price: Current price
            timestamp: Current timestamp
            
        Returns:
            Exit information if the position is closed, None otherwise
        """
        if self.state != PositionState.OPEN:
            return None
            
        # Update favorable/adverse excursion
        if self.side == "LONG":
            unrealized_pnl = (price - self.entry_price) / self.entry_price
            if price > self.peak_price:
                self.peak_price = price
        else:  # SHORT
            unrealized_pnl = (self.entry_price - price) / self.entry_price
            if price < self.peak_price:
                self.peak_price = price
                
        self.max_favorable_excursion = max(self.max_favorable_excursion, unrealized_pnl if unrealized_pnl > 0 else 0)
        self.max_adverse_excursion = max(self.max_adverse_excursion, -unrealized_pnl if unrealized_pnl < 0 else 0)
        
        # Check trailing stop activation
        if self.use_trailing_stop and not self.trailing_stop_activated and self.trailing_activation_price:
            if ((self.side == "LONG" and price >= self.trailing_activation_price) or
                (self.side == "SHORT" and price <= self.trailing_activation_price)):
                self.trailing_stop_activated = True
        
        # Update trailing stop if activated
        if self.trailing_stop_activated and self.current_stop_price:
            if self.side == "LONG":
                # For longs, trail the stop up as price increases
                price_movement = price - self.peak_price
                if price > self.peak_price:
                    self.peak_price = price
                    
                    # Calculate the new stop price
                    trail_distance = price * self.trailing_stop_callback_rate
                    new_stop = price - trail_distance
                    
                    # Only move the stop up, never down
                    if new_stop > self.current_stop_price:
                        self.current_stop_price = new_stop
            else:  # SHORT
                # For shorts, trail the stop down as price decreases
                if price < self.peak_price:
                    self.peak_price = price
                    
                    # Calculate the new stop price
                    trail_distance = price * self.trailing_stop_callback_rate
                    new_stop = price + trail_distance
                    
                    # Only move the stop down, never up
                    if new_stop < self.current_stop_price:
                        self.current_stop_price = new_stop
        
        # Check for exit conditions
        exit_info = None
        
        # Check take profit
        if self.tp_price:
            if ((self.side == "LONG" and price >= self.tp_price) or
                (self.side == "SHORT" and price <= self.tp_price)):
                exit_info = self._close_position(self.tp_price, timestamp, ExitReason.TAKE_PROFIT)
        
        # Check stop loss or trailing stop
        if not exit_info and self.current_stop_price:
            if ((self.side == "LONG" and price <= self.current_stop_price) or
                (self.side == "SHORT" and price >= self.current_stop_price)):
                
                reason = ExitReason.TRAILING_STOP if self.trailing_stop_activated else ExitReason.STOP_LOSS
                exit_info = self._close_position(self.current_stop_price, timestamp, reason)
        
        return exit_info
    
    def _close_position(self, exit_price: float, exit_time: datetime, reason: ExitReason) -> Dict[str, Any]:
        """
        Close the position.
        
        Args:
            exit_price: Exit price
            exit_time: Exit timestamp
            reason: Exit reason
            
        Returns:
            Dictionary with exit information
        """
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        self.state = PositionState.CLOSED
        
        # Calculate realized PnL
        price_diff = (exit_price - self.entry_price) if self.side == "LONG" else (self.entry_price - exit_price)
        self.realized_pnl = price_diff * self.quantity
        
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': exit_price,
            'quantity': self.quantity,
            'pnl': self.realized_pnl,
            'pnl_pct': (price_diff / self.entry_price) * 100,
            'entry_time': self.entry_time,
            'exit_time': exit_time,
            'duration_seconds': (exit_time - self.entry_time).total_seconds(),
            'exit_reason': reason.value
        }
    
    def force_close(self, exit_price: float, exit_time: datetime, reason: ExitReason = ExitReason.MANUAL) -> Optional[Dict[str, Any]]:
        """
        Force close the position.
        
        Args:
            exit_price: Exit price
            exit_time: Exit timestamp
            reason: Exit reason
            
        Returns:
            Dictionary with exit information or None if already closed
        """
        if self.state != PositionState.OPEN:
            return None
            
        return self._close_position(exit_price, exit_time, reason)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the position to a dictionary.
        
        Returns:
            Dictionary representation of the position
        """
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time,
            'quantity': self.quantity,
            'sl_price': self.sl_price,
            'tp_price': self.tp_price,
            'current_stop_price': self.current_stop_price,
            'use_trailing_stop': self.use_trailing_stop,
            'trailing_stop_activated': self.trailing_stop_activated,
            'state': self.state.value,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time,
            'exit_reason': self.exit_reason.value if self.exit_reason else None,
            'realized_pnl': self.realized_pnl,
            'max_favorable_excursion': self.max_favorable_excursion,
            'max_adverse_excursion': self.max_adverse_excursion
        }


class PositionSimulator:
    """
    Simulator for position management in backtesting.
    """
    
    def __init__(self, initial_balance: float = 10000.0, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        """
        Initialize the position simulator.
        
        Args:
            initial_balance: Initial account balance
            maker_fee: Maker fee rate
            taker_fee: Taker fee rate
        """
        self.logger = logging.getLogger(__name__)
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Position tracking
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Dict[str, Any]] = []
        self.all_trades: List[Dict[str, Any]] = []
        
        # Tracking metrics
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.total_fees_paid = 0.0
        self.win_count = 0
        self.loss_count = 0
    
    def reset(self, initial_balance: Optional[float] = None):
        """
        Reset the simulator to initial state.
        
        Args:
            initial_balance: New initial balance (optional)
        """
        if initial_balance is not None:
            self.initial_balance = initial_balance
            
        self.current_balance = self.initial_balance
        self.open_positions.clear()
        self.closed_positions.clear()
        self.all_trades.clear()
        self.equity_curve.clear()
        self.total_fees_paid = 0.0
        self.win_count = 0
        self.loss_count = 0
    
    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        entry_time: datetime,
        quantity: float,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        use_trailing_stop: bool = False,
        trailing_stop_activation_pct: float = 0.5,
        trailing_stop_callback_rate: float = 0.3,
        position_id: Optional[str] = None,
        order_type: OrderType = OrderType.MARKET
    ) -> Optional[Dict[str, Any]]:
        """
        Open a new position.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            side: Position side ('LONG' or 'SHORT')
            entry_price: Entry price
            entry_time: Entry timestamp
            quantity: Position size
            sl_price: Stop-loss price
            tp_price: Take-profit price
            use_trailing_stop: Whether to use trailing stop
            trailing_stop_activation_pct: Activation threshold for trailing stop
            trailing_stop_callback_rate: Callback rate for trailing stop
            position_id: Unique position ID (optional)
            order_type: Order type (MARKET or LIMIT)
            
        Returns:
            Position information or None if position couldn't be opened
        """
        # Generate position ID if not provided
        if not position_id:
            position_id = f"{symbol}_{side.upper()}_{entry_time.timestamp()}"
            
        # Check if position already exists
        if position_id in self.open_positions:
            self.logger.warning(f"Position {position_id} already exists")
            return None
            
        # Calculate position cost
        position_cost = entry_price * quantity
        
        # Calculate fee
        fee_rate = self.taker_fee if order_type == OrderType.MARKET else self.maker_fee
        fee = position_cost * fee_rate
        
        # Check if we have enough balance
        if position_cost + fee > self.current_balance:
            self.logger.warning(f"Insufficient balance to open position {position_id}")
            return None
            
        # Update balance
        self.current_balance -= fee
        self.total_fees_paid += fee
        
        # Create position
        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            entry_time=entry_time,
            quantity=quantity,
            sl_price=sl_price,
            tp_price=tp_price,
            use_trailing_stop=use_trailing_stop,
            trailing_stop_activation_pct=trailing_stop_activation_pct,
            trailing_stop_callback_rate=trailing_stop_callback_rate,
            position_id=position_id
        )
        
        # Add to tracking
        self.open_positions[position_id] = position
        
        # Record trade
        trade_info = {
            'type': 'ENTRY',
            'position_id': position_id,
            'symbol': symbol,
            'side': side.upper(),
            'price': entry_price,
            'quantity': quantity,
            'time': entry_time,
            'order_type': order_type.value,
            'fee': fee
        }
        self.all_trades.append(trade_info)
        
        # Update equity curve
        self.equity_curve.append((entry_time, self.current_balance))
        
        return position.to_dict()
    
    def update_positions(self, price_data: Dict[str, float], timestamp: datetime) -> List[Dict[str, Any]]:
        """
        Update all open positions with new price data.
        
        Args:
            price_data: Dictionary mapping symbols to prices
            timestamp: Current timestamp
            
        Returns:
            List of exit information for positions that were closed
        """
        exits = []
        
        # Process each open position
        for position_id, position in list(self.open_positions.items()):
            # Check if we have price data for this symbol
            if position.symbol not in price_data:
                continue
                
            # Get current price
            current_price = price_data[position.symbol]
            
            # Update position
            exit_info = position.update(current_price, timestamp)
            
            # If position was closed
            if exit_info:
                # Calculate fee
                position_value = exit_info['exit_price'] * exit_info['quantity']
                fee = position_value * self.taker_fee
                
                # Update balance
                self.current_balance += exit_info['pnl'] - fee
                self.total_fees_paid += fee
                
                # Update win/loss count
                if exit_info['pnl'] > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1
                
                # Record exit trade
                trade_info = {
                    'type': 'EXIT',
                    'position_id': position_id,
                    'symbol': position.symbol,
                    'side': 'SELL' if position.side == 'LONG' else 'BUY',
                    'price': exit_info['exit_price'],
                    'quantity': position.quantity,
                    'time': timestamp,
                    'order_type': OrderType.MARKET.value,
                    'fee': fee,
                    'pnl': exit_info['pnl'],
                    'exit_reason': exit_info['exit_reason']
                }
                self.all_trades.append(trade_info)
                
                # Add fees to exit info
                exit_info['fee'] = fee
                
                # Add to closed positions
                self.closed_positions.append(exit_info)
                
                # Remove from open positions
                del self.open_positions[position_id]
                
                # Add to exits
                exits.append(exit_info)
        
        # Update equity curve
        if exits:
            self.equity_curve.append((timestamp, self.current_balance))
            
        return exits
    
    def close_all_positions(self, price_data: Dict[str, float], timestamp: datetime) -> List[Dict[str, Any]]:
        """
        Close all open positions.
        
        Args:
            price_data: Dictionary mapping symbols to prices
            timestamp: Current timestamp
            
        Returns:
            List of exit information for positions that were closed
        """
        exits = []
        
        # Process each open position
        for position_id, position in list(self.open_positions.items()):
            # Check if we have price data for this symbol
            if position.symbol not in price_data:
                self.logger.warning(f"No price data for {position.symbol}, cannot close position {position_id}")
                continue
                
            # Get current price
            current_price = price_data[position.symbol]
            
            # Force close position
            exit_info = position.force_close(current_price, timestamp, ExitReason.MANUAL)
            
            if exit_info:
                # Calculate fee
                position_value = exit_info['exit_price'] * exit_info['quantity']
                fee = position_value * self.taker_fee
                
                # Update balance
                self.current_balance += exit_info['pnl'] - fee
                self.total_fees_paid += fee
                
                # Update win/loss count
                if exit_info['pnl'] > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1
                
                # Record exit trade
                trade_info = {
                    'type': 'EXIT',
                    'position_id': position_id,
                    'symbol': position.symbol,
                    'side': 'SELL' if position.side == 'LONG' else 'BUY',
                    'price': exit_info['exit_price'],
                    'quantity': position.quantity,
                    'time': timestamp,
                    'order_type': OrderType.MARKET.value,
                    'fee': fee,
                    'pnl': exit_info['pnl'],
                    'exit_reason': exit_info['exit_reason']
                }
                self.all_trades.append(trade_info)
                
                # Add fees to exit info
                exit_info['fee'] = fee
                
                # Add to closed positions
                self.closed_positions.append(exit_info)
                
                # Remove from open positions
                del self.open_positions[position_id]
                
                # Add to exits
                exits.append(exit_info)
        
        # Update equity curve
        if exits:
            self.equity_curve.append((timestamp, self.current_balance))
            
        return exits
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the simulation.
        
        Returns:
            Dictionary of performance metrics
        """
        # Extract PnL values
        pnls = [trade['pnl'] for trade in self.closed_positions]
        
        # Calculate metrics
        total_trades = len(self.closed_positions)
        win_rate = self.win_count / total_trades if total_trades > 0 else 0
        
        # Calculate profit factor
        gross_profit = sum(pnl for pnl in pnls if pnl > 0)
        gross_loss = abs(sum(pnl for pnl in pnls if pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate drawdown
        equity_values = [value for _, value in self.equity_curve]
        peak = self.initial_balance
        drawdown = 0
        max_drawdown = 0
        
        for value in equity_values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            drawdown = dd
            max_drawdown = max(max_drawdown, dd)
        
        # Calculate returns
        total_return = (self.current_balance - self.initial_balance) / self.initial_balance
        
        # Calculate average win/loss
        avg_win = sum(pnl for pnl in pnls if pnl > 0) / self.win_count if self.win_count > 0 else 0
        avg_loss = sum(pnl for pnl in pnls if pnl < 0) / self.loss_count if self.loss_count > 0 else 0
        
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.current_balance,
            'total_pnl': self.current_balance - self.initial_balance,
            'total_return_pct': total_return * 100,
            'total_trades': total_trades,
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'win_rate': win_rate * 100,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown * 100,
            'current_drawdown_pct': drawdown * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_fees_paid': self.total_fees_paid
        }