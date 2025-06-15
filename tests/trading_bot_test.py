# trading_bot_test.py
import asyncio
import os
import sys
import inspect
from datetime import datetime
from dotenv import load_dotenv

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pybit_bot.utils.config_loader import ConfigLoader
from pybit_bot.core.client import BybitClient, APICredentials
from pybit_bot.utils.logger import Logger

# Import the TradingEngine
try:
    from pybit_bot.engine import TradingEngine
    print("Imported TradingEngine from pybit_bot.engine")
except ImportError:
    print("Could not import TradingEngine from pybit_bot.engine")
    sys.exit(1)

async def test_trading_engine():
    """Test the main trading engine with all dependencies properly initialized"""
    # Load API keys from .env file
    load_dotenv()
    
    # Path to the configuration file - use the full path to the config file
    config_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'pybit_bot', 
        'configs', 
        'config.json'
    ))
    
    # Ensure the config file exists
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at: {config_path}")
        sys.exit(1)
    
    # Get current date and time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Initialize test with detailed information
    print(f"Starting Trading Engine test with:")
    print(f"- Config path: {config_path}")
    print(f"- Test mode: {True}")
    print(f"- Date/Time: {current_time} UTC")
    
    # Initialize Trading Engine
    print("\nInitializing Trading Engine...")
    engine = TradingEngine(config_path)
    print("✓ Successfully initialized Trading Engine")
    
    # Check if methods are async or sync
    is_start_async = inspect.iscoroutinefunction(engine.start)
    is_stop_async = inspect.iscoroutinefunction(engine.stop) if hasattr(engine, 'stop') else False
    
    print(f"- start() is {'async' if is_start_async else 'synchronous'}")
    print(f"- stop() is {'async' if is_stop_async else 'synchronous'}")
    
    # Starting the engine
    print("\nStarting Trading Engine...")
    try:
        if is_start_async:
            start_result = await engine.start()
        else:
            start_result = engine.start()
        
        print(f"✓ Trading Engine started successfully. Result: {start_result}")
        
        # Run for a short period
        print("\nRunning for 10 seconds...")
        for i in range(2):
            await asyncio.sleep(5)
            if hasattr(engine, "get_status"):
                status = engine.get_status()
                print(f"Status update ({(i+1)*5}s): {status}")
            else:
                print(f"Status update ({(i+1)*5}s): Running...")
                
        # Examine engine attributes
        print("\nTrading Engine attributes:")
        for attr in dir(engine):
            if not attr.startswith('_'):  # Skip private attributes
                try:
                    value = getattr(engine, attr)
                    if not callable(value):  # Only show non-method attributes
                        print(f"- {attr}: {value}")
                except Exception as e:
                    print(f"- {attr}: Error accessing ({e})")
    
    except Exception as e:
        print(f"✗ Error running Trading Engine: {e}")
    finally:
        # Shutdown
        print("\nStopping Trading Engine...")
        try:
            if hasattr(engine, 'stop'):
                if is_stop_async:
                    stop_result = await engine.stop()
                else:
                    stop_result = engine.stop()
                print(f"✓ Trading Engine stopped. Result: {stop_result}")
            else:
                print("⚠ Trading Engine has no stop() method.")
        except Exception as e:
            print(f"✗ Error stopping Trading Engine: {e}")

if __name__ == "__main__":
    asyncio.run(test_trading_engine())