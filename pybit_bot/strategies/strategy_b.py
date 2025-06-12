"""
Strategy B - Simple SMA crossover strategy implementation.
Uses fast and slow SMAs for signal generation, with ATR-based stops.
Designed for testing purposes and as a reference implementation.
"""

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

# Fix imports to use absolute path
from pybit_bot.strategies.base_strategy import BaseStrategy, TradeSignal, SignalType, OrderType
from pybit_bot.indicators.atr import calculate_atr


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
        self.sma_fast_length = self.strategy_config.get('sma_fast_length', 10)
        self.sma_slow_length = self.strategy_config.get('sma_slow_length', 30)
        
        # ATR parameters
        self.atr_length = self.strategy_config.get('atr_length', 14)
        self.tp_atr_mult = self.strategy_config.get('tp_atr_mult', 4.0)
        self.trail_atr_mult = self.strategy_config.get('trail_atr_mult', 2.0)
        self.trail_activation_pct = self.strategy_config.get('trail_activation_pct', 0.5)
        
        # Timeframes
        self.sma_timeframe = self.strategy_config.get('sma_timeframe', '1m')
        self.atr_timeframe = self.strategy_config.get('atr_timeframe', '5m')
        
        self.logger.info(f"Strategy B initialized for {symbol}")
    
    def get_required_timeframes(self) -> List[str]:
        """
        Get the list of timeframes required by this strategy.
        
        Returns:
            List of timeframe strings (e.g., ['1m', '5m', '1h'])
        """
        # We need the SMA timeframe and the ATR timeframe
        timeframes = [self.sma_timeframe]
        if self.atr_timeframe != self.sma_timeframe:
            timeframes.append(self.atr_timeframe)
        return timeframes
    
    def calculate_indicators(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Calculate all indicators required by the strategy.
        
        Args:
            data: Dictionary of DataFrames containing price/volume data for different timeframes
                 Format: {'1m': df_1m, '5m': df_5m, ...}
                 
        Returns:
            Dictionary of DataFrames with indicators added as columns
        """
        result_data = {}
        
        # Process SMA timeframe
        if self.sma_timeframe in data and data[self.sma_timeframe] is not None:
            sma_df = data[self.sma_timeframe].copy()
            
            # Calculate fast and slow SMAs
            sma_df['fast_sma'] = calculate_sma(sma_df['close'], self.sma_fast_length)
            sma_df['slow_sma'] = calculate_sma(sma_df['close'], self.sma_slow_length)
            
            result_data[self.sma_timeframe] = sma_df
        else:
            self.logger.warning(f"No data available for SMA timeframe {self.sma_timeframe}")
        
        # Process ATR timeframe
        if self.atr_timeframe in data and data[self.atr_timeframe] is not None:
            atr_df = data[self.atr_timeframe].copy()
            
            # Calculate ATR
            try:
                atr_df['atr'] = calculate_atr(atr_df, self.atr_length)
            except Exception as e:
                self.logger.error(f"Error calculating ATR: {str(e)}")
                atr_df['atr'] = pd.Series(np.nan, index=atr_df.index)
            
            result_data[self.atr_timeframe] = atr_df
        else:
            self.logger.warning(f"No data available for ATR timeframe {self.atr_timeframe}")
        
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
            self.logger.warning(f"No data for SMA timeframe {self.sma_timeframe}")
            return signals
        
        if self.atr_timeframe not in data or data[self.atr_timeframe] is None:
            self.logger.warning(f"No data for ATR timeframe {self.atr_timeframe}")
            return signals
        
        # Get dataframes
        sma_df = data[self.sma_timeframe]
        atr_df = data[self.atr_timeframe]
        
        # We need at least 2 bars for signal generation
        if len(sma_df) < 2:
            self.logger.warning(f"Not enough data for SMA timeframe {self.sma_timeframe}")
            return signals
        
        # Get SMA values from current and previous bar
        try:
            curr_fast_sma = sma_df['fast_sma'].iloc[-1]
            curr_slow_sma = sma_df['slow_sma'].iloc[-1]
            prev_fast_sma = sma_df['fast_sma'].iloc[-2]
            prev_slow_sma = sma_df['slow_sma'].iloc[-2]
        except (IndexError, KeyError):
            self.logger.warning("SMA data not available for signal generation")
            return signals
        
        # Get ATR value from current bar (for TP/SL calculation)
        try:
            curr_atr = atr_df['atr'].iloc[-1]
        except (IndexError, KeyError):
            self.logger.warning("ATR data not available for TP/SL calculation")
            return signals
        
        # Get current price
        try:
            curr_price = sma_df['close'].iloc[-1]
            curr_timestamp = sma_df.index[-1].timestamp() * 1000  # ms timestamp
        except (IndexError, KeyError):
            self.logger.warning("Price data not available for signal generation")
            return signals
        
        # Check for crossovers
        
        # Bullish crossover (fast SMA crosses above slow SMA)
        if prev_fast_sma <= prev_slow_sma and curr_fast_sma > curr_slow_sma:
            self.logger.info(f"Bullish crossover detected at {curr_price}")
            
            # Calculate stop loss and take profit levels
            sl_price = curr_price - (curr_atr * self.trail_atr_mult)
            tp_price = curr_price + (curr_atr * self.tp_atr_mult)
            
            # Create trade signal
            signal = TradeSignal(
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                price=curr_price,
                timestamp=int(curr_timestamp),
                order_type=OrderType.MARKET,
                sl_price=sl_price,
                tp_price=tp_price,
                indicator_values={
                    'fast_sma': curr_fast_sma,
                    'slow_sma': curr_slow_sma,
                    'atr': curr_atr
                },
                metadata={
                    'trail_activation_pct': self.trail_activation_pct,
                    'trail_atr_mult': self.trail_atr_mult
                }
            )
            
            signals.append(signal)
        
        # Bearish crossover (fast SMA crosses below slow SMA)
        elif prev_fast_sma >= prev_slow_sma and curr_fast_sma < curr_slow_sma:
            self.logger.info(f"Bearish crossover detected at {curr_price}")
            
            # Calculate stop loss and take profit levels
            sl_price = curr_price + (curr_atr * self.trail_atr_mult)
            tp_price = curr_price - (curr_atr * self.tp_atr_mult)
            
            # Create trade signal
            signal = TradeSignal(
                signal_type=SignalType.SELL,
                symbol=self.symbol,
                price=curr_price,
                timestamp=int(curr_timestamp),
                order_type=OrderType.MARKET,
                sl_price=sl_price,
                tp_price=tp_price,
                indicator_values={
                    'fast_sma': curr_fast_sma,
                    'slow_sma': curr_slow_sma,
                    'atr': curr_atr
                },
                metadata={
                    'trail_activation_pct': self.trail_activation_pct,
                    'trail_atr_mult': self.trail_atr_mult
                }
            )
            
            signals.append(signal)
        
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
        
        # Check SMA lengths
        if self.sma_fast_length >= self.sma_slow_length:
            return False, f"Fast SMA length ({self.sma_fast_length}) must be less than slow SMA length ({self.sma_slow_length})"
        
        # Check multipliers
        if self.tp_atr_mult <= 0 or self.trail_atr_mult <= 0:
            return False, "ATR multipliers must be positive"
        
        # Check trail activation
        if self.trail_activation_pct < 0 or self.trail_activation_pct > 1:
            return False, "Trail activation percentage must be between 0 and 1"
        
        return True, None