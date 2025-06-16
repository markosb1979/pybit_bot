#!/usr/bin/env python
"""
Daemon process for running the PyBit Bot in the background
"""
import os
import sys
import time
import signal
import argparse
import json
from pathlib import Path

# Ensure we can import from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from pybit_bot.engine import TradingEngine

# Constants
BOT_DIR = os.path.join(os.path.expanduser("~"), ".pybit_bot")
STATUS_FILE = os.path.join(BOT_DIR, "status.json")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="PyBit Bot Daemon")
    
    parser.add_argument(
        "--config", 
        type=str, 
        required=True,
        help="Path to configuration directory"
    )
    
    return parser.parse_args()

def main():
    """Main entry point for the daemon"""
    args = parse_args()
    
    # Create engine
    engine = TradingEngine(args.config)
    
    # Initialize engine
    if not engine.initialize():
        print("Failed to initialize engine")
        return 1
    
    # Register signal handlers
    def handle_signal(sig, frame):
        print(f"Received signal {sig}, shutting down...")
        engine.stop()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Start engine
    if not engine.start():
        print("Failed to start engine")
        return 1
    
    print(f"Bot started in daemon mode with PID: {os.getpid()}")
    
    # Main loop
    try:
        status_update_interval = 5  # seconds
        last_status_update = 0
        
        while engine.is_running:
            # Update status file periodically
            current_time = time.time()
            if current_time - last_status_update >= status_update_interval:
                engine.write_status_file(STATUS_FILE)
                last_status_update = current_time
            
            time.sleep(1)
    except Exception as e:
        print(f"Error in daemon main loop: {str(e)}")
    finally:
        engine.stop()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())