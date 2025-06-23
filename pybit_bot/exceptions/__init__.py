"""
Custom exceptions for the pybit_bot module

This module defines custom exceptions that are used throughout the codebase
to provide clear error handling and meaningful error messages.
"""

class BybitAPIError(Exception):
    """Base exception for Bybit API errors"""
    pass

class AuthenticationError(BybitAPIError):
    """Exception raised for authentication errors"""
    pass

class RateLimitError(BybitAPIError):
    """Exception raised when rate limit is exceeded"""
    pass

class ConnectionError(BybitAPIError):
    """Exception raised for connection errors"""
    pass

class InvalidOrderError(BybitAPIError):
    """Exception raised for invalid order parameters"""
    pass

class PositionError(BybitAPIError):
    """Exception raised for position-related errors"""
    pass

class ConfigurationError(Exception):
    """Exception raised for configuration errors"""
    pass

class DataError(Exception):
    """Exception raised for data-related errors"""
    pass

class StrategyError(Exception):
    """Exception raised for strategy-related errors"""
    pass