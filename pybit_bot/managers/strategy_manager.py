"""
Strategy Manager - Loads and manages trading strategies.
"""

import importlib
import logging
from typing import Dict, List, Any, Optional, Type

from pybit_bot.strategies.base_strategy import BaseStrategy, TradeSignal
from pybit_bot.utils.logger import Logger


class StrategyManager:
    """
    Manages strategy loading, instantiation, and execution.
    """
    
    def __init__(self, config: Dict[str, Any], logger=None):
        """
        Initialize the strategy manager.
        
        Args:
            config: Dictionary containing configuration information
            logger: Optional logger instance
        """
        self.logger = logger or Logger("StrategyManager")
        self.logger.info("Initializing StrategyManager")
        
        self.config = config
        self.strategy_config = config.get('strategy', {})
        self.active_strategies = {}
        self.strategy_instances = {}
        
        # Load strategies
        self._load_strategies()
    
    def _load_strategies(self):
        """Load and instantiate strategies based on configuration."""
        self.logger.info("Loading strategies")
        
        # Get the active strategy name from config
        active_strategy_name = self.strategy_config.get('active_strategy')
        
        if not active_strategy_name:
            self.logger.warning("No active strategy specified in config, using the first enabled strategy")
            # Fallback to using the first enabled strategy
            strategies_config = self.strategy_config.get('strategies', {})
            for name, strategy_config in strategies_config.items():
                if strategy_config.get('enabled', False):
                    active_strategy_name = name
                    break
        
        if not active_strategy_name:
            self.logger.error("No active or enabled strategies found in configuration")
            return
            
        self.logger.info(f"Active strategy: {active_strategy_name}")
        
        # Get the active strategy's configuration
        strategies_config = self.strategy_config.get('strategies', {})
        active_strategy_config = strategies_config.get(active_strategy_name, {})
        
        # Only proceed if the strategy is enabled
        if not active_strategy_config.get('enabled', False):
            self.logger.warning(f"Active strategy '{active_strategy_name}' is not enabled in config")
            return
            
        # Import the strategy module
        try:
            # Convert snake_case to CamelCase for class name
            class_name = ''.join(word.title() for word in active_strategy_name.split('_'))
            module_name = f"pybit_bot.strategies.{active_strategy_name}"
            
            self.logger.info(f"Importing strategy module: {module_name}")
            module = importlib.import_module(module_name)
            
            # Get the strategy class
            strategy_class = getattr(module, class_name)
            
            # Record the strategy
            self.active_strategies[active_strategy_name] = strategy_class
            
            self.logger.info(f"Successfully loaded strategy: {active_strategy_name}")
            
        except (ImportError, AttributeError) as e:
            self.logger.error(f"Failed to load strategy '{active_strategy_name}': {str(e)}")
    
    def get_active_strategies(self) -> List[str]:
        """
        Get the list of active strategy names.
        
        Returns:
            List of strategy names
        """
        return list(self.active_strategies.keys())
    
    async def initialize_strategies(self, symbols: List[str]):
        """
        Initialize strategy instances for each symbol.
        
        Args:
            symbols: List of trading symbols
        """
        self.logger.info(f"Initializing strategies for symbols: {symbols}")
        
        for symbol in symbols:
            if symbol not in self.strategy_instances:
                self.strategy_instances[symbol] = {}
                
            for strategy_name, strategy_class in self.active_strategies.items():
                try:
                    # Initialize the strategy with the symbol
                    strategy_instance = strategy_class(self.config, symbol)
                    
                    # Store the instance
                    self.strategy_instances[symbol][strategy_name] = strategy_instance
                    
                    self.logger.info(f"Initialized {strategy_name} for {symbol}")
                    
                except Exception as e:
                    self.logger.error(f"Error initializing {strategy_name} for {symbol}: {str(e)}")
    
    async def process_data(self, symbol: str, data: Dict[str, Any]) -> List[TradeSignal]:
        """
        Process market data through strategies and generate trade signals.
        
        Args:
            symbol: Trading symbol
            data: Dictionary of DataFrames for different timeframes
            
        Returns:
            List of trade signals
        """
        signals = []
        
        # Check if we have strategies for this symbol
        if symbol not in self.strategy_instances:
            return signals
            
        # Process each active strategy
        for strategy_name, strategy in self.strategy_instances[symbol].items():
            try:
                # Calculate indicators
                processed_data = strategy.calculate_indicators(data)
                
                # Generate signals
                strategy_signals = strategy.generate_signals(processed_data)
                
                if strategy_signals:
                    self.logger.info(f"Strategy {strategy_name} generated {len(strategy_signals)} signals for {symbol}")
                    signals.extend(strategy_signals)
                    
            except Exception as e:
                self.logger.error(f"Error processing {strategy_name} for {symbol}: {str(e)}")
        
        return signals