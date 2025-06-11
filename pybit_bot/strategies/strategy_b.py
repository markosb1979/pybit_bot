"""
Strategy B - Simple SMA crossover strategy implementation.
Uses fast and slow SMAs for signal generation, with ATR-based stops.
Designed for testing purposes and as a reference implementation.
"""

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from strategies.base_strategy import BaseStrategy, TradeSignal, SignalType, OrderType
from indicators.atr import calculate_atr


def calculate_sma(series: pd.Series, length: int) -> pd.Series:
    """
    Calculate Simple Moving Average.
    
    Args:
        series: Price series (typically close)
        length: SMA period
        
    Returns:
        SMA values as pandas.Series
    """
    return series.rolling(window=length, min_periods=1).mean()


class StrategyB(BaseStrategy):
    """
    Strategy B implementation - SMA crossover strategy for testing.
    """
    
    def __init__(self, config: Dict, symbol: str):
        """
        Initialize Strategy B with configuration and symbol.
        
        Args:
            config: Strategy configuration dictionary
            symbol: Trading symbol (e.g., 'BTCUSDT')
        """
        super().__init__(config, symbol)
        self.logger = logging.getLogger(__name__)
        
        # Extract strategy-specific config
        self.strategy_config = config.get('strategy_b', {})
        
        # SMA parameters
        self.fast_sma_length = self.strategy_config.get('sma_fast_length', 10)
        self.slow_sma_length = self.strategy_config.get('sma_slow_length', 30)
        self.atr_length = self.strategy_config.get('atr_length', 14)
        
        # TP/SL parameters
        self.tp_atr_mult = self.strategy_config.get('tp_atr_mult', 4.0)
        self.trail_atr_mult = self.strategy_config.get('trail_atr_mult', 2.0)
        self.trail_activation_pct = self.strategy_config.get('trail_activation_pct', 0.5)
        
        # Timeframes
        self.sma_timeframe = self.strategy_config.get('sma_timeframe', '1m')
        self.atr_timeframe = self.strategy_config.get('atr_timeframe', '5m')
        
        # Trade tracking
        self.active_trade = None
        
        self.logger.info(f"Strategy B initialized for {symbol} with fast SMA {self.fast_sma_length}, "
                         f"slow SMA {self.slow_sma_length}")
    
    def get_required_timeframes(self) -> List[str]:
        """
        Get the list of timeframes required by this strategy.
        
        Returns:
            List of timeframe strings (e.g., ['1m', '5m'])
        """
        timeframes = [self.sma_timeframe]
        if self.atr_timeframe != self.sma_timeframe:
            timeframes.append(self.atr_timeframe)
        return timeframes
    
    def calculate_indicators(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Calculate all indicators required by the strategy.
        
        Args:
            data: Dictionary of DataFrames containing price/volume data for different timeframes
                 
        Returns:
            Dictionary of DataFrames with indicators added as columns
        """
        result_data = {}
        
        # Process SMA timeframe
        if self.sma_timeframe in data and data[self.sma_timeframe] is not None:
            df_sma = data[self.sma_timeframe].copy()
            
            # Calculate fast and slow SMAs
            try:
                df_sma['fast_sma'] = calculate_sma(df_sma['close'], self.fast_sma_length)
                df_sma['slow_sma'] = calculate_sma(df_sma['close'], self.slow_sma_length)
                self.logger.debug(f"Calculated SMAs for {self.sma_timeframe}")
            except Exception as e:
                self.logger.error(f"Error calculating SMAs: {str(e)}")
                df_sma['fast_sma'] = pd.Series(np.nan, index=df_sma.index)
                df_sma['slow_sma'] = pd.Series(np.nan, index=df_sma.index)
            
            result_data[self.sma_timeframe] = df_sma
        
        # Process ATR timeframe
        if self.atr_timeframe in data and data[self.atr_timeframe] is not None:
            df_atr = data[self.atr_timeframe].copy()
            
            # Calculate ATR
            try:
                df_atr['atr'] = calculate_atr(df_atr, length=self.atr_length)
                self.logger.debug(f"Calculated ATR for {self.atr_timeframe}")
            except Exception as e:
                self.logger.error(f"Error calculating ATR: {str(e)}")
                df_atr['atr'] = pd.Series(np.nan, index=df_atr.index)
            
            result_data[self.atr_timeframe] = df_atr
        
        return result_data
    
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[TradeSignal]:
        """
        Generate trading signals based on the calculated indicators.
        
        Args:
            data: Dictionary of DataFrames with indicators
            
        Returns:
            List of TradeSignal objects
        """
        signals = []
        
        # Check if strategy is enabled
        if not self.strategy_config.get('enabled', False):
            return signals
        
        # Check if we have the required data
        if self.sma_timeframe not in data or data[self.sma_timeframe] is None:
            self.logger.warning(f"No data available for SMA timeframe {self.sma_timeframe}")
            return signals
        
        if self.atr_timeframe not in data or data[self.atr_timeframe] is None:
            self.logger.warning(f"No data available for ATR timeframe {self.atr_timeframe}")
            return signals
        
        # Get dataframes
        df_sma = data[self.sma_timeframe]
        df_atr = data[self.atr_timeframe]
        
        # Check if we have enough data
        if len(df_sma) < 3:  # Need at least 3 bars to detect crossover
            self.logger.warning("Not enough data to generate signals")
            return signals
        
        try:
            # Get indicator values from previous bars
            fast_sma_prev = df_sma['fast_sma'].iloc[-2]
            slow_sma_prev = df_sma['slow_sma'].iloc[-2]
            fast_sma_prev2 = df_sma['fast_sma'].iloc[-3]
            slow_sma_prev2 = df_sma['slow_sma'].iloc[-3]
            
            # Check for crossovers
            bullish_crossover = (fast_sma_prev > slow_sma_prev) and (fast_sma_prev2 <= slow_sma_prev2)
            bearish_crossover = (fast_sma_prev < slow_sma_prev) and (fast_sma_prev2 >= slow_sma_prev2)
            
            # Get ATR value
            atr_value = df_atr['atr'].iloc[-2]  # Previous completed bar
            
            # Check for signals
            if bullish_crossover:
                # Create a long signal
                entry_price = df_sma['close'].iloc[-2]  # Previous bar close
                sl_price = entry_price - (atr_value * self.trail_atr_mult)
                tp_price = entry_price + (atr_value * self.tp_atr_mult)
                
                signal = TradeSignal(
                    signal_type=SignalType.BUY,
                    symbol=self.symbol,
                    price=entry_price,
                    timestamp=int(df_sma.index[-2].timestamp() * 1000),
                    order_type=OrderType.MARKET,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    indicator_values={
                        'fast_sma': fast_sma_prev,
                        'slow_sma': slow_sma_prev,
                        'atr': atr_value
                    },
                    metadata={
                        'trail_activation_pct': self.trail_activation_pct,
                        'trail_atr_mult': self.trail_atr_mult
                    }
                )
                signals.append(signal)
                self.logger.info(f"Generated LONG signal at {entry_price}")
                
            elif bearish_crossover:
                # Create a short signal
                entry_price = df_sma['close'].iloc[-2]  # Previous bar close
                sl_price = entry_price + (atr_value * self.trail_atr_mult)
                tp_price = entry_price - (atr_value * self.tp_atr_mult)
                
                signal = TradeSignal(
                    signal_type=SignalType.SELL,
                    symbol=self.symbol,
                    price=entry_price,
                    timestamp=int(df_sma.index[-2].timestamp() * 1000),
                    order_type=OrderType.MARKET,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    indicator_values={
                        'fast_sma': fast_sma_prev,
                        'slow_sma': slow_sma_prev,
                        'atr': atr_value
                    },
                    metadata={
                        'trail_activation_pct': self.trail_activation_pct,
                        'trail_atr_mult': self.trail_atr_mult
                    }
                )
                signals.append(signal)
                self.logger.info(f"Generated SHORT signal at {entry_price}")
                
        except Exception as e:
            self.logger.error(f"Error generating signals: {str(e)}", exc_info=True)
        
        return signals
    
    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the strategy configuration has all required parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if strategy section exists
        if not self.strategy_config:
            return False, "Missing 'strategy_b' section in configuration"
        
        # Check if SMA lengths are valid
        if self.fast_sma_length >= self.slow_sma_length:
            return False, f"Fast SMA length ({self.fast_sma_length}) must be less than slow SMA length ({self.slow_sma_length})"
        
        # Check if ATR length is valid
        if self.atr_length <= 0:
            return False, f"ATR length ({self.atr_length}) must be positive"
        
        # Check if TP/SL multiples are valid
        if self.tp_atr_mult <= 0 or self.trail_atr_mult <= 0:
            return False, "TP and trail ATR multiples must be positive"
        
        # Check if trail activation percentage is valid
        if self.trail_activation_pct <= 0 or self.trail_activation_pct >= 1:
            return False, "Trail activation percentage must be between 0 and 1"
        
        return True, None