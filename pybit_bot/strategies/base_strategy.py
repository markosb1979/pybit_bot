from enum import Enum
from typing import Dict, Any, Optional


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TradeSignal:
    """
    Trade signal with entry price, stop loss, and take profit.
    """
    
    def __init__(
        self, 
        signal_type: SignalType,
        symbol: str,
        price: float,
        timestamp: int,
        order_type: OrderType = OrderType.MARKET,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        indicator_values: Dict[str, float] = None,
        metadata: Dict[str, Any] = None
    ):
        self.signal_type = signal_type
        self.symbol = symbol
        self.price = price
        self.timestamp = timestamp
        self.order_type = order_type
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.indicator_values = indicator_values or {}
        self.metadata = metadata or {}
    
    @property
    def direction(self):
        """Return the direction (LONG/SHORT) based on signal type"""
        return "LONG" if self.signal_type == SignalType.BUY else "SHORT"
    
    def __str__(self):
        return f"{self.signal_type.value} {self.symbol} @ {self.price}"


class BaseStrategy:
    """
    Base class for all trading strategies.
    """
    
    def __init__(self, config: Dict, symbol: str):
        """Initialize strategy with configuration and symbol."""
        self.config = config
        self.symbol = symbol
    
    def generate_signals(self, data: Dict) -> list:
        """
        Generate trading signals based on market data.
        
        Args:
            data: Dictionary of DataFrames for different timeframes
            
        Returns:
            List of TradeSignal objects
        """
        raise NotImplementedError("Subclasses must implement generate_signals()")
    
    def get_required_timeframes(self) -> list:
        """
        Get the list of timeframes required by this strategy.
        
        Returns:
            List of timeframe strings (e.g., ['1m', '5m', '1h'])
        """
        raise NotImplementedError("Subclasses must implement get_required_timeframes()")
    
    def calculate_indicators(self, data: Dict) -> Dict:
        """
        Calculate indicators required by the strategy.
        
        Args:
            data: Dictionary of DataFrames for different timeframes
            
        Returns:
            Dictionary of DataFrames with indicators added
        """
        raise NotImplementedError("Subclasses must implement calculate_indicators()")