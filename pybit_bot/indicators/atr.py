"""
ATR (Average True Range) indicator implementation.
Measures market volatility by calculating the average range between high and low prices.
"""

import pandas as pd
import numpy as np


def calculate_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """
    Calculate ATR (Average True Range) for a given DataFrame.
    
    Args:
        df: DataFrame containing 'high', 'low', and 'close' columns
        length: ATR period length (default: 14)
        
    Returns:
        pandas.Series with ATR values
    """
    # Validate inputs
    for col in ['high', 'low', 'close']:
        if col not in df.columns:
            raise ValueError(f"DataFrame must contain '{col}' column")
    
    # Calculate True Range
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate ATR
    atr = tr.rolling(window=length).mean()
    
    return atr