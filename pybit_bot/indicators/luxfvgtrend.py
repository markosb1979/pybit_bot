"""
LuxFVGtrend (Fair Value Gap Trend) indicator implementation.
Identifies fair value gaps in price action for trend confirmation.
"""

import pandas as pd
import numpy as np


def calculate_luxfvgtrend(df: pd.DataFrame, step_size: float = 1.0) -> tuple:
    """
    Calculate LuxFVGtrend (Fair Value Gap Trend) for a given DataFrame.
    
    Args:
        df: DataFrame containing 'high', 'low', 'close' columns
        step_size: Step size for gap detection (default: 1.0)
        
    Returns:
        Tuple of (signal, midpoint, counter)
    """
    # Validate inputs
    for col in ['high', 'low', 'close']:
        if col not in df.columns:
            raise ValueError(f"DataFrame must contain '{col}' column")
    
    # Initialize output arrays
    length = len(df)
    fvg_signal = np.zeros(length)
    fvg_midpoint = np.zeros(length)
    fvg_counter = np.zeros(length)
    
    # Look for FVG patterns (at least 3 bars needed)
    for i in range(2, length):
        # Check for bullish FVG (low[i] > high[i-2])
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            fvg_signal[i] = 1
            fvg_midpoint[i] = (df['low'].iloc[i] + df['high'].iloc[i-2]) / 2
            fvg_counter[i] = 1
        
        # Check for bearish FVG (high[i] < low[i-2])
        elif df['high'].iloc[i] < df['low'].iloc[i-2]:
            fvg_signal[i] = -1
            fvg_midpoint[i] = (df['high'].iloc[i] + df['low'].iloc[i-2]) / 2
            fvg_counter[i] = -1
        
        # Continue previous trend if no new FVG
        elif i > 0:
            if fvg_signal[i-1] != 0:
                fvg_signal[i] = fvg_signal[i-1]
                fvg_midpoint[i] = fvg_midpoint[i-1]
                
                # Increment counter if continuing trend
                if fvg_signal[i] > 0:
                    fvg_counter[i] = fvg_counter[i-1] + 1
                else:
                    fvg_counter[i] = fvg_counter[i-1] - 1
    
    return pd.Series(fvg_signal, index=df.index), pd.Series(fvg_midpoint, index=df.index), pd.Series(fvg_counter, index=df.index)