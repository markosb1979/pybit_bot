"""
Configuration loader for the trading bot.
Handles loading and validating JSON configuration files.
"""

import os
import json
import logging
from typing import Dict, Optional


class ConfigLoader:
    """
    Utility class for loading and validating configuration files.
    """
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize the config loader.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir
        self.logger = logging.getLogger(__name__)
    
    def load_config(self, config_file: str) -> Optional[Dict]:
        """
        Load a configuration file.
        
        Args:
            config_file: Name of the configuration file
            
        Returns:
            Configuration dictionary or None if loading fails
        """
        config_path = os.path.join(self.config_dir, config_file)
        
        if not os.path.exists(config_path):
            self.logger.error(f"Configuration file not found: {config_path}")
            return None
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.logger.info(f"Loaded configuration from {config_path}")
            return config
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON in {config_path}: {str(e)}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            return None
    
    def save_config(self, config: Dict, config_file: str) -> bool:
        """
        Save a configuration to a file.
        
        Args:
            config: Configuration dictionary
            config_file: Name of the configuration file
            
        Returns:
            Boolean indicating success
        """
        config_path = os.path.join(self.config_dir, config_file)
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.logger.info(f"Saved configuration to {config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving configuration to {config_path}: {str(e)}")
            return False
    
    def load_indicator_config(self) -> Optional[Dict]:
        """
        Load the indicator configuration.
        
        Returns:
            Indicator configuration dictionary or None if loading fails
        """
        return self.load_config("indicator.json")
    
    def validate_indicator_config(self, config: Dict) -> bool:
        """
        Validate the indicator configuration.
        
        Args:
            config: Indicator configuration dictionary
            
        Returns:
            Boolean indicating if configuration is valid
        """
        if not config:
            return False
        
        # Check if required sections exist
        required_sections = ['indicators', 'timeframes']
        for section in required_sections:
            if section not in config:
                self.logger.error(f"Missing required section '{section}' in indicator configuration")
                return False
        
        # Check if indicator section has required indicators
        required_indicators = ['atr', 'cvd', 'tva', 'vfi', 'luxfvgtrend']
        for indicator in required_indicators:
            if indicator not in config['indicators']:
                self.logger.error(f"Missing indicator '{indicator}' in indicator configuration")
                return False
        
        # Check if timeframes section has required fields
        if 'default' not in config['timeframes']:
            self.logger.error("Missing 'default' field in timeframes section")
            return False
        
        return True