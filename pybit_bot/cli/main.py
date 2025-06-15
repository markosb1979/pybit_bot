#!/usr/bin/env python
"""
PyBit Bot - Command Line Interface
"""
import os
import sys
import argparse
import logging
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.engine import TradingEngine
from pybit_bot.cli.monitor import BotMonitor
from pybit_bot.cli.commands import (
    start_command, stop_command, status_command, 
    positions_command, orders_command, 
    logs_command, config_command
)

def setup_logging():
    """Setup logging for CLI operations"""
    log_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, f"cli_{datetime.now().strftime('%Y%m%d')}.log")),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("pybit_cli")

def main():
    """Main CLI entry point"""
    logger = setup_logging()
    
    parser = argparse.ArgumentParser(description="PyBit Bot - Command Line Interface")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the trading bot")
    start_parser.add_argument("--config", "-c", default="config.json", help="Path to config file")
    start_parser.add_argument("--testnet", "-t", action="store_true", help="Use testnet")
    start_parser.add_argument("--daemon", "-d", action="store_true", help="Run as daemon")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the trading bot")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show bot status")
    
    # Positions command
    positions_parser = subparsers.add_parser("positions", help="Show current positions")
    
    # Orders command
    orders_parser = subparsers.add_parser("orders", help="Show open orders")
    
    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show logs")
    logs_parser.add_argument("--lines", "-n", type=int, default=50, help="Number of lines to show")
    logs_parser.add_argument("--follow", "-f", action="store_true", help="Follow log output")
    
    # Config command
    config_parser = subparsers.add_parser("config", help="View or edit configuration")
    config_parser.add_argument("--edit", "-e", action="store_true", help="Edit configuration")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Start real-time monitoring dashboard")
    monitor_parser.add_argument("--refresh", "-r", type=int, default=5, help="Refresh rate in seconds")
    
    args = parser.parse_args()
    
    # Execute the appropriate command
    if args.command == "start":
        start_command(args, logger)
    elif args.command == "stop":
        stop_command(args, logger)
    elif args.command == "status":
        status_command(args, logger)
    elif args.command == "positions":
        positions_command(args, logger)
    elif args.command == "orders":
        orders_command(args, logger)
    elif args.command == "logs":
        logs_command(args, logger)
    elif args.command == "config":
        config_command(args, logger)
    elif args.command == "monitor":
        # Import here to avoid circular imports
        from pybit_bot.cli.monitor import start_monitor
        start_monitor(args, logger)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()