"""
Command-line interface for running the trading bot
"""

import asyncio
import argparse
import os
import signal
import sys
import logging
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pybit_bot.core.trading_bot import TradingBot
from pybit_bot.utils.logger import setup_logging, Logger


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="PyBit Bot - Crypto Trading Bot")
    
    parser.add_argument(
        "--config", 
        type=str, 
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--log-level", 
        type=str, 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level"
    )
    
    parser.add_argument(
        "--testnet",
        action="store_true",
        help="Use Bybit testnet"
    )
    
    return parser.parse_args()


async def main():
    """Main entry point for the bot"""
    args = parse_args()
    
    # Setup logging
    setup_logging(level=getattr(logging, args.log_level))
    logger = Logger("BotRunner")
    
    # Create the bot
    bot = TradingBot(config_path=args.config, logger=logger)
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    
    def handle_signal(sig):
        logger.info(f"Received signal {sig.name}, shutting down...")
        asyncio.create_task(shutdown(bot, loop))
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda sig=sig: handle_signal(sig))
    
    # Start the bot
    try:
        logger.info("Starting PyBit Bot")
        await bot.start()
        
        # Keep running until shutdown
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
    finally:
        await shutdown(bot, loop)


async def shutdown(bot, loop):
    """Shutdown the bot and event loop gracefully"""
    try:
        await bot.stop()
    finally:
        loop.stop()


if __name__ == "__main__":
    asyncio.run(main())