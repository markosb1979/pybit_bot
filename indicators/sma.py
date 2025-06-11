"""
Simple Moving Average (SMA) indicator for Bybit trading bot.
Calculates simple arithmetic mean of price over a specified period.

Inputs:
    df: pandas.DataFrame with column 'close' (or other specified column)
    length: SMA window size (default: 20)
    source_column: Column to use for calculation (default: 'close')

Output:
    pandas.Series of SMA values, index aligned with input df

Usage:
    from indicators.sma import calculate_sma
    sma_series = calculate_sma(df, length=20, source_column='close')
    # Optionally: df['sma'] = sma_series
"""

import pandas as pd


def calculate_sma(df: pd.DataFrame, length: int = 20, source_column: str = 'close') -> pd.Series:
    """
    Calculate Simple Moving Average for a DataFrame.

    :param df: pandas.DataFrame with required source_column
    :param length: SMA window size (default: 20)
    :param source_column: Column to use for calculation (default: 'close')
    :return: pandas.Series of SMA values
    """
    if source_column not in df.columns:
        raise ValueError(f"Source column '{source_column}' not found in DataFrame")
    
    # Calculate SMA
    sma = df[source_column].rolling(window=length, min_periods=1).mean()
    return sma