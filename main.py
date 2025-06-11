"""
Main entry point for Bybit Trading Bot.
Loads configuration, initializes components, and starts the bot.
"""

import os
import logging
import argparse
import time
from typing import Dict, Optional

from utils.env_config import EnvConfigLoader
from utils.config_loader import ConfigLoader
from utils.state_persistence import StatePersistence
from utils.signal_logger import SignalLogger

# Import managers
from managers.strategy_manager import StrategyManager
from managers.tpsl_manager import TPSLManager

# Import strategies
from strategies.strategy_a import StrategyA
from strategies.strategy_b import StrategyB


def setup_logging(log_level: str = "INFO") -> None:
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (default: INFO)
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/bot.log"),
            logging.StreamHandler()
        ]
    )


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Bybit Trading Bot")
    
    parser.add_argument(
        "--strategy", 
        type=str, 
        choices=["strategy_a", "strategy_b"], 
        default="strategy_a",
        help="Trading strategy to use"
    )
    
    parser.add_argument(
        "--env_file", 
        type=str, 
        default=".env",
        help="Path to .env file with API credentials"
    )
    
    parser.add_argument(
        "--indicator_config", 
        type=str, 
        default="config/indicator.json",
        help="Path to indicator configuration file"
    )
    
    return parser.parse_args()


def main():
    """
    Main function to initialize and run the trading bot.
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Load environment configuration
    env_config = EnvConfigLoader(args.env_file)
    config = env_config.get_config()
    
    # Set up logging
    setup_logging(config.get("log_level", "INFO"))
    logger = logging.getLogger(__name__)
    logger.info("Starting Bybit Trading Bot")
    
    # Log if we're in testnet or production
    if config.get("testnet", True):
        logger.info("Running in TESTNET mode")
    else:
        logger.warning("Running in PRODUCTION mode - Real funds will be used!")
    
    # Load indicator configuration
    config_loader = ConfigLoader()
    indicator_config = config_loader.load_config("indicator.json")
    
    if not indicator_config:
        logger.error("Failed to load indicator configuration")
        return
    
    # Initialize state persistence
    state_persistence = StatePersistence("state.db")
    
    # Initialize signal logger
    signal_logger = SignalLogger()
    
    try:
        # Here you would initialize your client, OrderManager, and DataManager
        # For now, we'll just print a placeholder message
        logger.info(f"Would initialize client with API credentials from {args.env_file}")
        logger.info(f"Trading symbol: {config.get('symbol', 'BTCUSDT')}")
        
        # Initialize strategy based on command line argument
        if args.strategy == "strategy_a":
            strategy = StrategyA({**config, **indicator_config}, config.get("symbol", "BTCUSDT"))
            logger.info("Initialized Strategy A")
        else:
            strategy = StrategyB({**config, **indicator_config}, config.get("symbol", "BTCUSDT"))
            logger.info("Initialized Strategy B")
        
        # Validate strategy configuration
        is_valid, error = strategy.validate_config()
        if not is_valid:
            logger.error(f"Invalid strategy configuration: {error}")
            return
        
        logger.info("Strategy configuration validated successfully")
        
        # In a real implementation, you would:
        # 1. Initialize client
        # 2. Initialize OrderManager with client
        # 3. Initialize DataManager with client
        # 4. Initialize TPSLManager with OrderManager and DataManager
        # 5. Initialize StrategyManager with OrderManager, DataManager, and TPSLManager
        # 6. Add strategy to StrategyManager
        # 7. Start StrategyManager
        
        logger.info("Bot initialization completed")
        logger.info(f"Strategy {args.strategy} loaded and ready")
        
        # Placeholder for actual bot execution
        logger.info("Press Ctrl+C to stop the bot")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
    finally:
        # Clean up resources
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    main()