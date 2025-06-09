"""
PyBit Bot - A modular trading bot for Bybit USDT Perpetual contracts
"""

__version__ = "0.1.0"

# Re-export key classes for easier imports
from .core.client import BybitClient, APICredentials
from .utils.logger import Logger
from .utils.config_loader import ConfigLoader
from .utils.credentials import load_credentials
from .exceptions.errors import (
    BybitAPIError,
    AuthenticationError,
    RateLimitError,
    InvalidOrderError,
    ConfigurationError
)