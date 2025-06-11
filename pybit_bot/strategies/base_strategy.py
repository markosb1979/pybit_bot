"""
Base strategy class that defines the interface for all trading strategies.
All concrete strategies (Strategy A, Strategy B) must inherit from this class.
"""

import abc
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd
from enum import Enum


class SignalType(Enum):
    """Enum representing different types of trading signals"""
    BUY = "BUY"
    SELL = "SELL"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    NONE = "NONE"


class OrderType(Enum):
    """Enum representing different types of orders"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TradeSignal:
    """Class representing a trade signal with all necessary details"""
    
    def __init__(
        self,
        signal_type: SignalType,
        symbol: str,
        price: float,
        timestamp: int,
        order_type: OrderType = OrderType.MARKET,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        quantity: Optional[float] = None,
        indicator_values: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict] = None
    ):
        self.signal_type = signal_type
        self.symbol = symbol
        self.price = price
        self.timestamp = timestamp
        self.order_type = order_type
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.quantity = quantity
        self.indicator_values = indicator_values or {}
        self.metadata = metadata or {}
    
    def __str__(self) -> str:
        return (f"TradeSignal({self.signal_type.value}, {self.symbol}, "
                f"price={self.price}, order_type={self.order_type.value})")


class BaseStrategy(abc.ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(self, config: Dict, symbol: str):
        """
        Initialize the strategy with configuration and symbol
        
        Args:
            config: Strategy configuration dictionary
            symbol: Trading symbol (e.g., 'BTCUSDT')
        """
        self.config = config
        self.symbol = symbol
        self.name = self.__class__.__name__
        self.is_active = True
        
    @abc.abstractmethod
    def calculate_indicators(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Calculate all indicators required by the strategy.
        
        Args:
            data: Dictionary of DataFrames containing price/volume data for different timeframes
                 Format: {'1m': df_1m, '5m': df_5m, ...}
                 
        Returns:
            Dictionary of DataFrames with indicators added as columns
        """
        pass
    
    @abc.abstractmethod
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> List[TradeSignal]:
        """
        Generate trading signals based on the calculated indicators.
        
        Args:
            data: Dictionary of DataFrames with indicators
            
        Returns:
            List of TradeSignal objects
        """
        pass
    
    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the strategy configuration has all required parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Base implementation always returns valid
        # Child classes should override with specific validation
        return True, None
    
    def get_required_timeframes(self) -> List[str]:
        """
        Get the list of timeframes required by this strategy.
        
        Returns:
            List of timeframe strings (e.g., ['1m', '5m', '1h'])
        """
        # Default implementation - child classes should override
        return ['1m']
    
    def get_state(self) -> Dict:
        """
        Get the current state of the strategy for persistence.
        
        Returns:
            Dictionary containing strategy state
        """
        return {
            'name': self.name,
            'symbol': self.symbol,
            'is_active': self.is_active
        }
    
    def restore_state(self, state: Dict) -> None:
        """
        Restore strategy state from a persisted state dictionary.
        
        Args:
            state: Dictionary containing strategy state
        """
        if state.get('name') == self.name:
            self.is_active = state.get('is_active', True)