"""
Strategy Manager - Coordinates strategy execution and signal generation

This module manages the loading, initialization and execution of trading strategies.
It processes market data through strategies and collects generated signals.
"""

import os
import importlib
import inspect
import asyncio
from typing import Dict, List, Any, Optional
import pandas as pd

from ..utils.logger import Logger
from ..strategies.base_strategy import BaseStrategy, TradeSignal, SignalType

# Rename/alias TradeSignal as Signal for compatibility
Signal = TradeSignal


class StrategyManager:
    """
    Strategy Manager coordinates strategy execution and signal generation
    """
    
    def __init__(self, data_manager, config, logger=None):
        """
        Initialize the strategy manager
        
        Args:
            data_manager: DataManager instance for market data access
            config: Application configuration
            logger: Optional logger instance
        """
        self.logger = logger or Logger("StrategyManager")
        self.logger.debug(f"ENTER __init__()")
        
        self.data_manager = data_manager
        self.config = config
        
        # Strategy configuration
        self.strategy_config = config.get('strategy', {})
        
        # Map of active strategies by symbol
        self.strategies = {}
        
        # Load strategies
        self._load_strategies()
        
        self.logger.debug(f"EXIT __init__ completed")
    
    def _load_strategies(self):
        """
        Load and initialize strategy classes based on configuration
        """
        self.logger.debug(f"ENTER _load_strategies()")
        
        # Get list of enabled strategies
        enabled_strategies = self.strategy_config.get('enabled_strategies', [])
        
        if not enabled_strategies:
            self.logger.warning("No strategies enabled in configuration")
            return
            
        # Get trading symbols
        symbols = self.config.get('general', {}).get('trading', {}).get('symbols', [])
        
        if not symbols:
            self.logger.warning("No trading symbols configured")
            return
            
        # Load each strategy for each symbol
        for strategy_name in enabled_strategies:
            self.logger.info(f"Loading strategy: {strategy_name}")
            
            try:
                # Determine the strategy class name
                class_name = self._get_strategy_class_name(strategy_name)
                
                # Import the strategy module
                module_name = f"pybit_bot.strategies.{strategy_name}"
                module = importlib.import_module(module_name)
                
                # Get the strategy class
                strategy_class = getattr(module, class_name)
                
                # Create strategy instances for each symbol
                for symbol in symbols:
                    # Create strategy instance
                    strategy = strategy_class(self.config, symbol)
                    
                    # Validate strategy configuration
                    if hasattr(strategy, 'validate_config'):
                        is_valid, error_msg = strategy.validate_config()
                        if not is_valid:
                            self.logger.error(f"Invalid configuration for {strategy_name}: {error_msg}")
                            continue
                    
                    # Initialize symbol entry if not exists
                    if symbol not in self.strategies:
                        self.strategies[symbol] = []
                        
                    # Add strategy to the list
                    self.strategies[symbol].append(strategy)
                    self.logger.info(f"Initialized {strategy_name} for {symbol}")
            
            except Exception as e:
                self.logger.error(f"Error loading strategy {strategy_name}: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
        
        # Log loaded strategies summary
        for symbol, symbol_strategies in self.strategies.items():
            strategy_names = [s.__class__.__name__ for s in symbol_strategies]
            self.logger.info(f"Loaded {len(symbol_strategies)} strategies for {symbol}: {strategy_names}")
        
        self.logger.debug(f"EXIT _load_strategies completed")
    
    def _get_strategy_class_name(self, strategy_id: str) -> str:
        """
        Convert strategy ID to class name
        
        Args:
            strategy_id: Strategy identifier (e.g., 'strategy_a')
            
        Returns:
            Strategy class name (e.g., 'StrategyA')
        """
        # Convert snake_case to CamelCase
        parts = strategy_id.split('_')
        class_name = ''.join(part.capitalize() for part in parts)
        return class_name
    
    async def evaluate(self, symbol: str, market_data: Optional[Dict[str, pd.DataFrame]] = None) -> List[Signal]:
        """
        Evaluate strategies for a specific symbol with the latest market data
        
        Args:
            symbol: Trading symbol
            market_data: Optional market data dictionary (if None, fetched from data manager)
            
        Returns:
            List of signals generated by all strategies
        """
        self.logger.debug(f"ENTER evaluate(symbol={symbol})")
        
        all_signals = []
        
        # Check if we have strategies for this symbol
        if symbol not in self.strategies or not self.strategies[symbol]:
            self.logger.debug(f"No strategies for {symbol}")
            self.logger.debug(f"EXIT evaluate returned empty signals")
            return all_signals
            
        # Get market data if not provided
        if market_data is None:
            market_data = {}
            # Get all timeframes
            timeframes = self.config.get('general', {}).get('trading', {}).get('timeframes', ['1m'])
            
            # Get data for each timeframe
            for timeframe in timeframes:
                df = self.data_manager.get_klines(symbol, timeframe)
                if df is not None and not df.empty:
                    market_data[timeframe] = df
        
        # Run each strategy
        for strategy in self.strategies[symbol]:
            try:
                # Process market data with strategy
                signals = await strategy.process_data(symbol, market_data)
                
                # Add valid signals to results
                for signal in signals:
                    # Skip None or NONE signals
                    if signal.signal_type == SignalType.NONE:
                        continue
                        
                    all_signals.append(signal)
                    
                    # Log signal
                    self.logger.info(f"Signal from {strategy.__class__.__name__}: {signal.signal_type.name} at {signal.price}")
                    
            except Exception as e:
                self.logger.error(f"Error evaluating {strategy.__class__.__name__} for {symbol}: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
        
        self.logger.debug(f"EXIT evaluate returned {len(all_signals)} signals")
        return all_signals
        
    async def get_strategy_status(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the status of all strategies or for a specific symbol
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            Dictionary with strategy status information
        """
        self.logger.debug(f"ENTER get_strategy_status(symbol={symbol})")
        
        status = {}
        
        # Get all symbols or just the requested one
        symbols = [symbol] if symbol else list(self.strategies.keys())
        
        for sym in symbols:
            if sym not in self.strategies:
                continue
                
            status[sym] = []
            
            for strategy in self.strategies[sym]:
                # Get strategy info
                strategy_info = {
                    'name': strategy.__class__.__name__,
                    'type': strategy.__class__.__module__.split('.')[-1]
                }
                
                # Add additional information if available
                if hasattr(strategy, 'get_status'):
                    try:
                        strategy_info.update(strategy.get_status())
                    except Exception as e:
                        self.logger.error(f"Error getting status for {strategy.__class__.__name__}: {str(e)}")
                
                status[sym].append(strategy_info)
        
        self.logger.debug(f"EXIT get_strategy_status returned status")
        return status