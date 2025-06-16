#!/usr/bin/env python
"""
Test script to verify synchronization with Bybit minute closes
"""
import asyncio
import time
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pybit_bot.core.client import BybitClient, APICredentials
from dotenv import load_dotenv

async def test_minute_sync():
    load_dotenv()
    
    # Initialize client
    credentials = APICredentials(
        api_key=os.environ.get('BYBIT_API_KEY', ''),
        api_secret=os.environ.get('BYBIT_API_SECRET', ''),
        testnet=True
    )
    
    client = BybitClient(credentials)
    
    print("Starting minute synchronization test")
    print("=" * 50)
    
    # Run for 3 cycles
    for i in range(3):
        print(f"\nTest cycle {i+1}/3:")
        
        # Get server time
        server_time = client.get_server_time()
        time_second = int(server_time.get("timeSecond", time.time()))
        
        # Calculate seconds until next minute
        seconds_to_next_minute = 60 - (time_second % 60)
        if seconds_to_next_minute == 60:
            seconds_to_next_minute = 0
            
        # Log current time and wait time
        current_time_str = datetime.fromtimestamp(time_second).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Current server time: {current_time_str}")
        print(f"Waiting {seconds_to_next_minute + 1} seconds until next minute close")
        
        # Wait until the next minute plus 1 second buffer
        await asyncio.sleep(seconds_to_next_minute + 1)
        
        # Get fresh kline
        klines = client.get_klines(
            symbol="BTCUSDT",
            interval="1",
            limit=1
        )
        
        if klines:
            # Convert kline timestamp to readable format
            kline_ts = int(klines[0][0]) / 1000  # Convert to seconds
            kline_time_str = datetime.fromtimestamp(kline_ts).strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"Got kline with timestamp: {kline_time_str}")
            print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Time difference: {time.time() - kline_ts:.2f} seconds")
            
            # Print kline data in readable format
            ohlcv = {
                "timestamp": kline_time_str,
                "open": float(klines[0][1]),
                "high": float(klines[0][2]),
                "low": float(klines[0][3]),
                "close": float(klines[0][4]),
                "volume": float(klines[0][5]),
                "turnover": float(klines[0][6])
            }
            print(f"Kline data: {json.dumps(ohlcv, indent=2)}")
        else:
            print("No kline data received")
        
        print("-" * 50)
    
    print("\nTest completed")

if __name__ == "__main__":
    asyncio.run(test_minute_sync())