"""
CVD (Cumulative Volume Delta) indicator implementation.
Measures buying/selling pressure using volume and price movement.
"""

import pandas as pd
import numpy as np


def calculate_cvd(df: pd.DataFrame, cumulation_length: int = 25) -> pd.Series:
    """
    Calculate CVD (Cumulative Volume Delta) for a given DataFrame.
    
    Args:
        df: DataFrame containing 'open', 'close', and 'volume' columns
        cumulation_length: Period for cumulative summation (default: 25)
        
    Returns:
        pandas.Series with CVD values
    """
    # Validate inputs
    for col in ['open', 'close', 'volume']:
        if col not in df.columns:
            raise ValueError(f"DataFrame must contain '{col}' column")
    
    # Calculate volume delta
    volume_delta = np.where(
        df['close'] > df['open'],
        df['volume'],  # Bullish candle - positive volume
        np.where(
            df['close'] < df['open'],
            -df['volume'],  # Bearish candle - negative volume
            0  # Doji candle - neutral volume
        )
    )
    
    # Cumulative sum with rolling window
    cvd = pd.Series(volume_delta, index=df.index).rolling(window=cumulation_length).sum()
    
    return cvd