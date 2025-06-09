"""
Custom exceptions for the trading bot
"""

class TradingBotError(Exception):
    """Base exception for trading bot errors"""
    pass

class BybitAPIError(TradingBotError):
    """Bybit API related errors"""
    pass

class AuthenticationError(BybitAPIError):
    """Authentication failures"""
    pass

class RateLimitError(BybitAPIError):
    """Rate limit exceeded"""
    pass

class InvalidOrderError(TradingBotError):
    """Invalid order parameters"""
    pass

class PositionManagerError(TradingBotError):
    """Position management errors"""
    pass

class StrategyError(TradingBotError):
    """Strategy execution errors"""
    pass

class WebSocketError(TradingBotError):
    """WebSocket connection errors"""
    pass

class ConfigurationError(TradingBotError):
    """Configuration errors"""
    pass