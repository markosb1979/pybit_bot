"""
API Credentials - Load and manage API credentials from environment variables.

This module handles loading API keys and secrets from the .env file and provides
a structured way to access these credentials throughout the application.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from ..utils.logger import Logger

class APICredentials:
    """
    Handles API credential loading and management.
    
    Provides a structured interface to access API keys and secrets for various services.
    """
    
    def __init__(self, logger=None):
        """
        Initialize and load API credentials from environment variables.
        
        Args:
            logger: Optional Logger instance
        """
        self.logger = logger or Logger("APICredentials")
        self.logger.debug(f"→ __init__()")
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Bybit API credentials
        self.bybit_api_key = os.getenv('BYBIT_API_KEY', '')
        self.bybit_api_secret = os.getenv('BYBIT_API_SECRET', '')
        
        # Check if credentials are loaded
        if not self.bybit_api_key or not self.bybit_api_secret:
            self.logger.warning("Bybit API credentials not found or incomplete in .env file")
        else:
            # Mask credentials for security in logs
            masked_key = self.bybit_api_key[:4] + '*' * (len(self.bybit_api_key) - 8) + self.bybit_api_key[-4:]
            self.logger.info(f"Loaded Bybit API credentials (key: {masked_key})")
        
        # Testnet flag
        self.use_testnet = os.getenv('USE_TESTNET', 'true').lower() == 'true'
        self.logger.info(f"Using Bybit {'testnet' if self.use_testnet else 'mainnet'}")
        
        self.logger.debug(f"← __init__ completed")
    
    def get_bybit_credentials(self) -> tuple:
        """
        Get Bybit API credentials.
        
        Returns:
            Tuple of (api_key, api_secret, use_testnet)
        """
        self.logger.debug(f"→ get_bybit_credentials()")
        self.logger.debug(f"← get_bybit_credentials returned credentials")
        return (self.bybit_api_key, self.bybit_api_secret, self.use_testnet)
    
    def has_valid_credentials(self) -> bool:
        """
        Check if valid API credentials are available.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        self.logger.debug(f"→ has_valid_credentials()")
        valid = bool(self.bybit_api_key and self.bybit_api_secret)
        self.logger.debug(f"← has_valid_credentials returned {valid}")
        return valid
    
    @staticmethod
    def load_from_env() -> 'APICredentials':
        """
        Static factory method to create an instance from environment.
        
        Returns:
            New APICredentials instance
        """
        return APICredentials()