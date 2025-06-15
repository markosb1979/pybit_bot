#!/usr/bin/env python
"""
PyBit Bot Runner - Start and manage the trading bot
"""
import os
import sys
import argparse
import signal
import json
import time
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.engine import TradingEngine
from pybit_bot.utils.logger import Logger

# Global variables
engine = None
running = True
logger = None

def signal_handler(sig, frame):
    """Handle termination signals"""
    global running
    
    if logger:
        logger.info("Received termination signal. Shutting down...")
    
    running = False

def update_status_file(engine):
    """Update the status file with current engine state"""
    status_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot")
    os.makedirs(status_dir, exist_ok=True)
    status_file = os.path.join(status_dir, "status.json")
    
    try:
        status = engine.get_status()
        
        # Add positions and orders if available
        if hasattr(engine, 'order_manager') and engine.order_manager:
            status['positions'] = engine.order_manager.get_positions()
            status['orders'] = engine.order_manager.get_open_orders()
        
        # Write to file
        with open(status_file, 'w') as f:
            json.dump(status, f, indent=2)
    
    except Exception as e:
        if logger:
            logger.error(f"Failed to update status file: {str(e)}")

def run_bot(config_path, testnet=False):
    """Run the trading bot"""
    global engine, logger
    
    # Initialize logger
    log_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot", "logs")
    os.makedirs(log_dir, exist_ok=True)
    logger = Logger("BotRunner")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize engine
        logger.info(f"Initializing trading engine with config: {config_path}")
        engine = TradingEngine(config_path)
        
        # Start the engine
        logger.info("Starting trading engine...")
        result = engine.start()
        
        if not result:
            logger.error("Failed to start trading engine.")
            return
        
        logger.info("Trading engine started successfully.")
        
        # Main loop
        while running:
            # Update status file
            update_status_file(engine)
            
            # Sleep for a bit
            time.sleep(5)
        
        # Shutdown
        logger.info("Shutting down trading engine...")
        engine.stop()
        logger.info("Trading engine stopped.")
    
    except Exception as e:
        logger.error(f"Error running trading bot: {str(e)}")
        if engine:
            try:
                engine.stop()
            except:
                pass

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="PyBit Bot Runner")
    parser.add_argument("--config", "-c", default="config.json", help="Path to config file")
    parser.add_argument("--testnet", "-t", action="store_true", help="Use testnet")
    
    args = parser.parse_args()
    run_bot(args.config, args.testnet)

if __name__ == "__main__":
    main()