"""
Base Strategy - Abstract base class for all trading strategies
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd


class SignalType(Enum):
    """Signal types for trade signals"""
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    NONE = "NONE"


class OrderType(Enum):
    """Order types for trade signals"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"


class TradeSignal:
    """
    Trade signal class with all information needed for order execution
    """
    
    def __init__(
        self,
        signal_type: SignalType,
        direction: str = "LONG",
        strength: float = 1.0,
        timestamp: int = 0,
        price: float = 0.0,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a trade signal
        
        Args:
            signal_type: Type of signal (BUY, SELL, CLOSE)
            direction: Trade direction ("LONG" or "SHORT")
            strength: Signal strength from 0.0 to 1.0
            timestamp: Signal timestamp (milliseconds since epoch)
            price: Price at signal generation
            sl_price: Stop loss price
            tp_price: Take profit price
            order_type: Type of order to place (MARKET, LIMIT, etc.)
            metadata: Additional metadata for the signal
        """
        self.signal_type = signal_type
        self.direction = direction
        self.strength = strength
        self.timestamp = timestamp
        self.price = price
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.order_type = order_type
        self.metadata = metadata or {}


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies
    """
    
    def __init__(self, config: Dict, symbol: str):
        """
        Initialize the base strategy
        
        Args:
            config: Configuration dictionary
            symbol: Trading symbol this strategy is for
        """
        self.config = config
        self.symbol = symbol
    
    @abstractmethod
    async def process_data(self, symbol: str, data_dict: Dict[str, pd.DataFrame]) -> List[TradeSignal]:
        """
        Process market data and generate signals
        
        Args:
            symbol: Trading symbol
            data_dict: Dictionary of DataFrames with market data by timeframe
            
        Returns:
            List of trade signals
        """
        pass