"""
Strategy B - Simple time-based strategy implementation for testing.
Enters LONG on even minutes, SHORT on odd minutes.
Uses ATR-based stops for risk management.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from datetime import datetime

from pybit_bot.strategies.base_strategy import BaseStrategy, TradeSignal, SignalType, OrderType
from pybit_bot.utils.logger import Logger


class StrategyB(BaseStrategy):
    """
    Strategy B implementation - Time-based entry strategy for testing.
    """
    
    def __init__(self, config: Dict, symbol: str):
        """
        Initialize Strategy B with configuration and symbol.
        
        Args:
            config: Strategy configuration dictionary
            symbol: Trading symbol (e.g., 'BTCUSDT')
        """
        super().__init__(config, symbol)
        self.name = "Time-Based Test Strategy"
        self.symbol = symbol
        self.logger = Logger("StrategyB")
        
        # Extract strategy-specific config
        self.strategy_config = config.get('strategy', {}).get('strategies', {}).get('strategy_b', {})
        
        # ATR parameters
        self.atr_length = self.strategy_config.get('atr_length', 14)
        self.tp_atr_mult = self.strategy_config.get('tp_atr_mult', 4.0)
        self.trail_atr_mult = self.strategy_config.get('trail_atr_mult', 2.0)
        self.trail_activation_pct = self.strategy_config.get('trail_activation_pct', 0.5)
        
        # Timeframes
        self.primary_timeframe = self.strategy_config.get('sma_timeframe', '1m')
        self.atr_timeframe = self.strategy_config.get('atr_timeframe', '1m')
        
        # Enhanced state tracking
        self.last_signal_minute = -1
        self.last_signal_type = None
        self.force_alternating = self.strategy_config.get('force_alternating', True)  # Force alternating signals
        
        # Debug log all parameters
        self.logger.info(f"Strategy B initialized for {symbol} with parameters:")
        self.logger.info(f"- Primary Timeframe: {self.primary_timeframe}")
        self.logger.info(f"- ATR Length: {self.atr_length}")
        self.logger.info(f"- TP ATR Multiplier: {self.tp_atr_mult}")
        self.logger.info(f"- Trail ATR Multiplier: {self.trail_atr_mult}")
        self.logger.info(f"- Trail Activation: {self.trail_activation_pct}")
        self.logger.info(f"- Trade Rule: LONG on even minutes, SHORT on odd minutes")
        self.logger.info(f"- Force Alternating Signals: {self.force_alternating}")
    
    async def process_data(self, symbol: str, data_dict: Dict[str, pd.DataFrame]) -> List[TradeSignal]:
        """
        Process market data and generate signals.
        
        Args:
            symbol: Trading symbol
            data_dict: Dictionary of DataFrames with market data by timeframe
            
        Returns:
            List of trade signals
        """
        try:
            # Verify symbol matches what we were initialized with
            if symbol != self.symbol:
                self.logger.warning(f"Symbol mismatch: initialized with {self.symbol} but processing {symbol}")
            
            # Log what we received
            timeframes = list(data_dict.keys())
            self.logger.info(f"Processing data for {symbol} with timeframes: {timeframes}")
            
            # Check if we have at least the required timeframe
            if self.primary_timeframe not in data_dict:
                self.logger.warning(f"Not enough data for {symbol} {self.primary_timeframe}")
                return []
                
            # First add indicators to dataframes
            data_with_indicators = self._calculate_indicators(symbol, data_dict)
            
            # Then generate signals
            signals = self._generate_signals(symbol, data_with_indicators)
            
            # Log any signals
            if signals:
                self.logger.info(f"Generated {len(signals)} signals for {symbol}")
                for signal in signals:
                    self.logger.info(f"Signal: {signal.signal_type} at price {signal.price} with SL={signal.sl_price}, TP={signal.tp_price}")
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Error processing data for {symbol}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []
    
    def _calculate_indicators(self, symbol: str, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Calculate indicators for the strategy.
        
        Args:
            symbol: Trading symbol
            data_dict: Dictionary of DataFrames with market data by timeframe
            
        Returns:
            Dictionary of DataFrames with indicators added
        """
        result_data = {}
        
        # Get the data for the primary timeframe
        if self.primary_timeframe in data_dict:
            df = data_dict[self.primary_timeframe].copy()
            
            # Calculate ATR if this is also the ATR timeframe
            if self.primary_timeframe == self.atr_timeframe:
                df['atr'] = self._calculate_atr(df, self.atr_length)
            
            result_data[self.primary_timeframe] = df
            
            # Log details about the latest candle
            if len(df) > 0:
                last_candle = df.iloc[-1]
                timestamp_ms = last_candle['timestamp']
                candle_time = datetime.fromtimestamp(timestamp_ms / 1000)
                minute = candle_time.minute
                
                self.logger.info(f"Latest candle for {symbol} {self.primary_timeframe}:")
                self.logger.info(f"- Time: {candle_time.strftime('%Y-%m-%d %H:%M:%S')} (Minute: {minute})")
                self.logger.info(f"- Price: {last_candle['close']:.2f}")
                self.logger.info(f"- Even minute: {minute % 2 == 0}")
        
        # Calculate ATR for a different timeframe if needed
        if self.atr_timeframe != self.primary_timeframe and self.atr_timeframe in data_dict:
            df = data_dict[self.atr_timeframe].copy()
            df['atr'] = self._calculate_atr(df, self.atr_length)
            result_data[self.atr_timeframe] = df
            
            # Log ATR value
            if len(df) > 0:
                last_candle = df.iloc[-1]
                self.logger.info(f"- ATR ({self.atr_length}): {last_candle['atr']:.2f}")
        
        return result_data
    
    def _calculate_atr(self, df: pd.DataFrame, length: int) -> pd.Series:
        """
        Calculate Average True Range.
        
        Args:
            df: DataFrame with OHLC data
            length: ATR period
            
        Returns:
            ATR values as Series
        """
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            # Calculate True Range
            prev_close = close.shift(1)
            tr1 = high - low
            tr2 = (high - prev_close).abs()
            tr3 = (low - prev_close).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Calculate ATR using Simple Moving Average
            atr = tr.rolling(window=length, min_periods=1).mean()
            
            return atr
            
        except Exception as e:
            self.logger.error(f"Error calculating ATR: {str(e)}")
            return pd.Series(np.nan, index=df.index)
    
    def _generate_signals(self, symbol: str, data_dict: Dict[str, pd.DataFrame]) -> List[TradeSignal]:
        """
        Generate trade signals based on time.
        
        Args:
            symbol: Trading symbol
            data_dict: Dictionary of DataFrames with indicators
            
        Returns:
            List of trade signals
        """
        signals = []
        
        # Check if we have the required data
        if self.primary_timeframe not in data_dict or len(data_dict[self.primary_timeframe]) < 1:
            self.logger.warning(f"Not enough data for {symbol} {self.primary_timeframe}")
            return signals
        
        # Get the dataframe with latest data
        df = data_dict[self.primary_timeframe]
        
        # Get latest candle
        latest_candle = df.iloc[-1]
        timestamp_ms = latest_candle['timestamp']
        candle_time = datetime.fromtimestamp(timestamp_ms / 1000)
        minute = candle_time.minute
        
        # Check if we already generated a signal for this minute
        if minute == self.last_signal_minute:
            self.logger.info(f"Already generated signal for minute {minute}, skipping")
            return signals
        
        # Get ATR value
        atr_value = None
        if self.primary_timeframe == self.atr_timeframe:
            if 'atr' in df.columns and not df['atr'].isna().all():
                atr_value = df['atr'].iloc[-1]
        elif self.atr_timeframe in data_dict:
            atr_df = data_dict[self.atr_timeframe]
            if 'atr' in atr_df.columns and not atr_df['atr'].isna().all():
                atr_value = atr_df['atr'].iloc[-1]
        
        if atr_value is None or np.isnan(atr_value):
            self.logger.warning(f"ATR not available for {symbol}, using volatility estimate")
            # Fallback: calculate a simple volatility estimate (high-low)
            atr_value = (df['high'].iloc[-5:] - df['low'].iloc[-5:]).mean()
        
        # Get current price
        curr_close = latest_candle['close']
        
        # Determine signal type based on minute or force alternating pattern
        is_even_minute = minute % 2 == 0
        
        # Force alternating signals if enabled
        if self.force_alternating and self.last_signal_type is not None:
            # If we got a SELL last time, generate a BUY now regardless of minute
            if self.last_signal_type == SignalType.SELL:
                is_even_minute = True  # Force BUY signal
                self.logger.info(f"FORCING BUY signal (alternating from previous SELL)")
            # If we got a BUY last time, generate a SELL now regardless of minute
            elif self.last_signal_type == SignalType.BUY:
                is_even_minute = False  # Force SELL signal
                self.logger.info(f"FORCING SELL signal (alternating from previous BUY)")
        
        signal_type = SignalType.BUY if is_even_minute else SignalType.SELL
        direction = "LONG" if is_even_minute else "SHORT"
        
        self.logger.info(f"Minute {minute} is {'even' if is_even_minute else 'odd'}, generating {direction} signal")
        
        # Calculate stop loss and take profit with safeguards
        if is_even_minute:  # BUY/LONG
            sl_price = curr_close - (atr_value * self.trail_atr_mult)
            tp_price = curr_close + (atr_value * self.tp_atr_mult)
            
            # Ensure SL is below entry for LONG
            if sl_price >= curr_close:
                sl_price = curr_close * 0.995  # Fallback to 0.5% below
                self.logger.warning(f"Corrected invalid SL for LONG: now {sl_price} (0.5% below entry)")
                
            # Ensure TP is above entry for LONG
            if tp_price <= curr_close:
                tp_price = curr_close * 1.005  # Fallback to 0.5% above
                self.logger.warning(f"Corrected invalid TP for LONG: now {tp_price} (0.5% above entry)")
                
        else:  # SELL/SHORT
            sl_price = curr_close + (atr_value * self.trail_atr_mult)
            tp_price = curr_close - (atr_value * self.tp_atr_mult)
            
            # Ensure SL is above entry for SHORT
            if sl_price <= curr_close:
                sl_price = curr_close * 1.005  # Fallback to 0.5% above
                self.logger.warning(f"Corrected invalid SL for SHORT: now {sl_price} (0.5% above entry)")
                
            # Ensure TP is below entry for SHORT
            if tp_price >= curr_close:
                tp_price = curr_close * 0.995  # Fallback to 0.5% below
                self.logger.warning(f"Corrected invalid TP for SHORT: now {tp_price} (0.5% below entry)")
        
        # Round to appropriate precision
        sl_price = round(sl_price, 2)
        tp_price = round(tp_price, 2)
        
        # Create signal
        signal = TradeSignal(
            signal_type=signal_type,
            direction=direction,
            strength=1.0,
            timestamp=int(timestamp_ms),
            price=curr_close,
            sl_price=sl_price,
            tp_price=tp_price,
            metadata={
                'minute': minute,
                'is_even': is_even_minute,
                'atr': atr_value,
                'trail_activation_pct': self.trail_activation_pct,
                'forced_alternating': self.force_alternating and self.last_signal_type is not None
            }
        )
        
        signals.append(signal)
        
        # Update last signal minute and type
        self.last_signal_minute = minute
        self.last_signal_type = signal_type
        
        return signals