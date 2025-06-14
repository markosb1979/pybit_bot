#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Historical Data Indicator Validation

Downloads 2000 historical 1-minute candles for BTCUSDT from Bybit mainnet,
calculates indicator values using original TradingView-verified implementations,
and exports to CSV for comparison.
"""

import os
import json
import time
import datetime
import logging
import pandas as pd
import numpy as np
import requests
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import indicators - using original, TradingView-verified implementations
from pybit_bot.indicators.luxfvgtrend import calculate_luxfvgtrend
from pybit_bot.indicators.tva import calculate_tva
from pybit_bot.indicators.cvd import calculate_cvd
from pybit_bot.indicators.vfi import calculate_vfi
from pybit_bot.indicators.atr import calculate_atr


class IndicatorValidator:
    """
    Downloads historical data and calculates indicators for validation.
    """
    
    def __init__(self, config_path: str = "pybit_bot/configs/indicators.json"):
        """
        Initialize the validator.
        
        Args:
            config_path: Path to indicators configuration file
        """
        self.config = self._load_config(config_path)
        self.base_url = "https://api.bybit.com"
        self.output_dir = "validation_data"
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {"indicators": {}}
    
    def download_historical_data(self, symbol: str = "BTCUSDT", 
                                interval: str = "1", limit: int = 2000) -> Optional[pd.DataFrame]:
        """
        Download historical kline data from Bybit with pagination support.
        
        Args:
            symbol: Trading symbol
            interval: Kline interval (1 for 1 minute)
            limit: Total number of candles to download
            
        Returns:
            DataFrame with historical data or None if error
        """
        try:
            endpoint = "/v5/market/kline"
            all_candles = []
            remaining = limit
            max_per_request = 1000  # Bybit's limit per request
            
            # Start with no end timestamp (most recent candles first)
            end_time = None
            
            while remaining > 0:
                # Calculate how many candles to fetch in this request
                fetch_limit = min(remaining, max_per_request)
                
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "interval": interval,
                    "limit": fetch_limit
                }
                
                # Add end timestamp for pagination if we have one
                if end_time:
                    params["end"] = end_time
                
                url = f"{self.base_url}{endpoint}"
                response = requests.get(url, params=params)
                
                if response.status_code != 200:
                    logger.error(f"API request failed: {response.status_code} - {response.text}")
                    return None
                
                data = response.json()
                
                if not data.get('result') or not data['result'].get('list'):
                    logger.error(f"No data returned: {data}")
                    break  # No more data available
                
                # Parse response data
                candles = data['result']['list']
                
                if not candles:
                    break  # No more candles
                
                # Bybit returns newest first, so we need to get the oldest timestamp for the next request
                end_time = int(candles[-1][0])  # Timestamp is the first element in each candle
                
                # Add candles to our collection
                all_candles.extend(candles)
                
                # Update remaining count
                remaining = limit - len(all_candles)
                
                logger.info(f"Downloaded {len(candles)} candles, total: {len(all_candles)}, remaining: {remaining}")
                
                # Break if we got fewer candles than requested (means we reached the limit)
                if len(candles) < fetch_limit:
                    break
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.5)
            
            if not all_candles:
                logger.error("No candles were downloaded")
                return None
            
            # Create DataFrame
            df = pd.DataFrame(all_candles, columns=[
                "timestamp", "open", "high", "low", "close", "volume", "turnover"
            ])
            
            # Convert types
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            # Sort by timestamp (oldest first)
            df = df.sort_values('timestamp')
            
            # Limit to the requested number of candles (take the most recent ones)
            if len(df) > limit:
                df = df.tail(limit)
            
            logger.info(f"Downloaded {len(df)} candles for {symbol}")
            return df
            
        except Exception as e:
            logger.exception(f"Error downloading historical data: {e}")
            return None
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators on the historical data using the original
        TradingView-verified implementations.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added indicator columns
        """
        try:
            # Get indicator parameters from config
            atr_config = self.config.get('indicators', {}).get('atr', {})
            cvd_config = self.config.get('indicators', {}).get('cvd', {})
            tva_config = self.config.get('indicators', {}).get('tva', {})
            vfi_config = self.config.get('indicators', {}).get('vfi', {})
            luxfvg_config = self.config.get('indicators', {}).get('luxfvgtrend', {})
            
            # Extract parameters with defaults
            atr_length = atr_config.get('length', 14)
            cvd_length = cvd_config.get('cumulation_length', 25)
            tva_length = tva_config.get('length', 15)
            vfi_lookback = vfi_config.get('lookback', 50)
            
            # Calculate ATR
            logger.info(f"Calculating ATR with length={atr_length}")
            df['atr'] = calculate_atr(df, length=atr_length)
            
            # Calculate CVD
            logger.info(f"Calculating CVD with length={cvd_length}")
            df['cvd'] = calculate_cvd(df, cumulation_length=cvd_length)
            
            # Calculate TVA
            logger.info(f"Calculating TVA with length={tva_length}")
            tva_results = calculate_tva(df, length=tva_length)
            df['rb'] = tva_results[0]  # Rising Bull
            df['rr'] = tva_results[1]  # Rising Bear
            df['db'] = tva_results[2]  # Declining Bull
            df['dr'] = tva_results[3]  # Declining Bear
            df['tva_upper'] = tva_results[4]  # Upper line
            df['tva_lower'] = tva_results[5]  # Lower line
            
            # Calculate VFI
            logger.info(f"Calculating VFI with lookback={vfi_lookback}")
            df['vfi'] = calculate_vfi(df, lookback=vfi_lookback)
            
            # Calculate LuxFVGtrend
            logger.info("Calculating LuxFVGtrend")
            fvg_results = calculate_luxfvgtrend(df)
            df['fvg_signal'] = fvg_results[0]  # 1 = bullish gap, -1 = bearish gap, 0 = none
            df['fvg_midpoint'] = fvg_results[1]  # price midpoint of the detected gap
            df['fvg_counter'] = fvg_results[2]  # trend counter
            
            # Add a buy/sell signal column for easy validation
            df['signal'] = 0
            
            # Long signal conditions
            long_conditions = (
                (df['cvd'] > 0) &
                (df['rb'] > 0) &
                (df['vfi'] > 0) &
                (df['fvg_signal'] == 1)
            )
            df.loc[long_conditions, 'signal'] = 1
            
            # Short signal conditions
            short_conditions = (
                (df['cvd'] < 0) &
                (df['rr'] < 0) &
                (df['vfi'] < 0) &
                (df['fvg_signal'] == -1)
            )
            df.loc[short_conditions, 'signal'] = -1
            
            logger.info("All indicators calculated successfully")
            return df
            
        except Exception as e:
            logger.exception(f"Error calculating indicators: {e}")
            return df
    
    def export_to_csv(self, df: pd.DataFrame, symbol: str) -> str:
        """
        Export DataFrame with indicators to CSV.
        
        Args:
            df: DataFrame with indicator data
            symbol: Trading symbol
            
        Returns:
            Path to saved CSV file
        """
        try:
            # Format timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{symbol}_indicators_{timestamp}.csv"
            filepath = os.path.join(self.output_dir, filename)
            
            # Save to CSV
            df.to_csv(filepath, index=False, float_format='%.8f')
            logger.info(f"Data exported to {filepath}")
            
            # Save a sample file with just the last 100 rows for easier viewing
            sample_filename = f"{symbol}_indicators_sample_{timestamp}.csv"
            sample_filepath = os.path.join(self.output_dir, sample_filename)
            df.tail(100).to_csv(sample_filepath, index=False, float_format='%.8f')
            logger.info(f"Sample data (last 100 rows) exported to {sample_filepath}")
            
            return filepath
            
        except Exception as e:
            logger.exception(f"Error exporting to CSV: {e}")
            return ""
    
    def run_validation(self, symbol: str = "BTCUSDT"):
        """
        Run the full validation process.
        
        Args:
            symbol: Trading symbol
        """
        try:
            logger.info(f"Starting validation for {symbol} with 2000 historical bars")
            
            # Step 1: Download historical data
            df = self.download_historical_data(symbol=symbol, limit=2000)
            if df is None or len(df) == 0:
                logger.error("Failed to download historical data")
                return
            
            logger.info(f"Successfully downloaded {len(df)} candles, timespan: {df['timestamp'].min()} to {df['timestamp'].max()}")
            
            # Step 2: Calculate indicators
            df_with_indicators = self.calculate_indicators(df)
            
            # Step 3: Export to CSV
            csv_path = self.export_to_csv(df_with_indicators, symbol)
            
            if csv_path:
                logger.info(f"Validation complete. Results saved to {csv_path}")
                logger.info(f"Number of long signals: {len(df_with_indicators[df_with_indicators['signal'] == 1])}")
                logger.info(f"Number of short signals: {len(df_with_indicators[df_with_indicators['signal'] == -1])}")
                
                # Print sample data for quick review
                logger.info("\nSample of the latest 5 rows:")
                print(df_with_indicators.tail(5).to_string())
                
                # Also print a few rows with signals
                signal_rows = df_with_indicators[df_with_indicators['signal'] != 0].tail(3)
                if len(signal_rows) > 0:
                    logger.info("\nSample of the latest signal rows:")
                    print(signal_rows.to_string())
            
        except Exception as e:
            logger.exception(f"Error during validation: {e}")


if __name__ == "__main__":
    validator = IndicatorValidator()
    validator.run_validation("BTCUSDT")