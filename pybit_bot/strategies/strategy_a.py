"""
Strategy A - Multi-indicator confluence strategy implementation.
Uses multiple technical indicators for signal generation:
- LuxFVGtrend (Fair Value Gap)
- TVA (Trend Volume Analysis)
- CVD (Cumulative Volume Delta)
- VFI (Volume Flow Imbalance)
- ATR (Average True Range)
"""

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

# Fix import to use absolute import path
from pybit_bot.strategies.base_strategy import BaseStrategy, TradeSignal, SignalType, OrderType


class StrategyA(BaseStrategy):
    """
    Strategy A implementation - multi-indicator confluence strategy.
    """
    
    def __init__(self, config: Dict, symbol: str):
        """
        Initialize Strategy A with configuration and symbol.
        
        Args:
            config: Strategy configuration dictionary
            symbol: Trading symbol (e.g., 'BTCUSDT')
        """
        super().__init__(config, symbol)
        self.logger = logging.getLogger(__name__)
        
        # Extract strategy-specific config
        self.strategy_config = config.get('strategy_a', {})
        self.indicator_config = config.get('indicators', {})
        self.timeframe_config = config.get('timeframes', {})
        
        # Store active trade tracking
        self.active_long_trades = 0
        self.active_short_trades = 0
        
        self.logger.info(f"Strategy A initialized for {symbol}")
    
    def get_required_timeframes(self) -> List[str]:
        """
        Get the list of timeframes required by this strategy.
        
        Returns:
            List of timeframe strings (e.g., ['1m', '5m', '1h'])
        """
        # Get default timeframe
        default_tf = self.timeframe_config.get('default', '1m')
        
        # Get indicator-specific timeframes
        indicator_tfs = self.timeframe_config.get('indicator_specific', {})
        
        # Combine all required timeframes
        timeframes = set([default_tf])
        for indicator, indicator_tf in indicator_tfs.items():
            if self.indicator_config.get(indicator, {}).get('enabled', False):
                timeframes.add(indicator_tf)
        
        return list(timeframes)
    
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
        default_tf = self.timeframe_config.get('default', '1m')
        indicator_tfs = self.timeframe_config.get('indicator_specific', {})
        
        # Process each timeframe
        for tf, df in data.items():
            if df is None or df.empty:
                self.logger.warning(f"Empty or None DataFrame for timeframe {tf}")
                continue
                
            # Create a copy to avoid modifying the original
            result_df = df.copy()
            
            # Calculate ATR if enabled and this is the correct timeframe
            if (self.indicator_config.get('atr', {}).get('enabled', False) and 
                tf == indicator_tfs.get('atr', default_tf)):
                
                # Fix import to use absolute path
                from pybit_bot.indicators.atr import calculate_atr
                atr_length = self.indicator_config.get('atr', {}).get('length', 14)
                try:
                    result_df['atr'] = calculate_atr(result_df, length=atr_length)
                    self.logger.debug(f"Calculated ATR for {tf} with length {atr_length}")
                except Exception as e:
                    self.logger.error(f"Error calculating ATR: {str(e)}")
                    result_df['atr'] = pd.Series(np.nan, index=result_df.index)
            
            # Calculate CVD if enabled and this is the correct timeframe
            if (self.indicator_config.get('cvd', {}).get('enabled', False) and 
                tf == indicator_tfs.get('cvd', default_tf)):
                
                # Fix import to use absolute path
                from pybit_bot.indicators.cvd import calculate_cvd
                cvd_length = self.indicator_config.get('cvd', {}).get('cumulation_length', 25)
                try:
                    result_df['cvd'] = calculate_cvd(result_df, cumulation_length=cvd_length)
                    self.logger.debug(f"Calculated CVD for {tf} with length {cvd_length}")
                except Exception as e:
                    self.logger.error(f"Error calculating CVD: {str(e)}")
                    result_df['cvd'] = pd.Series(np.nan, index=result_df.index)
            
            # Calculate TVA if enabled and this is the correct timeframe
            if (self.indicator_config.get('tva', {}).get('enabled', False) and 
                tf == indicator_tfs.get('tva', default_tf)):
                
                # Fix import to use absolute path
                from pybit_bot.indicators.tva import calculate_tva
                tva_length = self.indicator_config.get('tva', {}).get('length', 15)
                try:
                    rb, rr, db, dr, upper, lower = calculate_tva(result_df, length=tva_length)
                    result_df['tva_rb'] = rb
                    result_df['tva_rr'] = rr
                    result_df['tva_db'] = db
                    result_df['tva_dr'] = dr
                    result_df['tva_upper'] = upper
                    result_df['tva_lower'] = lower
                    self.logger.debug(f"Calculated TVA for {tf} with length {tva_length}")
                except Exception as e:
                    self.logger.error(f"Error calculating TVA: {str(e)}")
                    result_df['tva_rb'] = pd.Series(np.nan, index=result_df.index)
                    result_df['tva_rr'] = pd.Series(np.nan, index=result_df.index)
                    result_df['tva_db'] = pd.Series(np.nan, index=result_df.index)
                    result_df['tva_dr'] = pd.Series(np.nan, index=result_df.index)
            
            # Calculate VFI if enabled and this is the correct timeframe
            if (self.indicator_config.get('vfi', {}).get('enabled', False) and 
                tf == indicator_tfs.get('vfi', default_tf)):
                
                # Fix import to use absolute path
                from pybit_bot.indicators.vfi import calculate_vfi
                vfi_lookback = self.indicator_config.get('vfi', {}).get('lookback', 50)
                try:
                    result_df['vfi'] = calculate_vfi(result_df, lookback=vfi_lookback)
                    self.logger.debug(f"Calculated VFI for {tf} with lookback {vfi_lookback}")
                except Exception as e:
                    self.logger.error(f"Error calculating VFI: {str(e)}")
                    result_df['vfi'] = pd.Series(np.nan, index=result_df.index)
            
            # Calculate LuxFVGtrend if enabled and this is the correct timeframe
            if (self.indicator_config.get('luxfvgtrend', {}).get('enabled', False) and 
                tf == indicator_tfs.get('luxfvgtrend', default_tf)):
                
                # Fix import to use absolute path
                from pybit_bot.indicators.luxfvgtrend import calculate_luxfvgtrend
                try:
                    fvg_signal, fvg_midpoint, fvg_counter = calculate_luxfvgtrend(result_df)
                    result_df['fvg_signal'] = fvg_signal
                    result_df['fvg_midpoint'] = fvg_midpoint
                    result_df['fvg_counter'] = fvg_counter
                    self.logger.debug(f"Calculated LuxFVGtrend for {tf}")
                except Exception as e:
                    self.logger.error(f"Error calculating LuxFVGtrend: {str(e)}")
                    result_df['fvg_signal'] = pd.Series(np.nan, index=result_df.index)
                    result_df['fvg_midpoint'] = pd.Series(np.nan, index=result_df.index)
                    result_df['fvg_counter'] = pd.Series(np.nan, index=result_df.index)
            
            # Store the result
            result_data[tf] = result_df
        
        return result_data
    
    # Rest of the class implementation remains the same...