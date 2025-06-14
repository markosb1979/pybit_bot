"""
[WORKING SOURCE CODE - DO NOT EDIT]

LuxFVGtrend (Fair Value Gap Trend, "bot ready") indicator for Bybit trading bot.
Implements the LuxAlgo FVG logic for higher timeframe detection.

Inputs:
    df: pandas.DataFrame with columns ['open', 'high', 'low', 'close']
        Sorted by time ascending.
    step_size: float (default: 1), hardcoded.

Outputs:
    Tuple of pandas.Series, index-aligned:
        - fvg_signal: 1 (bull FVG), -1 (bear FVG), 0 (none)
        - fvg_midpoint: float (midpoint value or 0.0 if no FVG)
        - fvg_counter: float (trend counter, as Pine Script)

Usage:
    from indicators.luxfvgtrend import calculate_luxfvgtrend
    fvg_signal, fvg_midpoint, fvg_counter = calculate_luxfvgtrend(df)
    # Optionally: df['fvg_signal'] = fvg_signal, etc.
"""

import pandas as pd
import numpy as np

def calculate_luxfvgtrend(df: pd.DataFrame) -> tuple:
    """
    Calculate FVG trend signals, midpoints, and trend counter.

    :param df: pandas.DataFrame with ['open', 'high', 'low', 'close']
    :return: (fvg_signal, fvg_midpoint, fvg_counter) as pandas.Series, step_size=1 (hardcoded)
    """
    step_size = 1.0  # hardcoded as per requirements

    high = df['high']
    low = df['low']
    close = df['close']

    # Shifted values for FVG logic
    high_1 = high.shift(1)
    high_2 = high.shift(2)
    low_1 = low.shift(1)
    low_2 = low.shift(2)
    close_1 = close.shift(1)

    bull_og = low > high_1
    bull_og_1 = bull_og.shift(1, fill_value=False)
    bear_og = high < low_1
    bear_og_1 = bear_og.shift(1, fill_value=False)

    bull_fvg = (low > high_2) & (close_1 > high_2) & (~bull_og) & (~bull_og_1)
    bear_fvg = (high < low_2) & (close_1 < low_2) & (~bear_og) & (~bear_og_1)

    bull_mid = (low + high_2) / 2
    bear_mid = (low_2 + high) / 2
    fvg_midpoint = np.where(bull_fvg, bull_mid, np.where(bear_fvg, bear_mid, 0.0))
    fvg_signal = np.where(bull_fvg, 1, np.where(bear_fvg, -1, 0))

    # Trend counter logic
    fvg_counter = np.zeros(len(df), dtype=float)
    last = 0.0
    for i in range(len(df)):
        if bull_fvg.iloc[i]:
            last = step_size if last < 0 else last + step_size
        elif bear_fvg.iloc[i]:
            last = -step_size if last > 0 else last - step_size
        fvg_counter[i] = last

    # Align with Pine Script offset=-1 (plot one bar earlier)
    fvg_signal = pd.Series(fvg_signal, index=df.index).shift(-1)
    fvg_midpoint = pd.Series(fvg_midpoint, index=df.index).shift(-1)
    fvg_counter = pd.Series(fvg_counter, index=df.index).shift(-1)

    return fvg_signal, fvg_midpoint, fvg_counter