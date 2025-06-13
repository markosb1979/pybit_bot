"""
Historical data loader for backtesting.
Supports loading data from CSV files and APIs.
"""

import pandas as pd
import numpy as np
import os
import json
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta


class DataLoader:
    """
    Loads and prepares historical data for backtesting.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the data loader.
        
        Args:
            config_path: Path to configuration file (optional)
        """
        self.logger = logging.getLogger(__name__)
        self.config = {}
        
        if config_path:
            self._load_config(config_path)
    
    def _load_config(self, config_path: str) -> None:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
        """
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
                
            self.logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")
            raise
    
    def load_from_csv(self, filepath: str, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Load data from a CSV file.
        
        Args:
            filepath: Path to the CSV file
            symbol: Trading symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe of the data (e.g., '1m', '5m')
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            df = pd.read_csv(filepath)
            
            # Try to convert timestamp column to datetime index
            timestamp_cols = ['timestamp', 'time', 'date', 'datetime', 'open_time']
            
            for col in timestamp_cols:
                if col in df.columns:
                    try:
                        # Check if timestamp is in milliseconds
                        if df[col].iloc[0] > 1e12:
                            df['datetime'] = pd.to_datetime(df[col], unit='ms')
                        else:
                            df['datetime'] = pd.to_datetime(df[col], unit='s')
                            
                        df.set_index('datetime', inplace=True)
                        break
                    except:
                        continue
            
            # If no timestamp column was found or converted
            if not isinstance(df.index, pd.DatetimeIndex):
                self.logger.warning(f"No valid timestamp column found in {filepath}")
                df.index.name = 'datetime'
            
            # Ensure required columns exist
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                self.logger.error(f"Missing required columns in {filepath}: {missing_cols}")
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Add metadata
            df.attrs['symbol'] = symbol
            df.attrs['timeframe'] = timeframe
            
            self.logger.info(f"Loaded {len(df)} rows from {filepath}")
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to load data from {filepath}: {str(e)}")
            raise
    
    def load_from_api(self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        Load data from an API.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe of the data (e.g., '1m', '5m')
            start_time: Start time for data
            end_time: End time for data
            
        Returns:
            DataFrame with OHLCV data
        """
        # This is a placeholder. In a real implementation, you would:
        # 1. Connect to the appropriate API (e.g., Bybit historical data API)
        # 2. Fetch data in chunks (APIs often have limits on how much data you can get at once)
        # 3. Combine the chunks into a single DataFrame
        # 4. Process and clean the data
        
        self.logger.warning("API data loading not yet implemented")
        
        # Create empty DataFrame with the right structure
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        df.attrs['symbol'] = symbol
        df.attrs['timeframe'] = timeframe
        
        return df
    
    def resample_timeframe(self, df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """
        Resample data to a different timeframe.
        
        Args:
            df: Source DataFrame with OHLCV data
            target_timeframe: Target timeframe (e.g., '5m', '1h')
            
        Returns:
            Resampled DataFrame
        """
        try:
            # Parse the target timeframe
            if target_timeframe.endswith('m'):
                freq = f"{target_timeframe[:-1]}T"
            elif target_timeframe.endswith('h'):
                freq = f"{target_timeframe[:-1]}H"
            elif target_timeframe.endswith('d'):
                freq = f"{target_timeframe[:-1]}D"
            else:
                raise ValueError(f"Unsupported timeframe format: {target_timeframe}")
            
            # Resample OHLCV data
            resampled = df.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            # Copy attributes
            resampled.attrs = df.attrs.copy()
            resampled.attrs['timeframe'] = target_timeframe
            
            return resampled
            
        except Exception as e:
            self.logger.error(f"Failed to resample data: {str(e)}")
            raise
    
    def prepare_data_for_backtest(self, 
                                 data_source: str, 
                                 symbol: str, 
                                 timeframes: List[str],
                                 start_time: Optional[datetime] = None,
                                 end_time: Optional[datetime] = None) -> Dict[str, pd.DataFrame]:
        """
        Prepare data for backtesting.
        
        Args:
            data_source: Path to CSV file or 'api'
            symbol: Trading symbol (e.g., 'BTCUSDT')
            timeframes: List of timeframes to prepare
            start_time: Start time for data (optional)
            end_time: End time for data (optional)
            
        Returns:
            Dictionary of DataFrames for each timeframe
        """
        result = {}
        
        try:
            # Load base data
            base_timeframe = min(timeframes, key=lambda x: self._timeframe_to_minutes(x))
            
            if data_source.lower() == 'api':
                # Load from API
                if not start_time or not end_time:
                    raise ValueError("start_time and end_time are required for API data loading")
                    
                base_df = self.load_from_api(symbol, base_timeframe, start_time, end_time)
            else:
                # Load from CSV
                base_df = self.load_from_csv(data_source, symbol, base_timeframe)
                
                # Apply time filters if provided
                if start_time:
                    base_df = base_df[base_df.index >= start_time]
                if end_time:
                    base_df = base_df[base_df.index <= end_time]
            
            # Store base timeframe
            result[base_timeframe] = base_df
            
            # Resample to other timeframes
            for tf in timeframes:
                if tf != base_timeframe:
                    result[tf] = self.resample_timeframe(base_df, tf)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to prepare data for backtesting: {str(e)}")
            raise
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """
        Convert timeframe string to minutes.
        
        Args:
            timeframe: Timeframe string (e.g., '1m', '5m', '1h')
            
        Returns:
            Number of minutes
        """
        try:
            if timeframe.endswith('m'):
                return int(timeframe[:-1])
            elif timeframe.endswith('h'):
                return int(timeframe[:-1]) * 60
            elif timeframe.endswith('d'):
                return int(timeframe[:-1]) * 60 * 24
            else:
                raise ValueError(f"Unsupported timeframe format: {timeframe}")
        except Exception as e:
            self.logger.error(f"Failed to parse timeframe: {str(e)}")
            raise ValueError(f"Invalid timeframe format: {timeframe}")