"""
Command line interface for the pybit_bot trading system
"""

import os
import sys
import argparse
import logging
from datetime import datetime

from ..engine import TradingEngine
from ..utils.logger import Logger

logger = Logger("BotRunner")

def start_bot(args):
    """
    Start the trading bot with the specified configuration
    
    Args:
        args: Command line arguments
    """
    try:
        # Use the known good config directory path
        config_dir = r"G:\My Drive\MyBotFolder\Bybit\pybit_bot\pybit_bot\configs"
        
        # Check if the directory exists
        if not os.path.exists(config_dir) or not os.path.isdir(config_dir):
            # Try the path provided in arguments
            config_dir = args.config
            logger.warning(f"Primary config directory not found, using provided path: {config_dir}")
        
        logger.info(f"Initializing trading engine with config directory: {config_dir}")
        print(f"Initializing trading engine with config directory: {config_dir}")
        
        # Initialize the trading engine with the directory path
        engine = TradingEngine(config_dir)
        
        # Initialize components
        if not engine.initialize():
            logger.error("Failed to initialize trading engine")
            print("ERROR: Failed to initialize trading engine")
            return
            
        # Start trading
        if engine.start():
            logger.info("Trading engine started successfully")
            print("Trading engine started successfully")
            
            # Keep process running until interrupted
            try:
                print("Press CTRL+C to stop the bot")
                while engine.is_running:
                    # Sleep briefly to avoid high CPU usage
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, stopping engine")
                print("Stopping trading engine...")
                engine.stop()
        else:
            logger.error("Failed to start trading engine")
            print("ERROR: Failed to start trading engine")
            
    except Exception as e:
        logger.error(f"Error running trading bot: {str(e)}")
        print(f"Error running trading bot: {str(e)}")

def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(description="PyBit Bot - Automated trading for Bybit")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the trading bot")
    
    # Default to the configs directory that definitely exists based on diagnostic
    default_config_dir = r"G:\My Drive\MyBotFolder\Bybit\pybit_bot\pybit_bot\configs"
    
    start_parser.add_argument(
        "--config", 
        default=default_config_dir,
        help="Path to config directory"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute command
    if args.command == "start":
        start_bot(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()