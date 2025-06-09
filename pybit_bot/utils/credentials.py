"""
Credentials handling for PyBit Bot
"""

import os
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

from ..core.client import APICredentials
from ..exceptions.errors import ConfigurationError
from .logger import Logger


def load_credentials(env_path: Optional[Path] = None, logger: Optional[Logger] = None) -> APICredentials:
    """
    Load API credentials from .env file
    
    Args:
        env_path: Path to .env file (default: project root .env)
        logger: Logger instance
    
    Returns:
        APICredentials object
    
    Raises:
        ConfigurationError: If required credentials are missing
    """
    
    logger = logger or Logger("Credentials")
    
    # Try to load from .env file
    if env_path and env_path.exists():
        logger.info(f"Loading credentials from {env_path}")
        load_dotenv(env_path)
    else:
        # Try default locations
        default_paths = [
            Path(".env"),
            Path("../.env"),
            Path(os.path.expanduser("~/.pybit_bot/.env")),
        ]
        
        for path in default_paths:
            if path.exists():
                logger.info(f"Loading credentials from {path}")
                load_dotenv(path)
                break
        else:
            logger.warning("No .env file found, using environment variables")
    
    # Get credentials from environment
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
    
    # Validate credentials
    if not api_key or not api_secret:
        logger.error("Missing API credentials!")
        logger.info("Please ensure .env file contains:")
        logger.info("BYBIT_API_KEY=your_api_key")
        logger.info("BYBIT_API_SECRET=your_api_secret")
        logger.info("BYBIT_TESTNET=true")
        raise ConfigurationError("API credentials not found in environment")
    
    logger.info(f"Loaded credentials for {'testnet' if testnet else 'mainnet'}")
    
    return APICredentials(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )