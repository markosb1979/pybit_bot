"""
Pytest fixtures for integration tests.
Provides mock data, API responses, and component configurations.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pybit_bot.strategies.base_strategy import SignalType, OrderType


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return {
        "trading": {
            "symbols": ["BTCUSDT"],
            "timeframes": ["1m", "5m"]
        },
        "strategies": {
            "strategy_a": {
                "enabled": True
            },
            "strategy_b": {
                "enabled": True
            }
        },
        "indicators": {
            "atr": {
                "enabled": True
            }
        },
        "risk_management": {
            "max_positions_per_symbol": 2
        },
        "tpsl_manager": {
            "check_interval_ms": 100,
            "default_stop_type": "TRAILING"
        }
    }


@pytest.fixture
def mock_market_data():
    """Create mock market data for testing."""
    # Create date range
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(minutes=i) for i in range(100)]
    
    # Create price data
    np.random.seed(42)  # For reproducibility
    close = 20000 + np.cumsum(np.random.normal(0, 100, 100))
    high = close + np.random.uniform(50, 200, 100)
    low = close - np.random.uniform(50, 200, 100)
    open_price = close - np.random.normal(0, 100, 100)
    volume = np.random.uniform(1, 10, 100) * 100
    
    # Create DataFrame
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    # Add indicators
    df['atr'] = np.ones(100) * 100
    df['fast_sma'] = pd.Series(np.linspace(19900, 20100, 100), index=df.index)
    df['slow_sma'] = pd.Series(np.linspace(20100, 19900, 100), index=df.index)
    
    # Create SMA crossover at the end
    df.loc[df.index[-2], 'fast_sma'] = 19950
    df.loc[df.index[-2], 'slow_sma'] = 20000
    df.loc[df.index[-1], 'fast_sma'] = 20050
    df.loc[df.index[-1], 'slow_sma'] = 20000
    
    # Add other indicators
    df['cvd'] = np.ones(100) * 1.0
    df['vfi'] = np.ones(100) * 0.5
    df['fvg_signal'] = np.ones(100)
    df['fvg_midpoint'] = df['close'] * 0.98
    
    return {'1m': df}


@pytest.fixture
def mock_order_executor():
    """Create a mock order executor for testing."""
    mock = MagicMock()
    mock.execute_order = MagicMock(return_value={"order_id": "12345"})
    return mock


@pytest.fixture
def mock_bybit_client():
    """Create a mock Bybit client for testing."""
    mock = MagicMock()
    
    # Mock market data methods
    mock.get_kline = MagicMock(return_value={
        "result": [
            {
                "symbol": "BTCUSDT",
                "interval": "1",
                "open_time": 1609459200,
                "open": "20000",
                "high": "20100",
                "low": "19900",
                "close": "20050",
                "volume": "100",
                "turnover": "2000000"
            }
        ]
    })
    
    # Mock order methods
    mock.place_active_order = MagicMock(return_value={
        "result": {
            "order_id": "12345",
            "symbol": "BTCUSDT",
            "side": "Buy",
            "order_type": "Limit",
            "price": "20000",
            "qty": "0.01",
            "time_in_force": "GTC",
            "order_status": "New",
            "reduce_only": False,
            "close_on_trigger": False
        }
    })
    
    # Mock position methods
    mock.my_position = MagicMock(return_value={
        "result": [
            {
                "symbol": "BTCUSDT",
                "side": "Buy",
                "size": "0.01",
                "entry_price": "20000",
                "leverage": "10",
                "unrealised_pnl": "5",
                "position_value": "200",
                "liq_price": "18000"
            }
        ]
    })
    
    return mock