"""
Utility helper functions
"""

import time
from datetime import datetime
from typing import Any, Dict, Optional


def generate_timestamp() -> int:
    """Generate timestamp in milliseconds"""
    return int(time.time() * 1000)


def format_timestamp(timestamp: int) -> str:
    """Format timestamp to readable string"""
    return datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def format_price(price: float, decimals: int = 8) -> str:
    """Format price with specified decimal places"""
    return f"{price:.{decimals}f}".rstrip('0').rstrip('.')


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Calculate percentage change between two values"""
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100


def truncate_string(text: str, max_length: int = 50) -> str:
    """Truncate string to max length with ellipsis"""
    return text[:max_length] + "..." if len(text) > max_length else text