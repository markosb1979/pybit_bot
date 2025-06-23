"""
Signal model - Trading signals and related types

This module defines the signal data structures used for communication
between strategy components and execution components.
"""

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class SignalType(enum.Enum):
    """
    Types of trading signals
    """
    LONG = "LONG"  # Long entry signal
    SHORT = "SHORT"  # Short entry signal
    CLOSE_LONG = "CLOSE_LONG"  # Close long position
    CLOSE_SHORT = "CLOSE_SHORT"  # Close short position
    CANCEL = "CANCEL"  # Cancel pending orders


@dataclass
class Signal:
    """
    Trading signal data structure
    
    Contains all information about a trading signal, including
    symbol, direction, price, and additional metadata.
    """
    # Required fields
    symbol: str
    signal_type: SignalType
    timestamp: datetime
    price: float
    
    # Optional fields
    timeframe: str = "1m"
    strategy_name: str = "default"
    confidence: float = 1.0
    expiry: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """
        Initialize default values after creation
        """
        # Set default expiry if not provided
        if self.expiry is None:
            self.expiry = self.timestamp + timedelta(minutes=5)
            
        # Initialize empty metadata dict if not provided
        if self.metadata is None:
            self.metadata = {}
    
    def is_expired(self) -> bool:
        """
        Check if the signal has expired
        
        Returns:
            True if signal has expired, False otherwise
        """
        return datetime.now() > self.expiry
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert signal to dictionary for serialization
        
        Returns:
            Dictionary representation of the signal
        """
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "confidence": self.confidence,
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Signal':
        """
        Create signal from dictionary
        
        Args:
            data: Dictionary representation of signal
            
        Returns:
            Signal instance
        """
        signal_type = SignalType(data["signal_type"])
        timestamp = datetime.fromisoformat(data["timestamp"])
        expiry = None
        if data.get("expiry"):
            expiry = datetime.fromisoformat(data["expiry"])
            
        return cls(
            symbol=data["symbol"],
            signal_type=signal_type,
            timestamp=timestamp,
            price=data["price"],
            timeframe=data.get("timeframe", "1m"),
            strategy_name=data.get("strategy_name", "default"),
            confidence=data.get("confidence", 1.0),
            expiry=expiry,
            metadata=data.get("metadata", {})
        )