"""
TVA (Trend Volume Analysis) indicator implementation.
Analyzes volume trends to identify rising/falling volume patterns.
"""

import pandas as pd
import numpy as np


def calculate_tva(df: pd.DataFrame, length: int = 15) -> tuple:
    """
    Calculate TVA (Trend Volume Analysis) for a given DataFrame.
    
    Args:
        df: DataFrame containing 'open', 'close', and 'volume' columns
        length: Period for TVA calculation (default: 15)
        
    Returns:
        Tuple of (rising_bull, rising_bear, dropping_bull, dropping_bear, upper_band, lower_band)
    """
    # Validate inputs
    for col in ['open', 'close', 'volume']:
        if col not in df.columns:
            raise ValueError(f"DataFrame must contain '{col}' column")
    
    # Calculate base values
    close = df['close']
    prev_close = close.shift(1)
    volume = df['volume']
    
    # Calculate bullish and bearish volume
    bull_volume = np.where(close > prev_close, volume, 0)
    bear_volume = np.where(close < prev_close, volume, 0)
    
    # Calculate moving averages
    bull_ma = pd.Series(bull_volume).rolling(window=length).mean()
    bear_ma = pd.Series(bear_volume).rolling(window=length).mean()
    
    # Calculate rising and dropping volume
    rising_bull = bull_ma - bull_ma.shift(1)
    rising_bear = bear_ma - bear_ma.shift(1)
    dropping_bull = bull_ma.shift(1) - bull_ma
    dropping_bear = bear_ma.shift(1) - bear_ma
    
    # Calculate upper and lower bands
    upper_band = pd.Series(np.where(rising_bull > rising_bear, 0.5, 0), index=df.index)
    lower_band = pd.Series(np.where(rising_bear > rising_bull, -0.5, 0), index=df.index)
    
    return rising_bull, rising_bear, dropping_bull, dropping_bear, upper_band, lower_band