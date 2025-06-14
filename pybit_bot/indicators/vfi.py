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
    close = df['close']
    open_ = df['open']
    volume = df['volume']

    # Buy volume: volume if close > open or close > previous close
    buy = np.where((close > open_) | (close > close.shift(1)), volume, 0.0)
    # Sell volume: volume if close < open or close < previous close
    sell = np.where((close < open_) | (close < close.shift(1)), volume, 0.0)

    # Cumulative sums over the lookback window
    cum_buy = pd.Series(buy, index=df.index).rolling(window=lookback, min_periods=1).sum()
    cum_sell = pd.Series(sell, index=df.index).rolling(window=lookback, min_periods=1).sum()

    # OFI calculation (avoid division by zero)
    denom = cum_buy + cum_sell
    vfi = np.where(denom == 0, np.nan, (cum_buy - cum_sell) / denom)
    return pd.Series(vfi, index=df.index)