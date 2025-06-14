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
        
        # Set configs directory path
        self.configs_dir = Path(os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "configs"
        )))
        
        # Ensure configs directory exists
        os.makedirs(self.configs_dir, exist_ok=True)
        
        self.config_path = self._find_config(config_path)
        self.config = self._load_config()
        self._validate_config()
    
    def _find_config(self, config_path: Optional[Union[str, Path]]) -> Path:
        """Find the configuration file"""
        if config_path:
            # Convert to absolute path if it's not already
            path = Path(os.path.abspath(config_path))
            if not path.exists():
                self.logger.warning(f"Config file not found at {path}")
            return path
        
        # First check in pybit_bot/configs directory
        configs_path = self.configs_dir / "config.json"
        if configs_path.exists():
            self.logger.info(f"Using config file from configs directory: {configs_path}")
            return configs_path
        
        # Try default locations (always convert to absolute paths)
        default_paths = [
            Path(os.path.abspath("config.json")),
            Path(os.path.abspath("../config.json")),
            Path(os.path.expanduser("~/.pybit_bot/config.json")),
        ]
        
        for path in default_paths:
            if path.exists():
                self.logger.info(f"Using config file: {path}")
                return path
        
        # If no config found, use the configs directory path
        self.logger.warning(f"No config file found, will create at {configs_path}")
        return configs_path
    
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
            # Handle the case where config_path is just a filename without directory
            directory = os.path.dirname(self.config_path)
            if directory:  # Only try to create directory if there is one
                os.makedirs(directory, exist_ok=True)
            
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
                    "enabled": True,
                    "step_size": 1.0
                },
                "tva": {
                    "enabled": True,
                    "length": 15
                },
                "cvd": {
                    "enabled": True,
                    "cumulation_length": 25
                },
                "vfi": {
                    "enabled": True,
                    "lookback": 50
                },
                "atr": {
                    "enabled": True,
                    "length": 14
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
            },
            "strategy_a": {
                "enabled": True,
                "filter_confluence": True,
                "use_limit_entries": True,
                "entry_settings": {
                    "max_long_trades": 1,
                    "max_short_trades": 1,
                    "order_timeout_seconds": 30
                },
                "risk_settings": {
                    "stop_loss_multiplier": 2.0,
                    "take_profit_multiplier": 4.0,
                    "trailing_stop": {
                        "enabled": True,
                        "activation_threshold": 0.5,
                        "atr_multiplier": 2.0
                    }
                }
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
        
    def load_indicator_config(self) -> Dict[str, Any]:
        """
        Load the indicator configuration from the configs directory
        
        Returns:
            Indicator configuration dictionary
        """
        indicator_path = self.configs_dir / "indicator.json"
        
        try:
            if indicator_path.exists():
                with open(indicator_path, 'r', encoding='utf-8') as f:
                    indicator_config = json.load(f)
                    self.logger.info(f"Loaded indicator config from {indicator_path}")
                    return indicator_config
            else:
                self.logger.warning(f"No indicator.json found at {indicator_path}, using indicators from main config")
                return {"indicators": self.config.get("indicators", {})}
        except Exception as e:
            self.logger.error(f"Error loading indicator config: {str(e)}")
            return {"indicators": self.config.get("indicators", {})}