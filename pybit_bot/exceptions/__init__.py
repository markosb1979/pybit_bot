"""
Exception classes for pybit_bot
"""

class BybitAPIError(Exception):
    """Base exception for all Bybit API errors"""
    pass

class AuthenticationError(BybitAPIError):
    """Authentication failed or invalid credentials"""
    pass

class RateLimitError(BybitAPIError):
    """Rate limit exceeded"""
    pass

class InvalidOrderError(BybitAPIError):
    """Invalid order parameters"""
    pass

class PositionError(BybitAPIError):
    """Error related to position operations"""
    pass

class WebSocketError(BybitAPIError):
    """WebSocket connection error"""
    pass

class ConfigurationError(Exception):
    """Configuration error"""
    pass