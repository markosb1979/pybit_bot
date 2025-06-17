"""
Strategy Manager - Manages strategy loading, selection and execution
"""

import importlib
import sys
import os
import json
import logging
import inspect
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Type, Union

from pybit_bot.strategies.base_strategy import BaseStrategy, TradeSignal
from pybit_bot.utils.logger import Logger


class StrategyManager:
    """
    Strategy manager that handles loading and executing trading strategies
    """
    
    def __init__(self, config, logger=None):
        """
        Initialize the strategy manager with configuration.
        
        Args:
            config: Configuration dictionary
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger or Logger("StrategyManager")
        
        self.strategies = {}  # Dictionary of loaded strategies
        self.active_strategy = None  # Currently active strategy
        
        # Initialize
        self.logger.info("Initializing StrategyManager")
        self._load_strategies()
    
    def _load_strategies(self):
        """
        Load all enabled strategies from config.
        """
        self.logger.info("Loading strategies")
        
        try:
            # Get active strategy name from config
            active_strategy_name = self.config.get('strategy', {}).get('active_strategy', 'strategy_a')
            self.logger.info(f"Active strategy: {active_strategy_name}")
            
            # Get symbols from config
            symbols = self.config.get('general', {}).get('trading', {}).get('symbols', ["BTCUSDT"])
            default_symbol = symbols[0] if symbols else "BTCUSDT"
            self.logger.info(f"Using default symbol: {default_symbol}")
            
            # Import the module
            module_path = f"pybit_bot.strategies.{active_strategy_name}"
            self.logger.info(f"Importing strategy module: {module_path}")
            
            try:
                module = importlib.import_module(module_path)
                
                # Find strategy class in the module
                strategy_class = None
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, BaseStrategy) and 
                        obj is not BaseStrategy):
                        strategy_class = obj
                        break
                
                if not strategy_class:
                    self.logger.error(f"No strategy class found in {module_path}")
                    return
                
                # Initialize the strategy with the symbol
                strategy = strategy_class(self.config, default_symbol)
                
                # Add to strategies dictionary
                self.strategies[active_strategy_name] = strategy
                self.active_strategy = strategy
                
                self.logger.info(f"Successfully loaded strategy: {active_strategy_name}")
                
            except ImportError as e:
                self.logger.error(f"Error importing strategy {active_strategy_name}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error loading strategy {active_strategy_name}: {str(e)}")
                
        except Exception as e:
            self.logger.error(f"Error loading strategies: {str(e)}")
    
    async def process_data(self, symbol, data_dict):
        """
        Process market data with the active strategy.
        
        Args:
            symbol: Trading symbol
            data_dict: Dictionary of DataFrames by timeframe
            
        Returns:
            List of trade signals
        """
        signals = []
        
        try:
            # Get active strategy
            strategy = self.active_strategy
            if not strategy:
                return signals
                
            # Process data with strategy
            strategy_signals = await strategy.process_data(symbol, data_dict)
            
            # Log indicator values for the latest candle
            self._log_indicator_values(symbol, strategy, data_dict)
            
            if strategy_signals:
                signals.extend(strategy_signals)
                
            return signals
            
        except Exception as e:
            self.logger.error(f"Error processing data for {symbol}: {str(e)}")
            return []
    
    def _log_indicator_values(self, symbol, strategy, data_dict):
        """Log the values of all indicators for the latest candle"""
        try:
            # Get the default timeframe data
            default_tf = "1m"  # Assuming 1m is your primary timeframe
            if default_tf not in data_dict:
                return
                
            df = data_dict[default_tf]
            if df.empty or len(df) == 0:
                return
                
            # Get the latest candle
            latest_candle = df.iloc[-1]
            
            # Get timestamp in human-readable format
            timestamp = pd.to_datetime(latest_candle['timestamp'], unit='ms')
            
            # Log basic candle info
            self.logger.info(f"======= {symbol} {default_tf} CLOSE at {timestamp} =======")
            self.logger.info(f"OHLCV: Open={latest_candle['open']:.2f}, High={latest_candle['high']:.2f}, "
                          f"Low={latest_candle['low']:.2f}, Close={latest_candle['close']:.2f}, "
                          f"Volume={latest_candle['volume']:.2f}")
            
            # Log indicator values if they exist in the DataFrame
            indicators = ['luxfvgtrend', 'tva', 'cvd', 'vfi', 'atr']
            indicator_values = {}
            
            for indicator in indicators:
                # Check for common indicator column patterns
                for col in df.columns:
                    if indicator in col.lower():
                        indicator_values[col] = float(latest_candle[col])
            
            if indicator_values:
                self.logger.info(f"INDICATORS: {json.dumps(indicator_values, indent=2)}")
            
            print(f"Processed {symbol} {default_tf} candle close at {timestamp}")
            
        except Exception as e:
            self.logger.error(f"Error logging indicator values: {str(e)}")
    
    def get_active_strategies(self):
        """
        Get list of active strategy names.
        
        Returns:
            List of active strategy names
        """
        if self.active_strategy:
            return [self.active_strategy.__class__.__name__]
        return []