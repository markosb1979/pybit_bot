"""
Configuration management for PyBit Bot
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .logger import Logger
from ..exceptions.errors import ConfigurationError


class ConfigLoader:
    """
    Configuration loader and validator for PyBit Bot
    """
    
    def __init__(
        self, 
        config_path: Optional[Union[str, Path]] = None,
        logger: Optional[Logger] = None
    ):
        self.logger = logger or Logger("Config")
        self.config_path = self._find_config(config_path)
        self.config = self._load_config()
        self._validate_config()
    
    def _find_config(self, config_path: Optional[Union[str, Path]]) -> Path:
        """Find the configuration file"""
        if config_path:
            path = Path(config_path)
            if not path.exists():
                self.logger.warning(f"Config file not found at {path}")
                
            return path
        
        # Try default locations
        default_paths = [
            Path("config.json"),
            Path("../config.json"),
            Path(os.path.expanduser("~/.pybit_bot/config.json")),
        ]
        
        for path in default_paths:
            if path.exists():
                self.logger.info(f"Using config file: {path}")
                return path
        
        # If no config found, use the first default path and it will be created
        # with default values when needed
        self.logger.warning(f"No config file found, will create at {default_paths[0]}")
        return default_paths[0]
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not self.config_path.exists():
            self.logger.info("Config file not found, creating with default values")
            config = self._create_default_config()
            self._save_config(config)
            return config
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.logger.info("Configuration loaded successfully")
                return config
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file: {e}")
            self.logger.info("Creating new config with default values")
            config = self._create_default_config()
            self._save_config(config)
            return config
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
                self.logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}")
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        return {
            "trading": {
                "symbol": "BTCUSDT",
                "timeframe": "1m",
                "position_size_usdt": 50.0,
                "max_positions": 3
            },
            "risk": {
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.04,
                "max_daily_loss_usdt": 100.0
            },
            "indicators": {
                "luxfvgtrend": {
                    "length": 14,
                    "mult": 2.0
                },
                "tva": {
                    "volume_ma_period": 20
                },
                "cvd": {
                    "length": 20
                },
                "vfi": {
                    "period": 130
                },
                "atr": {
                    "period": 14
                }
            },
            "data": {
                "lookback_bars": {
                    "1m": 2000,
                    "5m": 1000,
                    "1h": 200
                },
                "update_interval": 60
            },
            "system": {
                "log_level": "INFO"
            }
        }
    
    def _validate_config(self):
        """Validate configuration values"""
        # Check required sections
        required_sections = ["trading", "risk", "indicators", "data", "system"]
        for section in required_sections:
            if section not in self.config:
                self.logger.error(f"Missing required section: {section}")
                self.config[section] = self._create_default_config()[section]
        
        # Validate trading section
        trading = self.config["trading"]
        if "symbol" not in trading:
            self.logger.warning("Missing symbol in config, using BTCUSDT")
            trading["symbol"] = "BTCUSDT"
            
        if "position_size_usdt" not in trading:
            self.logger.warning("Missing position size in config, using 50 USDT")
            trading["position_size_usdt"] = 50.0
        
        # Save any changes
        self._save_config(self.config)
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            path: Configuration path (e.g., 'trading.symbol')
            default: Default value if path not found
            
        Returns:
            Configuration value or default
        """
        parts = path.split('.')
        value = self.config
        
        try:
            for part in parts:
                value = value[part]
            return value
        except (KeyError, TypeError):
            return default
    
    def update(self, path: str, value: Any, save: bool = True):
        """
        Update configuration value using dot notation
        
        Args:
            path: Configuration path (e.g., 'trading.symbol')
            value: New value
            save: Whether to save the config file
        """
        parts = path.split('.')
        config = self.config
        
        # Navigate to the right level
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        
        # Update value
        config[parts[-1]] = value
        
        if save:
            self._save_config(self.config)
    
    def save(self):
        """Save current configuration"""
        self._save_config(self.config)