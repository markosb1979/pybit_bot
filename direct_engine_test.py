"""
Direct test of PyBit Bot engine with enhanced logging
"""
import os
import sys
import time
from datetime import datetime

# Add project root to Python path to ensure imports work correctly
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

def test_engine():
    """Directly test the trading engine"""
    print("=" * 60)
    print("PYBIT BOT ENGINE DIRECT TEST")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # Import the engine from the correct location
        from pybit_bot.engine import TradingEngine
        print("✓ Successfully imported TradingEngine")
        
        # Find config file
        config_path = os.path.join("pybit_bot", "configs", "config.json")
        if not os.path.exists(config_path):
            print(f"✗ Config file not found at {config_path}")
            return False
        
        print(f"✓ Using config file: {config_path}")
        
        # Initialize engine
        print("\nInitializing trading engine...")
        engine = TradingEngine(config_path)
        print("✓ Engine initialized")
        
        # Start engine
        print("\nStarting trading engine...")
        result = engine.start()
        
        if result:
            print("✓ Engine started successfully")
            
            # Run for a short time to observe behavior
            print("\nRunning engine for 30 seconds...")
            for i in range(30):
                sys.stdout.write(f"\rRunning: {i+1}/30 seconds")
                sys.stdout.flush()
                time.sleep(1)
            print("\n")
            
            # Check status
            print("Engine status:")
            if hasattr(engine, 'get_status'):
                status = engine.get_status()
                print(f"✓ Status: {status}")
            else:
                print("✗ No get_status method available")
            
            # Stop engine
            print("\nStopping engine...")
            engine.stop()
            print("✓ Engine stopped")
            
            return True
        else:
            print("✗ Engine failed to start")
            return False
            
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_engine()