"""
Modular Bybit Trading Bot Library
Designed for USDT Perpetuals with comprehensive testing capabilities
"""

__version__ = "1.0.0"
__author__ = "Trading Bot Team"

# Phase 1 - Available imports
from .core import BybitClient, APICredentials
from .utils import Logger, ConfigManager

# Phase 2 - Will be available later
# from .trading import OrderManager, PositionManager
# from .websocket import WebSocketManager
# from .indicators import Indicators

# Phase 3 - Will be available later  
# from .strategies import StrategyBase

__all__ = [
    'BybitClient',
    'APICredentials', 
    'Logger',
    'ConfigManager'
]