#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyBit Bot Runner

Command-line tool for running the trading bot in live or paper trading mode.
Handles initialization, configuration, and graceful shutdown.
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import datetime
from typing import Dict, List, Any, Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot_runner.log")
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)


class BotRunner:
    """Command-line tool for running the PyBit Bot."""
    
    def __init__(self):
        """Initialize the bot runner."""
        self.config = {}
        self.engine = None
        self.is_running = False
        self.stop_requested = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            return {}
    
    def _handle_shutdown_signal(self, signum, frame):
        """
        Handle shutdown signals (SIGINT, SIGTERM).
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        if self.stop_requested:
            logger.warning("Forced shutdown requested. Exiting immediately.")
            sys.exit(1)
        
        logger.info("Shutdown signal received. Stopping bot gracefully...")
        self.stop_requested = True
        
        # In a non-blocking way, request engine to stop
        if self.engine:
            try:
                self.engine.stop()
            except Exception as e:
                logger.error(f"Error stopping engine: {str(e)}")
    
    def start_bot(self, args: argparse.Namespace) -> bool:
        """
        Start the trading bot with the given arguments.
        
        Args:
            args: Command-line arguments
            
        Returns:
            True if started successfully, False otherwise
        """
        logger.info("Starting PyBit Bot...")
        
        # Load config
        if args.config:
            self.config = self._load_config(args.config)
            if not self.config:
                logger.error("Failed to load configuration.")
                return False
            
            logger.info(f"Loaded configuration from {args.config}")
        else:
            logger.error("No configuration file specified.")
            return False
        
        # Override config with command-line arguments
        if args.testnet:
            logger.info("Running in testnet mode")
            self.config.setdefault('connection', {})['testnet'] = True
        
        if args.paper_trading:
            logger.info("Running in paper trading mode")
            self.config.setdefault('trading', {})['paper_trading'] = True
        
        if args.symbols:
            symbols = [s.strip() for s in args.symbols.split(',')]
            logger.info(f"Trading symbols: {symbols}")
            self.config.setdefault('trading', {})['symbols'] = symbols
        
        # Import here to avoid circular imports
        try:
            from pybit_bot.engine import TradingEngine
            
            # Create and initialize engine
            self.engine = TradingEngine(args.config)
            
            if not self.engine.initialize():
                logger.error("Failed to initialize trading engine.")
                return False
            
            # Start the engine
            if not self.engine.start():
                logger.error("Failed to start trading engine.")
                return False
            
            self.is_running = True
            
            # Start monitoring dashboard if requested
            if args.dashboard:
                try:
                    from pybit_bot.monitoring.dashboard import Dashboard
                    dashboard = Dashboard(args.config)
                    dashboard.start()
                except ImportError:
                    logger.warning("Could not start dashboard. Make sure dash is installed.")
                except Exception as e:
                    logger.error(f"Error starting dashboard: {str(e)}")
            
            logger.info("PyBit Bot started successfully")
            return True
            
        except ImportError as e:
            logger.error(f"Failed to import required modules: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}")
            return False
    
    def stop_bot(self) -> bool:
        """
        Stop the trading bot.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if not self.is_running:
            logger.warning("Bot is not running.")
            return True
        
        logger.info("Stopping PyBit Bot...")
        
        try:
            if self.engine:
                self.engine.stop()
            
            self.is_running = False
            logger.info("PyBit Bot stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping bot: {str(e)}")
            return False
    
    def run_bot(self, args: argparse.Namespace) -> int:
        """
        Run the trading bot and handle the main loop.
        
        Args:
            args: Command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        if not self.start_bot(args):
            return 1
        
        try:
            # Main loop
            while self.is_running and not self.stop_requested:
                # Check engine status
                if self.engine:
                    status = self.engine.get_status()
                    if status and not status.get('is_running', False):
                        logger.warning("Engine has stopped. Shutting down.")
                        break
                
                # Sleep to avoid high CPU usage
                time.sleep(1)
            
            # Cleanup
            self.stop_bot()
            return 0
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Stopping bot...")
            self.stop_bot()
            return 0
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            self.stop_bot()
            return 1


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(description='PyBit Bot Runner')
    
    # Configuration
    parser.add_argument('--config', type=str, required=True, help='Path to configuration file')
    
    # Mode flags
    parser.add_argument('--testnet', action='store_true', help='Use testnet instead of mainnet')
    parser.add_argument('--paper-trading', action='store_true', help='Use paper trading mode')
    
    # Trading parameters
    parser.add_argument('--symbols', type=str, help='Comma-separated list of symbols to trade')
    
    # Features
    parser.add_argument('--dashboard', action='store_true', help='Start the monitoring dashboard')
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Logging level')
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create and run bot
    runner = BotRunner()
    exit_code = runner.run_bot(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()