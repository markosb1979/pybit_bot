#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Strategy Manager

Manages strategy execution, signal generation, and indicator processing.
Handles the integration of custom indicators and execution of trading logic.
"""

import logging
import time
import json
import os
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np

# Import indicators
from pybit_bot.indicators.luxfvgtrend import calculate_luxfvgtrend
from pybit_bot.indicators.tva import calculate_tva
from pybit_bot.indicators.cvd import calculate_cvd
from pybit_bot.indicators.vfi import calculate_vfi
from pybit_bot.indicators.atr import calculate_atr

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages trading strategies, indicator processing, and signal generation.
    
    Handles the integration of multiple indicators, executes strategy logic,
    and generates entry/exit signals based on indicator values.
    """
    
    def __init__(self, client, order_manager, data_manager, tpsl_manager=None):
        """
        Initialize the strategy manager.
        
        Args:
            client: Bybit API client
            order_manager: Order manager instance
            data_manager: Data manager instance
            tpsl_manager: TP/SL manager instance (optional)
        """
        self.client = client
        self.order_manager = order_manager
        self.data_manager = data_manager
        self.tpsl_manager = tpsl_manager
        
        # Load configuration
        self.config = self._load_indicator_config()
        
        # Track active strategies
        self.active_strategy = "StrategyA"  # Default to StrategyA
        
        # Track open positions and orders
        self.open_long_positions = {}  # symbol -> position details
        self.open_short_positions = {}  # symbol -> position details
        self.pending_orders = {}  # order_id -> order details
        
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
    
    def start(self, strategy_name="StrategyA"):
        """
        Start the strategy manager with the specified strategy.
        
        Args:
            strategy_name: Name of the strategy to run
        """
        if self.is_running:
            logger.warning("Strategy Manager is already running")
            return
        
        # Set active strategy
        self.active_strategy = strategy_name
        
        logger.info(f"Starting Strategy Manager with {strategy_name}")
        self.is_running = True
    
    def stop(self):
        """Stop the strategy manager."""
        if not self.is_running:
            return
            
        logger.info("Stopping Strategy Manager")
        self.is_running = False
    
    def process(self):
        """
        Process market data and generate signals.
        This should be called regularly from the main loop.
        """
        if not self.is_running:
            return
            
        current_time = time.time()
        if current_time - self.last_check_time < self.check_interval_sec:
            return
            
        self.last_check_time = current_time
        
        try:
            # Get symbols to process
            symbols = self.config.get('symbols', ['BTCUSDT'])
            
            # Process each symbol
            for symbol in symbols:
                # Process based on active strategy
                if self.active_strategy == "StrategyA":
                    self._process_strategy_a(symbol)
                elif self.active_strategy == "StrategyB":
                    self._process_strategy_b(symbol)
                else:
                    logger.warning(f"Unknown strategy: {self.active_strategy}")
        
        except Exception as e:
            logger.exception(f"Error in Strategy Manager: {str(e)}")
    
    def _process_strategy_a(self, symbol: str):
        """
        Process StrategyA logic for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        # Get timeframes to process
        timeframes = self.config.get('timeframes', ['1m'])
        
        # Process each timeframe
        for timeframe in timeframes:
            # Get the latest closed candle
            candles = self.data_manager.get_candles(symbol, timeframe, 100)  # Get enough for indicators
            
            if candles is None or len(candles) < 50:  # Need enough data for indicators
                logger.warning(f"Not enough data for {symbol} {timeframe}")
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            # Ensure we're working with the previous closed candle, not the current forming one
            prev_candle = df.iloc[-2]  # -1 would be the current forming candle
            
            # Calculate indicators on the full dataset
            self._calculate_indicators(df)
            
            # Check for signals on the previous candle
            signal = self._check_strategy_a_signals(df, symbol, timeframe)
            
            if signal:
                self._execute_signal(signal, symbol, timeframe, df)
    
    def _calculate_indicators(self, df: pd.DataFrame):
        """
        Calculate all indicators for the dataset.
        
        Args:
            df: DataFrame with OHLCV data
        """
        # Get indicator parameters from config
        atr_length = self.config.get('atr', {}).get('length', 14)
        cvd_length = self.config.get('cvd', {}).get('length', 14)
        tva_length = self.config.get('tva', {}).get('length', 15)
        vfi_lookback = self.config.get('vfi', {}).get('lookback', 50)
        
        # Calculate ATR
        df['atr'] = calculate_atr(df, length=atr_length)
        
        # Calculate CVD
        df['cvd'] = calculate_cvd(df, cumulation_length=cvd_length)
        
        # Calculate TVA
        tva_results = calculate_tva(df, length=tva_length)
        df['rb'] = tva_results[0]  # Rising Bull
        df['rr'] = tva_results[1]  # Rising Bear
        df['db'] = tva_results[2]  # Declining Bull
        df['dr'] = tva_results[3]  # Declining Bear
        
        # Calculate VFI
        df['vfi'] = calculate_vfi(df, lookback=vfi_lookback)
        
        # Calculate LuxFVGtrend
        fvg_results = calculate_luxfvgtrend(df)
        df['fvg_signal'] = fvg_results[0]  # 1 = bullish gap, -1 = bearish gap, 0 = none
        df['fvg_midpoint'] = fvg_results[1]  # price midpoint of the detected gap
        df['fvg_counter'] = fvg_results[2]  # trend counter
    
    def _check_strategy_a_signals(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Check for StrategyA signals.
        
        Args:
            df: DataFrame with indicator values
            symbol: Trading symbol
            timeframe: Candle timeframe
            
        Returns:
            Signal dictionary or None if no signal
        """
        # Get the previous completed candle
        prev_idx = -2  # Skip the current forming candle
        
        # Check if indicators are enabled
        use_cvd = self.config.get('use_cvd', True)
        use_tva = self.config.get('use_tva', True)
        use_vfi = self.config.get('use_vfi', True)
        use_fvg = self.config.get('use_fvg', True)
        
        # Get indicator values from the previous candle
        cvd = df['cvd'].iloc[prev_idx]
        rb = df['rb'].iloc[prev_idx]
        rr = df['rr'].iloc[prev_idx]
        vfi = df['vfi'].iloc[prev_idx]
        fvg_signal = df['fvg_signal'].iloc[prev_idx]
        fvg_midpoint = df['fvg_midpoint'].iloc[prev_idx]
        atr = df['atr'].iloc[prev_idx]
        
        # Previous candle price data
        prev_close = df['close'].iloc[prev_idx]
        
        # Check for long signal
        long_conditions = []
        if use_cvd:
            long_conditions.append(cvd > 0)
        if use_tva:
            long_conditions.append(rb > 0)
        if use_vfi:
            long_conditions.append(vfi > 0)
        if use_fvg:
            long_conditions.append(fvg_signal == 1)
        
        # Only generate signal if all enabled conditions are met
        long_signal = all(long_conditions) if long_conditions else False
        
        # Check for short signal
        short_conditions = []
        if use_cvd:
            short_conditions.append(cvd < 0)
        if use_tva:
            short_conditions.append(rr < 0)
        if use_vfi:
            short_conditions.append(vfi < 0)
        if use_fvg:
            short_conditions.append(fvg_signal == -1)
        
        # Only generate signal if all enabled conditions are met
        short_signal = all(short_conditions) if short_conditions else False
        
        # Check for market or limit entry
        use_limit_entry = self.config.get('use_limit_entry', False)
        
        # Check position limits
        max_long_positions = self.config.get('max_long_positions', 1)
        max_short_positions = self.config.get('max_short_positions', 1)
        
        # Count current positions
        current_long_positions = len(self.open_long_positions)
        current_short_positions = len(self.open_short_positions)
        
        # Generate signal
        signal = None
        
        if long_signal and current_long_positions < max_long_positions:
            # Check for existing opposite positions
            if symbol in self.open_short_positions:
                # Handle position reversal if needed
                pass
            
            # Determine entry price
            if use_limit_entry and fvg_midpoint > 0:
                entry_price = fvg_midpoint + atr
            else:
                entry_price = prev_close
            
            # Calculate TP/SL
            stop_loss_multiplier = self.config.get('stop_loss_multiplier', 2.0)
            take_profit_multiplier = self.config.get('take_profit_multiplier', 4.0)
            
            sl_price = entry_price - (atr * stop_loss_multiplier)
            tp_price = entry_price + (atr * take_profit_multiplier)
            
            signal = {
                'symbol': symbol,
                'timeframe': timeframe,
                'side': 'BUY',
                'entry_type': 'LIMIT' if use_limit_entry else 'MARKET',
                'entry_price': entry_price,
                'stop_loss': sl_price,
                'take_profit': tp_price,
                'atr': atr,
                'reason': 'StrategyA long signal',
                'indicators': {
                    'cvd': cvd,
                    'rb': rb,
                    'vfi': vfi,
                    'fvg_signal': fvg_signal,
                    'fvg_midpoint': fvg_midpoint
                }
            }
            
        elif short_signal and current_short_positions < max_short_positions:
            # Check for existing opposite positions
            if symbol in self.open_long_positions:
                # Handle position reversal if needed
                pass
            
            # Determine entry price
            if use_limit_entry and fvg_midpoint > 0:
                entry_price = fvg_midpoint - atr
            else:
                entry_price = prev_close
            
            # Calculate TP/SL
            stop_loss_multiplier = self.config.get('stop_loss_multiplier', 2.0)
            take_profit_multiplier = self.config.get('take_profit_multiplier', 4.0)
            
            sl_price = entry_price + (atr * stop_loss_multiplier)
            tp_price = entry_price - (atr * take_profit_multiplier)
            
            signal = {
                'symbol': symbol,
                'timeframe': timeframe,
                'side': 'SELL',
                'entry_type': 'LIMIT' if use_limit_entry else 'MARKET',
                'entry_price': entry_price,
                'stop_loss': sl_price,
                'take_profit': tp_price,
                'atr': atr,
                'reason': 'StrategyA short signal',
                'indicators': {
                    'cvd': cvd,
                    'rr': rr,
                    'vfi': vfi,
                    'fvg_signal': fvg_signal,
                    'fvg_midpoint': fvg_midpoint
                }
            }
        
        return signal
    
    def _execute_signal(self, signal: Dict[str, Any], symbol: str, timeframe: str, df: pd.DataFrame):
        """
        Execute a trading signal.
        
        Args:
            signal: Signal dictionary
            symbol: Trading symbol
            timeframe: Candle timeframe
            df: DataFrame with indicator values
        """
        # Check for opposite pending orders
        self._check_and_cancel_opposite_orders(symbol, signal['side'])
        
        # Determine order type and parameters
        order_type = 'LIMIT' if signal['entry_type'] == 'LIMIT' else 'MARKET'
        side = signal['side']  # 'BUY' or 'SELL'
        entry_price = signal['entry_price']
        
        # Calculate position size
        position_size = self._calculate_position_size(symbol, entry_price, signal['stop_loss'])
        
        # Place order
        try:
            result = self.order_manager.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                qty=position_size,
                price=entry_price if order_type == 'LIMIT' else None
            )
            
            if not result or not result.get('success', False):
                logger.error(f"Failed to place {side} order for {symbol}: {result}")
                return
            
            order_id = result['result']['order_id']
            
            # Track pending order
            self.pending_orders[order_id] = {
                'symbol': symbol,
                'side': side,
                'entry_price': entry_price,
                'stop_loss': signal['stop_loss'],
                'take_profit': signal['take_profit'],
                'atr': signal['atr'],
                'timestamp': time.time()
            }
            
            logger.info(f"Placed {side} {order_type} order for {symbol} at {entry_price}")
            
        except Exception as e:
            logger.exception(f"Error placing order for {symbol}: {str(e)}")
    
    def _check_and_cancel_opposite_orders(self, symbol: str, side: str):
        """
        Check for and cancel opposite pending orders.
        
        Args:
            symbol: Trading symbol
            side: Order side ('BUY' or 'SELL')
        """
        opposite_side = 'SELL' if side == 'BUY' else 'BUY'
        
        # Find any pending orders for this symbol with opposite side
        for order_id, order in list(self.pending_orders.items()):
            if order['symbol'] == symbol and order['side'] == opposite_side:
                # Cancel the order
                try:
                    result = self.order_manager.cancel_order(symbol, order_id)
                    if result and result.get('success', False):
                        logger.info(f"Canceled opposite {opposite_side} order {order_id} for {symbol}")
                        # Remove from tracking
                        del self.pending_orders[order_id]
                    else:
                        logger.warning(f"Failed to cancel opposite order {order_id} for {symbol}")
                except Exception as e:
                    logger.exception(f"Error canceling opposite order {order_id}: {str(e)}")
    
    def handle_order_filled(self, order_id: str, fill_price: float):
        """
        Handle order fill event.
        
        Args:
            order_id: Filled order ID
            fill_price: Fill price
        """
        # Check if this is a tracked order
        if order_id not in self.pending_orders:
            return
        
        order = self.pending_orders[order_id]
        symbol = order['symbol']
        side = order['side']
        stop_loss = order['stop_loss']
        take_profit = order['take_profit']
        atr = order['atr']
        
        logger.info(f"{side} order filled for {symbol} at {fill_price}")
        
        # Track position
        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': fill_price,
            'entry_time': time.time(),
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'atr': atr
        }
        
        if side == 'BUY':
            self.open_long_positions[symbol] = position
        else:  # SELL
            self.open_short_positions[symbol] = position
        
        # Remove from pending orders
        del self.pending_orders[order_id]
        
        # Place TP/SL orders
        if self.tpsl_manager:
            # Create position object for TPSL manager
            tpsl_position = {
                'symbol': symbol,
                'size': 1.0 if side == 'BUY' else -1.0,  # Placeholder, will be replaced by actual position size
                'entry_price': fill_price
            }
            
            self.tpsl_manager.place_tpsl_orders(symbol, tpsl_position, atr)
    
    def handle_position_closed(self, symbol: str, side: str, exit_price: float, exit_reason: str):
        """
        Handle position close event.
        
        Args:
            symbol: Trading symbol
            side: Position side ('BUY' or 'SELL')
            exit_price: Exit price
            exit_reason: Reason for exit
        """
        # Remove from position tracking
        if side == 'BUY' and symbol in self.open_long_positions:
            position = self.open_long_positions[symbol]
            entry_price = position['entry_price']
            pnl_pct = (exit_price / entry_price - 1) * 100 if side == 'BUY' else (entry_price / exit_price - 1) * 100
            
            logger.info(f"Closed long position for {symbol} at {exit_price}, P&L: {pnl_pct:.2f}%, reason: {exit_reason}")
            del self.open_long_positions[symbol]
            
        elif side == 'SELL' and symbol in self.open_short_positions:
            position = self.open_short_positions[symbol]
            entry_price = position['entry_price']
            pnl_pct = (entry_price / exit_price - 1) * 100 if side == 'SELL' else (exit_price / entry_price - 1) * 100
            
            logger.info(f"Closed short position for {symbol} at {exit_price}, P&L: {pnl_pct:.2f}%, reason: {exit_reason}")
            del self.open_short_positions[symbol]
    
    def _calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float) -> float:
        """
        Calculate position size based on risk parameters.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            
        Returns:
            Position size
        """
        # Get risk parameters
        account_size = self.config.get('account_size_usdt', 1000.0)
        risk_per_trade_pct = self.config.get('risk_per_trade_pct', 1.0)
        
        # Calculate risk amount
        risk_amount = account_size * (risk_per_trade_pct / 100.0)
        
        # Calculate price risk
        price_risk = abs(entry_price - stop_loss)
        
        # Calculate position size
        if price_risk > 0:
            position_size = risk_amount / price_risk
        else:
            # Fallback to fixed size if stop loss is not valid
            position_size = self.config.get('default_position_size', 0.01)
        
        # Apply min/max constraints
        min_size = self.config.get('min_position_size', 0.001)
        max_size = self.config.get('max_position_size', 0.1)
        
        position_size = max(min_size, min(position_size, max_size))
        
        # Round to appropriate precision
        position_size = round(position_size, 3)
        
        return position_size
    
    def _process_strategy_b(self, symbol: str):
        """
        Process StrategyB logic for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        # Not implemented yet
        pass