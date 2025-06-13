"""
Strategy Manager - Coordinates multiple trading strategies.
Responsible for initializing strategies, routing market data,
and collecting trade signals.
"""

import logging
from typing import Dict, List, Any, Optional, Set, Type
import importlib
import inspect
import os

from pybit_bot.strategies.base_strategy import BaseStrategy, TradeSignal


class StrategyManager:
    """
    Manages multiple trading strategies, coordinates data flow,
    and collects signals.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the strategy manager with configuration.
        
        Args:
            config: Global configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.strategies: Dict[str, BaseStrategy] = {}
        self.active_strategies: Set[str] = set()
        self.required_timeframes: Dict[str, Set[str]] = {}  # symbol -> set of timeframes
        
        # Initialize strategies
        self._load_strategies()
    
    def _load_strategies(self):
        """
        Load and initialize strategy instances based on configuration.
        """
        strategy_config = self.config.get('strategies', {})
        symbols = self.config.get('trading', {}).get('symbols', [])
        
        if not symbols:
            self.logger.warning("No trading symbols configured")
            return
            
        # Try to load strategies
        for strategy_name, strategy_settings in strategy_config.items():
            if not strategy_settings.get('enabled', False):
                self.logger.info(f"Strategy {strategy_name} is disabled, skipping")
                continue
                
            try:
                # Load the strategy class
                strategy_class = self._get_strategy_class(strategy_name)
                if not strategy_class:
                    self.logger.error(f"Could not load strategy class for {strategy_name}")
                    continue
                    
                # Initialize for each symbol
                for symbol in symbols:
                    strategy_id = f"{strategy_name}_{symbol}"
                    self.logger.info(f"Initializing strategy {strategy_id}")
                    
                    # Create strategy instance
                    strategy = strategy_class(self.config, symbol)
                    
                    # Validate the configuration
                    is_valid, error_msg = strategy.validate_config()
                    if not is_valid:
                        self.logger.error(f"Invalid configuration for {strategy_id}: {error_msg}")
                        continue
                        
                    # Store the strategy
                    self.strategies[strategy_id] = strategy
                    self.active_strategies.add(strategy_id)
                    
                    # Track required timeframes for this symbol
                    if symbol not in self.required_timeframes:
                        self.required_timeframes[symbol] = set()
                    
                    self.required_timeframes[symbol].update(strategy.get_required_timeframes())
                    
                    self.logger.info(f"Strategy {strategy_id} initialized successfully")
                    
            except Exception as e:
                self.logger.error(f"Error initializing strategy {strategy_name}: {str(e)}", exc_info=True)
    
    def _get_strategy_class(self, strategy_name: str) -> Optional[Type[BaseStrategy]]:
        """
        Dynamically load a strategy class by name.
        
        Args:
            strategy_name: Name of the strategy (e.g., 'strategy_a')
            
        Returns:
            Strategy class or None if not found
        """
        try:
            # Convert strategy name to expected module name (e.g., strategy_a -> pybit_bot.strategies.strategy_a)
            module_name = f"pybit_bot.strategies.{strategy_name.lower()}"
            
            # Import the module
            module = importlib.import_module(module_name)
            
            # Find strategy class in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseStrategy) and obj != BaseStrategy:
                    return obj
                    
            # If we reach here, no suitable strategy class was found
            self.logger.error(f"No BaseStrategy subclass found in module {module_name}")
            return None
            
        except ImportError as e:
            self.logger.error(f"Could not import strategy module {strategy_name}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting strategy class {strategy_name}: {str(e)}")
            return None
    
    def get_required_timeframes(self, symbol: str) -> List[str]:
        """
        Get all unique timeframes required by strategies for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            List of required timeframe strings
        """
        return list(self.required_timeframes.get(symbol, set()))
    
    def get_all_symbols(self) -> List[str]:
        """
        Get all symbols that have active strategies.
        
        Returns:
            List of symbol strings
        """
        return list(self.required_timeframes.keys())
    
    def process_market_data(self, symbol: str, data: Dict[str, Any]) -> List[TradeSignal]:
        """
        Process market data and collect signals from all active strategies.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            data: Dictionary of market data for different timeframes
                 Format: {'1m': df_1m, '5m': df_5m, ...}
        
        Returns:
            List of trade signals from all strategies
        """
        signals = []
        
        # Process data with each active strategy for this symbol
        for strategy_id, strategy in self.strategies.items():
            if strategy_id not in self.active_strategies:
                continue
                
            # Check if this strategy is for the current symbol
            if not strategy_id.endswith(f"_{symbol}"):
                continue
                
            try:
                # Calculate indicators
                data_with_indicators = strategy.calculate_indicators(data)
                
                # Generate signals
                strategy_signals = strategy.generate_signals(data_with_indicators)
                
                # Add to overall signals list
                signals.extend(strategy_signals)
                
                # Log results
                if strategy_signals:
                    self.logger.info(f"Strategy {strategy_id} generated {len(strategy_signals)} signals")
                    
            except Exception as e:
                self.logger.error(f"Error processing data with strategy {strategy_id}: {str(e)}", exc_info=True)
        
        return signals
    
    def is_strategy_active(self, strategy_id: str) -> bool:
        """
        Check if a strategy is active.
        
        Args:
            strategy_id: Strategy identifier (e.g., 'strategy_a_BTCUSDT')
            
        Returns:
            True if the strategy is active, False otherwise
        """
        return strategy_id in self.active_strategies
    
    def activate_strategy(self, strategy_id: str) -> bool:
        """
        Activate a strategy.
        
        Args:
            strategy_id: Strategy identifier (e.g., 'strategy_a_BTCUSDT')
            
        Returns:
            True if successful, False otherwise
        """
        if strategy_id in self.strategies:
            self.active_strategies.add(strategy_id)
            self.logger.info(f"Activated strategy {strategy_id}")
            return True
        else:
            self.logger.warning(f"Cannot activate unknown strategy {strategy_id}")
            return False
    
    def deactivate_strategy(self, strategy_id: str) -> bool:
        """
        Deactivate a strategy.
        
        Args:
            strategy_id: Strategy identifier (e.g., 'strategy_a_BTCUSDT')
            
        Returns:
            True if successful, False otherwise
        """
        if strategy_id in self.active_strategies:
            self.active_strategies.remove(strategy_id)
            self.logger.info(f"Deactivated strategy {strategy_id}")
            return True
        else:
            self.logger.warning(f"Strategy {strategy_id} is not active")
            return False
    
    def shutdown(self):
        """
        Perform any cleanup before shutdown.
        """
        self.logger.info("Shutting down Strategy Manager")
        self.active_strategies.clear()
        self.strategies.clear()