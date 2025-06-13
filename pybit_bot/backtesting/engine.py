#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backtesting Engine

Core backtesting engine for testing trading strategies with historical data.
Supports multi-timeframe testing, realistic execution simulation, and
comprehensive performance reporting.
"""

import os
import json
import logging
import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from copy import deepcopy

# Import performance metrics
from pybit_bot.backtesting.performance_metrics import PerformanceMetrics
from pybit_bot.backtesting.market_simulator import MarketSimulator

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Backtesting engine for testing trading strategies.
    
    Handles historical data loading, strategy execution,
    realistic order simulation, and performance reporting.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the backtest engine.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.data_dir = config.get('data_dir', 'data')
        self.results_dir = config.get('results_dir', 'results')
        
        # Ensure directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Initialize components
        self.market_simulator = MarketSimulator(config.get('simulator', {}))
        
        # State tracking
        self.data = {}          # Symbol -> Timeframe -> DataFrame
        self.trades = []        # List of executed trades
        self.equity_curve = []  # Equity points over time
        self.positions = {}     # Current open positions
        self.orders = {}        # Active orders
        
        # Performance tracking
        self.initial_capital = config.get('initial_capital', 10000)
        self.current_capital = self.initial_capital
        self.metrics = None
    
    def load_data(self, symbol: str, timeframes: List[str], start_date: str, end_date: str) -> bool:
        """
        Load historical data for backtesting.
        
        Args:
            symbol: Trading symbol
            timeframes: List of timeframes to load
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            True if data loaded successfully, False otherwise
        """
        try:
            if symbol not in self.data:
                self.data[symbol] = {}
                
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            for timeframe in timeframes:
                # Construct file path
                file_path = os.path.join(self.data_dir, f"{symbol}_{timeframe}.csv")
                
                if not os.path.exists(file_path):
                    logger.error(f"Data file not found: {file_path}")
                    return False
                
                # Load data
                df = pd.read_csv(file_path)
                
                # Convert timestamp to datetime
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                elif 'time' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['time'])
                    
                # Filter by date range
                df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)]
                
                if len(df) == 0:
                    logger.warning(f"No data found for {symbol} {timeframe} in date range")
                    return False
                
                # Ensure required columns
                required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                for col in required_columns:
                    if col not in df.columns:
                        logger.error(f"Missing required column {col} in {file_path}")
                        return False
                
                # Sort by timestamp
                df = df.sort_values('timestamp')
                
                # Store data
                self.data[symbol][timeframe] = df
                logger.info(f"Loaded {len(df)} candles for {symbol} {timeframe}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error loading data: {str(e)}")
            return False
    
    def run_backtest(self, strategy_class, strategy_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a backtest with the given strategy and parameters.
        
        Args:
            strategy_class: Strategy class to instantiate
            strategy_params: Strategy parameters
            
        Returns:
            Dictionary of backtest results
        """
        try:
            logger.info(f"Starting backtest with strategy: {strategy_class.__name__}")
            
            # Initialize strategy
            strategy = strategy_class(strategy_params)
            
            # Get strategy requirements
            symbol = strategy_params.get('symbol', 'BTCUSDT')
            timeframes = strategy_params.get('timeframes', ['1m'])
            primary_timeframe = timeframes[0]
            
            # Reset state
            self.trades = []
            self.equity_curve = []
            self.positions = {}
            self.orders = {}
            self.current_capital = self.initial_capital
            
            # Add initial equity point
            self.equity_curve.append({
                'timestamp': self.data[symbol][primary_timeframe]['timestamp'].iloc[0],
                'equity': self.current_capital
            })
            
            # Get data
            if symbol not in self.data or not all(tf in self.data[symbol] for tf in timeframes):
                logger.error(f"Missing data for {symbol} {timeframes}")
                return self._generate_empty_results()
            
            # Main backtest loop
            primary_data = self.data[symbol][primary_timeframe]
            
            for i, row in primary_data.iterrows():
                # Current timestamp
                current_time = row['timestamp']
                
                # Update market data in simulator
                self.market_simulator.update_market_data(symbol, {
                    'timestamp': current_time,
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume']
                })
                
                # Prepare candle data for all timeframes at this point in time
                candles = {}
                for tf in timeframes:
                    # Get data up to current time
                    tf_data = self.data[symbol][tf]
                    tf_data = tf_data[tf_data['timestamp'] <= current_time]
                    
                    if len(tf_data) > 0:
                        # Get the last candle
                        last_candle = tf_data.iloc[-1].to_dict()
                        candles[tf] = last_candle
                
                # Process strategy
                signals = strategy.process_candles(symbol, candles)
                
                # Process signals
                for signal in signals:
                    self._process_signal(signal, current_time)
                
                # Process open orders
                self._process_orders(current_time)
                
                # Update equity curve
                self._update_equity(current_time)
            
            # Close any remaining positions at the end
            self._close_all_positions(primary_data['timestamp'].iloc[-1])
            
            # Calculate performance metrics
            self.metrics = PerformanceMetrics.calculate_metrics(self.trades, self.initial_capital)
            
            # Generate equity curve DataFrame
            equity_df = pd.DataFrame(self.equity_curve)
            
            # Generate results
            results = {
                'strategy': strategy_class.__name__,
                'symbol': symbol,
                'timeframes': timeframes,
                'start_date': primary_data['timestamp'].iloc[0].strftime('%Y-%m-%d'),
                'end_date': primary_data['timestamp'].iloc[-1].strftime('%Y-%m-%d'),
                'trades': self.trades,
                'equity_curve': self.equity_curve,
                'metrics': self.metrics
            }
            
            # Save results
            self._save_results(results)
            
            logger.info(f"Backtest completed with {len(self.trades)} trades")
            
            return results
            
        except Exception as e:
            logger.exception(f"Error running backtest: {str(e)}")
            return self._generate_empty_results()
    
    def _process_signal(self, signal: Dict[str, Any], current_time: pd.Timestamp):
        """
        Process a trading signal.
        
        Args:
            signal: Signal dictionary
            current_time: Current timestamp
        """
        try:
            symbol = signal['symbol']
            side = signal['side']  # 'BUY' or 'SELL'
            signal_type = signal.get('type', 'MARKET')  # 'MARKET', 'LIMIT', etc.
            price = signal.get('price')
            tp_price = signal.get('take_profit')
            sl_price = signal.get('stop_loss')
            
            # For market orders, use current price if not specified
            if signal_type == 'MARKET' and price is None:
                ticker = self.market_simulator.ticker_data.get(symbol, {})
                price = ticker.get('close')
                if price is None:
                    logger.warning(f"No price data available for {symbol}, skipping signal")
                    return
            
            # Calculate position size
            position_size = self._calculate_position_size(symbol, price, sl_price)
            
            # Check if we're already in a position
            existing_position = self.positions.get(symbol)
            
            # If signal is to close position
            if signal.get('action') == 'CLOSE' and existing_position:
                self._close_position(symbol, price, "Signal", current_time)
                return
            
            # Handle existing position
            if existing_position:
                existing_side = existing_position['side']
                
                # If same direction, ignore
                if existing_side == side:
                    logger.info(f"Already in {side} position for {symbol}, ignoring signal")
                    return
                
                # If opposite direction, close existing and open new
                self._close_position(symbol, price, "Reversal", current_time)
            
            # Place order
            order = {
                'symbol': symbol,
                'side': side,
                'type': signal_type,
                'qty': position_size,
                'price': price,
                'take_profit': tp_price,
                'stop_loss': sl_price,
                'time': current_time,
                'status': 'PENDING'
            }
            
            # Generate order ID
            order_id = f"backtest_{len(self.orders) + 1}"
            self.orders[order_id] = order
            
            # For market orders, execute immediately
            if signal_type == 'MARKET':
                self._execute_order(order_id, current_time)
                
        except Exception as e:
            logger.exception(f"Error processing signal: {str(e)}")
    
    def _process_orders(self, current_time: pd.Timestamp):
        """
        Process open orders.
        
        Args:
            current_time: Current timestamp
        """
        for order_id, order in list(self.orders.items()):
            if order['status'] != 'PENDING':
                continue
                
            symbol = order['symbol']
            price = order['price']
            side = order['side']
            order_type = order['type']
            
            # Skip market orders (should be executed immediately)
            if order_type == 'MARKET':
                continue
                
            # Get latest price data
            ticker = self.market_simulator.ticker_data.get(symbol, {})
            if not ticker:
                continue
                
            high = ticker.get('high')
            low = ticker.get('low')
            
            # Check if limit order would execute
            if order_type == 'LIMIT':
                # Buy limit: execute if low price <= limit price
                if side == 'BUY' and low <= price:
                    self._execute_order(order_id, current_time)
                
                # Sell limit: execute if high price >= limit price
                elif side == 'SELL' and high >= price:
                    self._execute_order(order_id, current_time)
            
            # Check if stop order would execute
            elif order_type == 'STOP':
                # Buy stop: execute if high price >= stop price
                if side == 'BUY' and high >= price:
                    self._execute_order(order_id, current_time)
                
                # Sell stop: execute if low price <= stop price
                elif side == 'SELL' and low <= price:
                    self._execute_order(order_id, current_time)
    
    def _execute_order(self, order_id: str, current_time: pd.Timestamp):
        """
        Execute an order.
        
        Args:
            order_id: Order ID
            current_time: Current timestamp
        """
        order = self.orders[order_id]
        symbol = order['symbol']
        side = order['side']
        qty = order['qty']
        price = order['price']
        tp_price = order.get('take_profit')
        sl_price = order.get('stop_loss')
        
        # Simulate order execution with market simulator
        execution = self.market_simulator.execute_order(order)
        
        if execution['status'] != 'FILLED':
            logger.warning(f"Order {order_id} not filled: {execution['message']}")
            order['status'] = execution['status']
            return
            
        # Update order status
        order['status'] = 'FILLED'
        order['filled_price'] = execution['avg_price']
        order['commission'] = execution.get('commission', 0)
        
        # Calculate position cost
        position_cost = qty * execution['avg_price']
        
        # Update capital
        if side == 'BUY':
            self.current_capital -= position_cost
        else:  # SELL
            self.current_capital += position_cost
        
        # Deduct commission
        self.current_capital -= order['commission']
        
        # Create or update position
        self.positions[symbol] = {
            'symbol': symbol,
            'side': side,
            'entry_price': execution['avg_price'],
            'size': qty,
            'entry_time': current_time,
            'take_profit': tp_price,
            'stop_loss': sl_price,
            'order_id': order_id
        }
        
        logger.info(f"Executed {side} order for {symbol} at {execution['avg_price']}, size: {qty}")
    
    def _close_position(self, symbol: str, price: float, reason: str, current_time: pd.Timestamp):
        """
        Close an open position.
        
        Args:
            symbol: Trading symbol
            price: Closing price
            reason: Reason for closing
            current_time: Current timestamp
        """
        if symbol not in self.positions:
            return
            
        position = self.positions[symbol]
        entry_price = position['entry_price']
        size = position['size']
        side = position['side']
        entry_time = position['entry_time']
        
        # Calculate profit/loss
        if side == 'BUY':
            pnl = (price - entry_price) * size
            pnl_pct = (price / entry_price - 1) * 100
        else:  # SELL
            pnl = (entry_price - price) * size
            pnl_pct = (entry_price / price - 1) * 100
        
        # Update capital
        self.current_capital += (size * price) if side == 'BUY' else (-size * price)
        
        # Record trade
        trade = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'exit_price': price,
            'size': size,
            'entry_time': entry_time,
            'exit_time': current_time,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'duration': (current_time - entry_time).total_seconds() / 3600,  # Hours
            'exit_reason': reason
        }
        
        self.trades.append(trade)
        
        # Remove position
        del self.positions[symbol]
        
        logger.info(f"Closed {side} position for {symbol} at {price}, PnL: {pnl:.2f} ({pnl_pct:.2f}%)")
    
    def _close_all_positions(self, current_time: pd.Timestamp):
        """
        Close all open positions.
        
        Args:
            current_time: Current timestamp
        """
        for symbol in list(self.positions.keys()):
            ticker = self.market_simulator.ticker_data.get(symbol, {})
            if not ticker:
                continue
                
            price = ticker.get('close')
            if price:
                self._close_position(symbol, price, "End of backtest", current_time)
    
    def _update_equity(self, current_time: pd.Timestamp):
        """
        Update equity curve.
        
        Args:
            current_time: Current timestamp
        """
        # Calculate unrealized P&L
        unrealized_pnl = 0
        
        for symbol, position in self.positions.items():
            ticker = self.market_simulator.ticker_data.get(symbol, {})
            if not ticker:
                continue
                
            current_price = ticker.get('close')
            if not current_price:
                continue
                
            entry_price = position['entry_price']
            size = position['size']
            side = position['side']
            
            if side == 'BUY':
                unrealized_pnl += (current_price - entry_price) * size
            else:  # SELL
                unrealized_pnl += (entry_price - current_price) * size
        
        # Calculate total equity
        total_equity = self.current_capital + unrealized_pnl
        
        # Add to equity curve
        self.equity_curve.append({
            'timestamp': current_time,
            'equity': total_equity
        })
    
    def _calculate_position_size(self, symbol: str, price: float, stop_loss: Optional[float]) -> float:
        """
        Calculate position size based on risk parameters.
        
        Args:
            symbol: Trading symbol
            price: Entry price
            stop_loss: Stop loss price
            
        Returns:
            Position size
        """
        # Get risk parameters
        risk_per_trade_pct = self.config.get('risk_per_trade_pct', 1.0) / 100
        max_position_size_pct = self.config.get('max_position_size_pct', 10.0) / 100
        
        # Calculate maximum position size based on capital
        max_position = self.current_capital * max_position_size_pct
        
        # If stop loss is defined, calculate risk-based position size
        if stop_loss:
            risk_amount = self.current_capital * risk_per_trade_pct
            price_risk = abs(price - stop_loss)
            
            if price_risk > 0:
                risk_based_size = risk_amount / price_risk
                return min(risk_based_size, max_position / price)
        
        # Default to fixed position size
        return max_position / price
    
    def _save_results(self, results: Dict[str, Any]):
        """
        Save backtest results to file.
        
        Args:
            results: Results dictionary
        """
        try:
            # Create filename
            strategy = results['strategy']
            symbol = results['symbol']
            start_date = results['start_date'].replace('-', '')
            end_date = results['end_date'].replace('-', '')
            
            filename = f"backtest_{strategy}_{symbol}_{start_date}_{end_date}.json"
            file_path = os.path.join(self.results_dir, filename)
            
            # Convert timestamps to strings for JSON serialization
            results_copy = deepcopy(results)
            
            # Convert trades timestamps
            for trade in results_copy['trades']:
                trade['entry_time'] = trade['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
                trade['exit_time'] = trade['exit_time'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Convert equity curve timestamps
            for point in results_copy['equity_curve']:
                point['timestamp'] = point['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(results_copy, f, indent=2)
                
            logger.info(f"Results saved to {file_path}")
            
        except Exception as e:
            logger.exception(f"Error saving results: {str(e)}")
    
    def _generate_empty_results(self) -> Dict[str, Any]:
        """
        Generate empty results structure.
        
        Returns:
            Empty results dictionary
        """
        return {
            'strategy': 'Unknown',
            'symbol': 'Unknown',
            'timeframes': [],
            'start_date': '',
            'end_date': '',
            'trades': [],
            'equity_curve': [],
            'metrics': {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'max_drawdown': 0,
                'max_drawdown_pct': 0,
                'sharpe_ratio': 0,
                'sortino_ratio': 0
            }
        }