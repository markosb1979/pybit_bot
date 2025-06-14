"""
TVA_stable01 – Trend Volume Acceleration indicator (modular, values only version).

Inputs:
    df: pandas.DataFrame with columns ['close', 'volume']
        Sorted by time ascending.
    length: int (default: 15, adjustable)
        All other parameters hardcoded: smo=3, mult=5.0

Outputs:
    Tuple of pandas.Series, index-aligned, values only (0 if nan):
        - rb: Rising Bull accumulator
        - rr: Rising Bear accumulator
        - db: Declining Bull accumulator (negative)
        - dr: Declining Bear accumulator (negative)
        - upper: Upper level (gray line)
        - lower: Lower level (gray line)

Usage:
    from indicators.tva import calculate_tva
    rb, rr, db, dr, upper, lower = calculate_tva(df, length=15)
"""

import pandas as pd
import numpy as np

def calculate_tva(df: pd.DataFrame, length: int = 15):
    # Hardcoded parameters
    smo = 3
    mult = 5.0

    # Ensure we have enough data
    if len(df) < length + smo:
        # Return empty series if not enough data
        empty = pd.Series(0, index=df.index)
        return empty, empty, empty, empty, empty, empty

    # Get required data
    close = df['close'].values
    volume = df['volume'].values

    # Calculate oscillator (WMA - SMA)
    wma = np.zeros_like(close)
    sma = np.zeros_like(close)
    
    # Calculate SMA (Simple Moving Average)
    for i in range(length-1, len(close)):
        sma[i] = np.mean(close[i-length+1:i+1])
    
    # Calculate WMA (Weighted Moving Average)
    weights = np.arange(1, length + 1)
    weight_sum = np.sum(weights)
    
    for i in range(length-1, len(close)):
        segment = close[i-length+1:i+1]
        wma[i] = np.sum(segment * weights) / weight_sum
    
    # Calculate oscillator
    oscillator = wma - sma
    
    # Calculate volume changes
    vol_diff = np.zeros_like(volume)
    vol_diff[1:] = volume[1:] - volume[:-1]
    
    # Up/down volume masks
    up_vol_mask = np.zeros_like(volume)
    down_vol_mask = np.zeros_like(volume)
    
    up_vol_mask[vol_diff > 0] = volume[vol_diff > 0]
    down_vol_mask[vol_diff < 0] = volume[vol_diff < 0]
    
    # Calculate smoothed volumes
    rising_vol = np.zeros_like(volume)
    declining_vol = np.zeros_like(volume)
    
    for i in range(smo-1, len(volume)):
        rising_vol[i] = np.mean(up_vol_mask[i-smo+1:i+1])
        declining_vol[i] = np.mean(down_vol_mask[i-smo+1:i+1])
    
    # Initialize accumulators
    rb = np.zeros_like(close)
    rr = np.zeros_like(close)
    db = np.zeros_like(close)
    dr = np.zeros_like(close)
    
    # Previous oscillator sign for tracking changes
    prev_osc_sign = 0
    
    # Calculate accumulators with proper reset logic
    for i in range(length + smo):
        # Skip the initial period with insufficient data
        rb[i] = 0
        rr[i] = 0
        db[i] = 0
        dr[i] = 0
    
    for i in range(length + smo, len(close)):
        osc_val = oscillator[i]
        curr_sign = 1 if osc_val > 0 else -1 if osc_val < 0 else 0
        
        # Process Rising Bull (rb)
        if osc_val > 0:
            # Only reset on sign change
            if prev_osc_sign < 0:
                rb[i] = rising_vol[i]
            else:
                rb[i] = rb[i-1] + rising_vol[i]
        else:
            rb[i] = 0
        
        # Process Rising Bear (rr)
        if osc_val < 0:
            # Only reset on sign change
            if prev_osc_sign > 0:
                rr[i] = rising_vol[i]
            else:
                rr[i] = rr[i-1] + rising_vol[i]
        else:
            rr[i] = 0
        
        # Process Declining Bull (db) - negative values
        if osc_val > 0:
            # Only reset on sign change
            if prev_osc_sign < 0:
                db[i] = -declining_vol[i]
            else:
                db[i] = db[i-1] - declining_vol[i]
        else:
            db[i] = 0
        
        # Process Declining Bear (dr) - negative values
        if osc_val < 0:
            # Only reset on sign change
            if prev_osc_sign > 0:
                dr[i] = -declining_vol[i]
            else:
                dr[i] = dr[i-1] - declining_vol[i]
        else:
            dr[i] = 0
        
        # Update previous sign if current sign is non-zero
        if curr_sign != 0:
            prev_osc_sign = curr_sign
    
    # Calculate upper and lower levels - using proper averaging
    wave_period = min(20, len(close) // 4)  # Adaptive wave period
    
    upper = np.zeros_like(close)
    lower = np.zeros_like(close)
    
    for i in range(length + smo + wave_period, len(close)):
        # Use appropriate window for waves
        rb_rr_sum = rb[i-wave_period:i] + rr[i-wave_period:i]
        db_dr_sum = db[i-wave_period:i] + dr[i-wave_period:i]
        
        upper[i] = np.mean(rb_rr_sum) * mult
        lower[i] = np.mean(db_dr_sum) * mult
    
    # Convert to pandas Series
    idx = df.index
    rb_series = pd.Series(rb, index=idx)
    rr_series = pd.Series(rr, index=idx)
    db_series = pd.Series(db, index=idx)
    dr_series = pd.Series(dr, index=idx)
    upper_series = pd.Series(upper, index=idx)
    lower_series = pd.Series(lower, index=idx)
    
    # Return tuple of series
    return (rb_series, rr_series, db_series, dr_series, upper_series, lower_series)