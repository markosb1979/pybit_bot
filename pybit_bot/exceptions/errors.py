"""
Error classes for PyBit Bot
"""

class APIError(Exception):
    """Exception raised for errors in API responses."""
    def __init__(self, message, response=None):
        self.message = message
        self.response = response
        super().__init__(self.message)

class BybitAPIError(Exception):
    """Exception raised for errors in Bybit API responses."""
    def __init__(self, message, response=None, status_code=None):
        self.message = message
        self.response = response
        self.status_code = status_code
        super().__init__(self.message)

class ConfigError(Exception):
    """Exception raised for errors in configuration."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class ConfigurationError(Exception):
    """Exception raised for errors in configuration."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class DataError(Exception):
    """Exception raised for errors in data processing."""
    def __init__(self, message, data=None):
        self.message = message
        self.data = data
        super().__init__(self.message)

class OrderError(Exception):
    """Exception raised for errors in order operations."""
    def __init__(self, message, order_id=None, symbol=None):
        self.message = message
        self.order_id = order_id
        self.symbol = symbol
        super().__init__(self.message)

# Add this missing exception class
class InvalidOrderError(Exception):
    """Exception raised for invalid order parameters."""
    def __init__(self, message, order_details=None):
        self.message = message
        self.order_details = order_details
        super().__init__(self.message)

class PositionError(Exception):
    """Exception raised for errors in position operations."""
    def __init__(self, message, symbol=None):
        self.message = message
        self.symbol = symbol
        super().__init__(self.message)

class WebSocketError(Exception):
    """Exception raised for errors in WebSocket connections."""
    def __init__(self, message, connection=None):
        self.message = message
        self.connection = connection
        super().__init__(self.message)

class StrategyError(Exception):
    """Exception raised for errors in strategy execution."""
    def __init__(self, message, strategy=None):
        self.message = message
        self.strategy = strategy
        super().__init__(self.message)

class ConnectionError(Exception):
    """Exception raised for connection issues."""
    def __init__(self, message, details=None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class AuthenticationError(Exception):
    """Exception raised for authentication failures."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class RateLimitError(Exception):
    """Exception raised for rate limit issues."""
    def __init__(self, message, reset_time=None):
        self.message = message
        self.reset_time = reset_time
        super().__init__(self.message)

class ValidationError(Exception):
    """Exception raised for validation failures."""
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(self.message)