"""
[WORKING SOURCE CODE - DO NOT EDIT]

Cumulative Volume Delta (CVD) indicator for Bybit trading bot.
Matches the TradingView/Pine Script CVD logic as described.

Inputs:
    df: pandas.DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        Sorted by time ascending.
    cumulation_length: int (default: 14) - EMA smoothing window.

Output:
    pandas.Series of CVD (cumulative_volume_delta), index-aligned with df.

EMA implementation:
    Uses pandas .ewm(span=length, adjust=False).mean() for smoothing (matches Pine Script's EMA).

Usage:
    from indicators.cvd import calculate_cvd
    cvd_series = calculate_cvd(df, cumulation_length=14)
    # Optionally: df['cvd'] = cvd_series
"""

import pandas as pd
import numpy as np

def calculate_cvd(df: pd.DataFrame, cumulation_length: int = 14) -> pd.Series:
    """
    Calculate the Cumulative Volume Delta (CVD) for a DataFrame of OHLCV data.

    :param df: pandas.DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
    :param cumulation_length: window for EMA smoothing (default: 14)
    :return: pandas.Series of CVD values
    """
    open_ = df['open'].values
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    volume = df['volume'].values

    # Calculate candle spread
    spread = high - low
    
    # Handle zero spread safely (avoid division by zero)
    spread_safe = np.copy(spread)
    spread_safe[spread_safe == 0] = np.nan
    
    # Calculate wicks and body
    upper_wick = np.where(close > open_, high - close, high - open_)
    lower_wick = np.where(close > open_, open_ - low, close - low)
    body_length = spread - (upper_wick + lower_wick)
    
    # Calculate percentage components
    percent_upper_wick = upper_wick / spread_safe
    percent_lower_wick = lower_wick / spread_safe
    percent_body_length = body_length / spread_safe
    
    # Replace NaN with 0 (for zero spread candles)
    percent_upper_wick = np.nan_to_num(percent_upper_wick)
    percent_lower_wick = np.nan_to_num(percent_lower_wick)
    percent_body_length = np.nan_to_num(percent_body_length)
    
    # Calculate buying and selling volume exactly as in TradingView
    buying_volume = np.zeros_like(volume)
    selling_volume = np.zeros_like(volume)
    
    for i in range(len(volume)):
        if close[i] > open_[i]:  # Bullish candle
            # Buying volume = body + half of wicks
            buying_volume[i] = (percent_body_length[i] + (percent_upper_wick[i] + percent_lower_wick[i])/2) * volume[i]
            # Selling volume = half of wicks
            selling_volume[i] = ((percent_upper_wick[i] + percent_lower_wick[i])/2) * volume[i]
        elif close[i] < open_[i]:  # Bearish candle
            # Buying volume = half of wicks
            buying_volume[i] = ((percent_upper_wick[i] + percent_lower_wick[i])/2) * volume[i]
            # Selling volume = body + half of wicks
            selling_volume[i] = (percent_body_length[i] + (percent_upper_wick[i] + percent_lower_wick[i])/2) * volume[i]
        else:  # Doji (open = close)
            # Equal split between buying and selling
            buying_volume[i] = volume[i] / 2
            selling_volume[i] = volume[i] / 2
    
    # Convert to pandas Series for EMA calculation
    buying_volume_series = pd.Series(buying_volume, index=df.index)
    selling_volume_series = pd.Series(selling_volume, index=df.index)
    
    # Apply EMA smoothing to match TradingView's implementation
    # TradingView uses alpha = 2/(length+1) for EMA
    alpha = 2 / (cumulation_length + 1)
    
    # Manual EMA calculation to match TradingView exactly
    cumulative_buying_volume = buying_volume_series.copy()
    cumulative_selling_volume = selling_volume_series.copy()
    
    # First value is the raw value (TradingView initialization)
    for i in range(1, len(df)):
        cumulative_buying_volume.iloc[i] = alpha * buying_volume_series.iloc[i] + (1 - alpha) * cumulative_buying_volume.iloc[i-1]
        cumulative_selling_volume.iloc[i] = alpha * selling_volume_series.iloc[i] + (1 - alpha) * cumulative_selling_volume.iloc[i-1]
    
    # Calculate final CVD
    cvd = cumulative_buying_volume - cumulative_selling_volume
    
    return cvd