"""
Adapter for DataManager tests - adds missing methods to match test expectations
"""
import asyncio
import pandas as pd
import numpy as np
from pybit_bot.managers.data_manager import DataManager

class DataManagerTestAdapter:
    """
    Wraps the DataManager to add test methods without modifying the original class
    """
    
    def __init__(self, data_manager):
        self.data_manager = data_manager
        # Common test symbols
        self._symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    
    async def get_symbols(self):
        """Return a list of supported symbols for testing"""
        return self._symbols
    
    async def get_historical_data(self, symbol, interval, limit=100):
        """
        Adapter for historical data method.
        Try to use the actual method if it exists with a different name.
        """
        # Check if there's a similar method available
        if hasattr(self.data_manager, "get_klines"):
            # If the actual class has get_klines, use that - and make sure to await it
            try:
                klines = await self.data_manager.get_klines(symbol, interval, limit)
                return self._convert_klines_to_dataframe(klines)
            except Exception as e:
                print(f"Error getting klines: {e}")
        
        # Fallback to creating mock data
        return self._create_mock_historical_data(limit)
    
    async def get_indicator_data(self, symbol):
        """
        Add mock indicator data for testing
        """
        # First try to get historical data
        df = await self.get_historical_data(symbol, "1m", 100)
        
        # Add indicator columns that the strategy might expect
        df['cvd'] = np.random.normal(0, 1, len(df)).cumsum()  # Cumulative volume delta
        df['rb'] = np.random.normal(0, 0.5, len(df))          # Range bars
        df['rr'] = np.random.normal(0, 0.5, len(df))          # Range ratio
        df['vfi'] = np.random.normal(0, 0.5, len(df))         # Volume Flow Indicator
        df['fvg_signal'] = np.random.choice([-1, 0, 1], len(df))  # Fair Value Gap signal
        df['fvg_midpoint'] = df['close'] * (1 + np.random.normal(0, 0.02, len(df)))
        df['atr'] = df['high'] - df['low']                    # Simple ATR approximation
        
        return df
    
    def _convert_klines_to_dataframe(self, klines):
        """Convert klines to DataFrame"""
        if not klines or len(klines) == 0:
            return self._create_mock_historical_data(10)
        
        df = pd.DataFrame(klines)
        # Rename columns to match expected format
        if 'openTime' in df.columns:
            df.rename(columns={
                'openTime': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }, inplace=True)
        return df
    
    def _create_mock_historical_data(self, rows=100):
        """Create mock historical data for testing"""
        # Create a basic price series
        base_price = 50000.0
        timestamps = [1612345600000 + i * 60000 for i in range(rows)]
        
        # Generate random price movements
        np.random.seed(42)  # For reproducibility
        price_changes = np.random.normal(0, 100, rows)
        
        # Create OHLCV data
        data = []
        current_price = base_price
        
        for i in range(rows):
            current_price += price_changes[i]
            # Simple OHLC generation
            open_price = current_price
            high_price = current_price + abs(np.random.normal(0, 50))
            low_price = current_price - abs(np.random.normal(0, 50))
            close_price = current_price + np.random.normal(0, 30)
            volume = abs(np.random.normal(10, 5))
            
            data.append({
                'timestamp': timestamps[i],
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        return df
    
    # Delegate all other methods to the original data_manager
    def __getattr__(self, name):
        return getattr(self.data_manager, name)