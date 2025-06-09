"""
Custom exceptions for the PyBit Bot
"""

class BybitAPIError(Exception):
    """Base exception for Bybit API errors"""
    pass


class AuthenticationError(BybitAPIError):
    """Authentication failure with API keys"""
    pass


class RateLimitError(BybitAPIError):
    """Rate limit exceeded"""
    pass


class InvalidOrderError(BybitAPIError):
    """Invalid order parameters"""
    pass


class ConfigurationError(Exception):
    """Invalid configuration settings"""
    pass


class WebSocketError(Exception):
    """WebSocket connection error"""
    pass


class IndicatorError(Exception):
    """Error in indicator calculation"""
    pass


class OrderExecutionError(Exception):
    """Error executing an order"""
    pass


class InsufficientBalanceError(Exception):
    """Insufficient balance for operation"""
    pass