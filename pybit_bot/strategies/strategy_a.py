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

from strategies.base_strategy import BaseStrategy, TradeSignal, SignalType, OrderType


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
                
                from indicators.atr import calculate_atr
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
                
                from indicators.cvd import calculate_cvd
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
                
                from indicators.tva import calculate_tva
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
                
                from indicators.vfi import calculate_vfi
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
                
                from indicators.luxfvgtrend import calculate_luxfvgtrend
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
        
        # Get primary timeframe data
        default_tf = self.timeframe_config.get('default', '1m')
        if default_tf not in data or data[default_tf] is None or data[default_tf].empty:
            self.logger.warning(f"No data available for primary timeframe {default_tf}")
            return signals
        
        # Get dataframe for primary timeframe
        df = data[default_tf]
        
        # Check if we have enough data
        if len(df) < 2:
            self.logger.warning("Not enough data to generate signals")
            return signals
        
        # We need the previous (completed) bar for signal generation
        prev_bar_idx = -2
        
        # Get indicator values from previous bar
        try:
            # Check if all required indicators are available
            indicator_values = self._get_indicator_values(data, prev_bar_idx)
            if indicator_values is None:
                return signals
                
            # Check for entry conditions based on indicator confluence
            long_signal, short_signal = self._check_confluence(indicator_values)
            
            # Generate trade signals if conditions are met
            if long_signal and self.active_long_trades < self.strategy_config.get('entry_settings', {}).get('max_long_trades', 1):
                signal = self._create_long_signal(df, indicator_values, prev_bar_idx)
                if signal:
                    signals.append(signal)
                    
            if short_signal and self.active_short_trades < self.strategy_config.get('entry_settings', {}).get('max_short_trades', 1):
                signal = self._create_short_signal(df, indicator_values, prev_bar_idx)
                if signal:
                    signals.append(signal)
                    
        except Exception as e:
            self.logger.error(f"Error generating signals: {str(e)}", exc_info=True)
        
        return signals
    
    def _get_indicator_values(self, data: Dict[str, pd.DataFrame], idx: int) -> Optional[Dict]:
        """
        Get all required indicator values for the specified bar index.
        
        Args:
            data: Dictionary of DataFrames with indicators
            idx: Bar index to get values for
            
        Returns:
            Dictionary of indicator values or None if missing data
        """
        values = {}
        default_tf = self.timeframe_config.get('default', '1m')
        indicator_tfs = self.timeframe_config.get('indicator_specific', {})
        
        # Get ATR value
        if self.indicator_config.get('atr', {}).get('enabled', False):
            tf = indicator_tfs.get('atr', default_tf)
            if tf in data and 'atr' in data[tf].columns:
                try:
                    values['atr'] = data[tf]['atr'].iloc[idx]
                except IndexError:
                    self.logger.warning(f"ATR data not available at index {idx}")
                    return None
            else:
                self.logger.warning(f"ATR data not available for timeframe {tf}")
                return None
        
        # Get CVD value
        if self.indicator_config.get('cvd', {}).get('enabled', False):
            tf = indicator_tfs.get('cvd', default_tf)
            if tf in data and 'cvd' in data[tf].columns:
                try:
                    values['cvd'] = data[tf]['cvd'].iloc[idx]
                except IndexError:
                    self.logger.warning(f"CVD data not available at index {idx}")
                    return None
            else:
                self.logger.warning(f"CVD data not available for timeframe {tf}")
                return None
        
        # Get TVA values
        if self.indicator_config.get('tva', {}).get('enabled', False):
            tf = indicator_tfs.get('tva', default_tf)
            if tf in data and 'tva_rb' in data[tf].columns and 'tva_rr' in data[tf].columns:
                try:
                    values['tva_rb'] = data[tf]['tva_rb'].iloc[idx]
                    values['tva_rr'] = data[tf]['tva_rr'].iloc[idx]
                except IndexError:
                    self.logger.warning(f"TVA data not available at index {idx}")
                    return None
            else:
                self.logger.warning(f"TVA data not available for timeframe {tf}")
                return None
        
        # Get VFI value
        if self.indicator_config.get('vfi', {}).get('enabled', False):
            tf = indicator_tfs.get('vfi', default_tf)
            if tf in data and 'vfi' in data[tf].columns:
                try:
                    values['vfi'] = data[tf]['vfi'].iloc[idx]
                except IndexError:
                    self.logger.warning(f"VFI data not available at index {idx}")
                    return None
            else:
                self.logger.warning(f"VFI data not available for timeframe {tf}")
                return None
        
        # Get FVG values
        if self.indicator_config.get('luxfvgtrend', {}).get('enabled', False):
            tf = indicator_tfs.get('luxfvgtrend', default_tf)
            if tf in data and 'fvg_signal' in data[tf].columns and 'fvg_midpoint' in data[tf].columns:
                try:
                    values['fvg_signal'] = data[tf]['fvg_signal'].iloc[idx]
                    values['fvg_midpoint'] = data[tf]['fvg_midpoint'].iloc[idx]
                except IndexError:
                    self.logger.warning(f"FVG data not available at index {idx}")
                    return None
            else:
                self.logger.warning(f"FVG data not available for timeframe {tf}")
                return None
        
        # Get price data from default timeframe
        try:
            values['close'] = data[default_tf]['close'].iloc[idx]
            values['high'] = data[default_tf]['high'].iloc[idx]
            values['low'] = data[default_tf]['low'].iloc[idx]
            values['timestamp'] = data[default_tf].index[idx].timestamp() * 1000  # ms timestamp
        except (IndexError, KeyError):
            self.logger.warning(f"Price data not available at index {idx}")
            return None
        
        return values
    
    def _check_confluence(self, indicator_values: Dict) -> Tuple[bool, bool]:
        """
        Check if indicators show confluence for long or short signals.
        
        Args:
            indicator_values: Dictionary of indicator values
            
        Returns:
            Tuple of (long_signal, short_signal) booleans
        """
        # Default to no signals
        long_signal = True
        short_signal = True
        
        # Check if filter confluence is required
        filter_confluence = self.strategy_config.get('filter_confluence', True)
        
        # Check CVD
        if self.indicator_config.get('cvd', {}).get('enabled', False):
            cvd = indicator_values.get('cvd', 0)
            if filter_confluence:
                long_signal = long_signal and cvd > 0
                short_signal = short_signal and cvd < 0
        
        # Check TVA
        if self.indicator_config.get('tva', {}).get('enabled', False):
            tva_rb = indicator_values.get('tva_rb', 0)
            tva_rr = indicator_values.get('tva_rr', 0)
            if filter_confluence:
                long_signal = long_signal and tva_rb > 0
                short_signal = short_signal and tva_rr > 0
        
        # Check VFI
        if self.indicator_config.get('vfi', {}).get('enabled', False):
            vfi = indicator_values.get('vfi', 0)
            if filter_confluence:
                long_signal = long_signal and vfi > 0
                short_signal = short_signal and vfi < 0
        
        # Check FVG
        if self.indicator_config.get('luxfvgtrend', {}).get('enabled', False):
            fvg_signal = indicator_values.get('fvg_signal', 0)
            if filter_confluence:
                long_signal = long_signal and fvg_signal == 1
                short_signal = short_signal and fvg_signal == -1
        
        return long_signal, short_signal
    
    def _create_long_signal(self, df: pd.DataFrame, indicator_values: Dict, idx: int) -> Optional[TradeSignal]:
        """
        Create a long trade signal.
        
        Args:
            df: DataFrame with price data
            indicator_values: Dictionary of indicator values
            idx: Bar index
            
        Returns:
            TradeSignal object or None
        """
        # Determine entry price
        use_limit_entry = self.strategy_config.get('use_limit_entries', True)
        
        # Get entry price
        if use_limit_entry and 'fvg_midpoint' in indicator_values and indicator_values['fvg_midpoint'] > 0:
            # FVG midpoint + ATR for limit entry
            entry_price = indicator_values['fvg_midpoint'] + indicator_values.get('atr', 0)
            order_type = OrderType.LIMIT
        else:
            # Market entry at close price
            entry_price = indicator_values['close']
            order_type = OrderType.MARKET
        
        # Calculate stop loss and take profit levels
        risk_settings = self.strategy_config.get('risk_settings', {})
        sl_multiplier = risk_settings.get('stop_loss_multiplier', 2.0)
        tp_multiplier = risk_settings.get('take_profit_multiplier', 4.0)
        
        sl_price = entry_price - (indicator_values.get('atr', 0) * sl_multiplier)
        tp_price = entry_price + (indicator_values.get('atr', 0) * tp_multiplier)
        
        # Create trade signal
        signal = TradeSignal(
            signal_type=SignalType.BUY,
            symbol=self.symbol,
            price=entry_price,
            timestamp=int(indicator_values['timestamp']),
            order_type=order_type,
            sl_price=sl_price,
            tp_price=tp_price,
            indicator_values={
                k: v for k, v in indicator_values.items() 
                if k not in ['timestamp', 'close', 'high', 'low']
            }
        )
        
        return signal
    
    def _create_short_signal(self, df: pd.DataFrame, indicator_values: Dict, idx: int) -> Optional[TradeSignal]:
        """
        Create a short trade signal.
        
        Args:
            df: DataFrame with price data
            indicator_values: Dictionary of indicator values
            idx: Bar index
            
        Returns:
            TradeSignal object or None
        """
        # Determine entry price
        use_limit_entry = self.strategy_config.get('use_limit_entries', True)
        
        # Get entry price
        if use_limit_entry and 'fvg_midpoint' in indicator_values and indicator_values['fvg_midpoint'] > 0:
            # FVG midpoint - ATR for limit entry
            entry_price = indicator_values['fvg_midpoint'] - indicator_values.get('atr', 0)
            order_type = OrderType.LIMIT
        else:
            # Market entry at close price
            entry_price = indicator_values['close']
            order_type = OrderType.MARKET
        
        # Calculate stop loss and take profit levels
        risk_settings = self.strategy_config.get('risk_settings', {})
        sl_multiplier = risk_settings.get('stop_loss_multiplier', 2.0)
        tp_multiplier = risk_settings.get('take_profit_multiplier', 4.0)
        
        sl_price = entry_price + (indicator_values.get('atr', 0) * sl_multiplier)
        tp_price = entry_price - (indicator_values.get('atr', 0) * tp_multiplier)
        
        # Create trade signal
        signal = TradeSignal(
            signal_type=SignalType.SELL,
            symbol=self.symbol,
            price=entry_price,
            timestamp=int(indicator_values['timestamp']),
            order_type=order_type,
            sl_price=sl_price,
            tp_price=tp_price,
            indicator_values={
                k: v for k, v in indicator_values.items() 
                if k not in ['timestamp', 'close', 'high', 'low']
            }
        )
        
        return signal
    
    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the strategy configuration has all required parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if strategy section exists
        if not self.strategy_config:
            return False, "Missing 'strategy_a' section in configuration"
        
        # Check if at least one indicator is enabled
        indicators_enabled = False
        for indicator in ['atr', 'cvd', 'tva', 'vfi', 'luxfvgtrend']:
            if self.indicator_config.get(indicator, {}).get('enabled', False):
                indicators_enabled = True
                break
        
        if not indicators_enabled:
            return False, "No indicators are enabled"
        
        # Check if ATR is enabled (required for TP/SL calculations)
        if not self.indicator_config.get('atr', {}).get('enabled', False):
            return False, "ATR indicator must be enabled for TP/SL calculations"
        
        return True, None