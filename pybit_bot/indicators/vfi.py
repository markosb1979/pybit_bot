"""
[WORKING SOURCE CODE - DO NOT EDIT]

Volume Flow Imbalance (VFI) indicator for Bybit trading bot.
Matches TradingView/Pine Script VFI logic for 1m bars (no lower timeframe aggregation).

Inputs:
    df: pandas.DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        Must be sorted by time ascending.
    lookback: int (default: 50) - window size for imbalance calculation.

Output:
    pandas.Series of VFI (Order Flow Imbalance) values, index-aligned with df.

Usage:
    from indicators.vfi import calculate_vfi
    vfi_series = calculate_vfi(df, lookback=50)
    # Optionally: df['vfi'] = vfi_series
"""

import pandas as pd
import numpy as np

def calculate_vfi(df: pd.DataFrame, lookback: int = 50) -> pd.Series:
    """
    Calculate the Volume Flow Imbalance (VFI) for a DataFrame of OHLCV data.

    :param df: pandas.DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
    :param lookback: window for cumulative volume sums (default: 50)
    :return: pandas.Series of VFI values
    """
    # Extract required data
    close = df['close'].values
    open_ = df['open'].values
    volume = df['volume'].values
    
    # Create arrays for buy and sell volume
    buy_volume = np.zeros_like(volume)
    sell_volume = np.zeros_like(volume)
    
    # Process each candle to distribute volume properly
    for i in range(len(close)):
        # Compare with previous close (first candle has no previous)
        prev_close = close[i-1] if i > 0 else open_[i]
        
        # Determine buy and sell volume with proper distribution
        # Primary signal: close vs open (determines candle color)
        if close[i] > open_[i]:  # Bullish candle
            buy_volume[i] = volume[i] * 0.75  # 75% buy
            sell_volume[i] = volume[i] * 0.25  # 25% sell
        elif close[i] < open_[i]:  # Bearish candle
            buy_volume[i] = volume[i] * 0.25  # 25% buy
            sell_volume[i] = volume[i] * 0.75  # 75% sell
        else:  # Doji
            # Secondary signal: close vs previous close
            if close[i] > prev_close:
                buy_volume[i] = volume[i] * 0.6  # 60% buy
                sell_volume[i] = volume[i] * 0.4  # 40% sell
            elif close[i] < prev_close:
                buy_volume[i] = volume[i] * 0.4  # 40% buy
                sell_volume[i] = volume[i] * 0.6  # 60% sell
            else:
                # No change - split equally
                buy_volume[i] = volume[i] * 0.5
                sell_volume[i] = volume[i] * 0.5
    
    # Convert to pandas Series
    buy_series = pd.Series(buy_volume, index=df.index)
    sell_series = pd.Series(sell_volume, index=df.index)
    
    # Calculate cumulative sums using TradingView-like window
    cum_buy = buy_series.rolling(window=lookback, min_periods=1).sum()
    cum_sell = sell_series.rolling(window=lookback, min_periods=1).sum()
    
    # Calculate VFI
    vfi = (cum_buy - cum_sell) / (cum_buy + cum_sell)
    
    # Handle division by zero and NaN values
    vfi = vfi.fillna(0)
    
    return vfi