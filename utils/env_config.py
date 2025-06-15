"""
Environment configuration loader for Bybit Trading Bot.
Loads API credentials and settings from .env file.
"""

import os
import logging
from typing import Dict, Optional
from dotenv import load_dotenv


class EnvConfigLoader:
    """
    Utility class for loading configuration from environment variables.
    """
    
    def __init__(self, env_file: str = ".env"):
        """
        Initialize the environment config loader.
        
        Args:
            env_file: Path to .env file (default: ".env" in root directory)
        """
        self.env_file = env_file
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables
        load_dotenv(self.env_file)
        self.logger.info(f"Loaded environment variables from {env_file}")
    
    def get_api_credentials(self) -> Dict[str, str]:
        """
        Get Bybit API credentials from environment variables.
        
        Returns:
            Dictionary with API key, secret, and testnet flag
        """
        api_key = os.getenv("BYBIT_API_KEY", "")
        api_secret = os.getenv("BYBIT_API_SECRET", "")
        testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        
        if not api_key or not api_secret:
            self.logger.warning("API credentials not found in environment variables")
        
        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "testnet": testnet
        }
    
    def get_config(self) -> Dict:
        """
        Get complete configuration from environment variables.
        
        Returns:
            Dictionary with all configuration values
        """
        config = {
            **self.get_api_credentials(),
            "symbol": os.getenv("SYMBOL", "BTCUSDT"),
            "quantity": float(os.getenv("QUANTITY", "0.001")),
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "strategy_loop_interval": int(os.getenv("STRATEGY_LOOP_INTERVAL", "5")),
            "tpsl_check_interval": int(os.getenv("TPSL_CHECK_INTERVAL", "5")),
            "max_placement_attempts": int(os.getenv("MAX_PLACEMENT_ATTEMPTS", "3")),
            "retry_delay": int(os.getenv("RETRY_DELAY", "5"))
        }
        
        return config