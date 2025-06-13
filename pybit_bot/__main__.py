"""
Main entry point for running the trading bot.
"""

import argparse
import os
import signal
import sys
import time

from pybit_bot.engine import TradingEngine


def signal_handler(sig, frame):
    """Handle Ctrl+C and other termination signals."""
    print("\nShutting down gracefully... (press Ctrl+C again to force)")
    if engine:
        engine.stop()
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyBit Trading Bot")
    
    parser.add_argument(
        "--config", 
        type=str, 
        default="config.json", 
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug mode"
    )
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not os.path.isfile(args.config):
        print(f"Error: Configuration file '{args.config}' not found.")
        sys.exit(1)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    # Create and start engine
    engine = TradingEngine(args.config)
    
    # Initialize components
    if not engine.initialize():
        print("Failed to initialize trading engine. Exiting.")
        sys.exit(1)
    
    # Start trading
    if engine.start():
        print(f"Trading bot started with configuration from {args.config}")
        
        # Print status periodically
        try:
            while True:
                time.sleep(60)
                status = engine.get_status()
                print(f"\nEngine status: {'RUNNING' if status['is_running'] else 'STOPPED'}")
                print(f"Runtime: {status['runtime']}")
                print(f"Signals generated: {status['performance']['signals_generated']}")
                print(f"Orders placed: {status['performance']['orders_placed']}")
                print(f"Orders filled: {status['performance']['orders_filled']}")
                print(f"Active positions: {status['active_positions']}")
                print(f"Errors: {status['performance']['errors']}")
        except KeyboardInterrupt:
            pass
        finally:
            engine.stop()
            print("Trading bot stopped")
    else:
        print("Failed to start trading engine")
        sys.exit(1)