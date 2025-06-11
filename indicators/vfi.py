"""
VFI (Volume Flow Indicator) implementation.
Measures money flow volume with price sensitivity.
"""

import pandas as pd
import numpy as np


def calculate_vfi(df: pd.DataFrame, lookback: int = 50) -> pd.Series:
    """
    Calculate VFI (Volume Flow Indicator) for a given DataFrame.
    
    Args:
        df: DataFrame containing 'high', 'low', 'close', and 'volume' columns
        lookback: Period for VFI calculation (default: 50)
        
    Returns:
        pandas.Series with VFI values
    """
    # Validate inputs
    for col in ['high', 'low', 'close', 'volume']:
        if col not in df.columns:
            raise ValueError(f"DataFrame must contain '{col}' column")
    
    # Calculate typical price
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    
    # Calculate price change
    price_change = typical_price.diff()
    
    # Calculate direction
    direction = np.where(
        price_change > 0,
        1,  # Positive change
        np.where(
            price_change < 0,
            -1,  # Negative change
            0  # No change
        )
    )
    
    # Calculate volume flow
    volume_flow = direction * df['volume']
    
    # Calculate VFI
    vfi = pd.Series(volume_flow, index=df.index).rolling(window=lookback).sum()
    
    # Normalize
    vfi = vfi / df['volume'].rolling(window=lookback).sum()
    
    return vfi