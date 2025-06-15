# trading_bot_test.py
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the TradingEngine as found by find_trading_bot.py
try:
    from pybit_bot.engine import TradingEngine
    print("Imported TradingEngine from pybit_bot.engine")
except ImportError:
    # Fallback to mock if import fails
    print("Could not import TradingEngine. Using mock instead.")
    class TradingEngine:
        def __init__(self, config_path):
            self.config_path = config_path
            print(f"MOCK TradingEngine created with config: {config_path}")
        
        async def start(self):
            print("MOCK TradingEngine started")
        
        def get_status(self):
            return {"status": "running", "active_trades": 0}
        
        async def stop(self):
            print("MOCK TradingEngine stopped")

async def test_trading_bot():
    # Load API keys from .env file
    load_dotenv()
    
    # Path to the configuration file
    config_path = "config.json"
    
    # Test case 1: Initialize Trading Bot
    bot = TradingEngine(config_path)
    print(f"TradingEngine initialized with config: {config_path}")
    
    # Test case 2: Start the bot
    print("Starting TradingEngine...")
    try:
        await bot.start()
        print("TradingEngine started")
        
        # Test case 3: Check bot status
        if hasattr(bot, "get_status"):
            status = bot.get_status()
            print(f"Bot status: {status}")
        else:
            print("Bot status method not available")
        
        # Test case 4: Run the bot for a short period
        print("Running bot for 15 seconds...")
        
        for i in range(3):
            await asyncio.sleep(5)
            if hasattr(bot, "get_status"):
                status = bot.get_status()
                print(f"Status update ({(i+1)*5}s): {status}")
            else:
                print(f"Status update ({(i+1)*5}s): Running...")
    except Exception as e:
        print(f"Error running bot: {e}")
    finally:
        # Test case 5: Test bot shutdown
        print("Stopping TradingEngine...")
        if hasattr(bot, "stop"):
            await bot.stop()
        print("TradingEngine stopped")

if __name__ == "__main__":
    asyncio.run(test_trading_bot())