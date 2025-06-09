"""
Configuration management with JSON support
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class TradingConfig:
    """Main trading configuration"""
    # API Settings
    testnet: bool = True
    api_key: str = ""
    api_secret: str = ""
    
    # Trading Parameters  
    symbol: str = "BTCUSDT"
    position_size: float = 0.01  # Position size as fraction of balance
    max_position_size: float = 0.1
    stop_loss_pct: float = 0.02  # 2%
    take_profit_pct: float = 0.04  # 4%
    
    # Risk Management
    max_daily_loss: float = 0.05  # 5% of balance
    max_open_positions: int = 3
    min_balance_threshold: float = 100.0  # USDT
    
    # Strategy Settings
    strategy_name: str = "MultiIndicatorStrategy"
    lookback_period: int = 100
    signal_threshold: float = 0.7
    
    # Indicator Parameters
    lux_fvg_settings: Dict[str, Any] = None
    tva_settings: Dict[str, Any] = None
    cvd_settings: Dict[str, Any] = None
    vfi_settings: Dict[str, Any] = None
    atr_settings: Dict[str, Any] = None
    
    # WebSocket Settings
    ws_reconnect_attempts: int = 5
    ws_ping_interval: int = 20
    
    # Logging
    log_level: str = "INFO"
    log_trades: bool = True
    log_positions: bool = True
    log_signals: bool = True
    
    def __post_init__(self):
        if self.lux_fvg_settings is None:
            self.lux_fvg_settings = {"period": 20, "sensitivity": 1.0}
        if self.tva_settings is None:
            self.tva_settings = {"period": 14, "smoothing": 3}
        if self.cvd_settings is None:
            self.cvd_settings = {"period": 20, "threshold": 0.5}
        if self.vfi_settings is None:
            self.vfi_settings = {"period": 130, "smoothing": 13}
        if self.atr_settings is None:
            self.atr_settings = {"period": 14, "multiplier": 2.0}


class ConfigManager:
    """Configuration manager with environment variable support"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = TradingConfig()
        self.load_config()
        
    def load_config(self):
        """Load configuration from file and environment variables"""
        # Load from JSON file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    
                # Update config with loaded data
                for key, value in config_data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                        
            except Exception as e:
                print(f"Error loading config file: {e}")
        
        # Override with environment variables
        self._load_from_env()
        
    def _load_from_env(self):
        """Load sensitive data from environment variables"""
        env_mappings = {
            'BYBIT_API_KEY': 'api_key',
            'BYBIT_API_SECRET': 'api_secret',
            'BYBIT_TESTNET': 'testnet',
            'TRADING_SYMBOL': 'symbol',
            'POSITION_SIZE': 'position_size',
            'STOP_LOSS_PCT': 'stop_loss_pct',
            'TAKE_PROFIT_PCT': 'take_profit_pct'
        }
        
        for env_var, config_attr in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert types appropriately
                if config_attr in ['testnet']:
                    value = value.lower() in ('true', '1', 'yes')
                elif config_attr in ['position_size', 'stop_loss_pct', 'take_profit_pct']:
                    value = float(value)
                    
                setattr(self.config, config_attr, value)
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            config_dict = asdict(self.config)
            # Remove sensitive data from saved config
            config_dict.pop('api_key', None)
            config_dict.pop('api_secret', None)
            
            with open(self.config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
                
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_config(self) -> TradingConfig:
        """Get current configuration"""
        return self.config
    
    def update_config(self, **kwargs):
        """Update configuration parameters"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def validate_config(self) -> bool:
        """Validate configuration parameters"""
        errors = []
        
        if not self.config.api_key:
            errors.append("API key is required")
        if not self.config.api_secret:
            errors.append("API secret is required")
        if self.config.position_size <= 0 or self.config.position_size > 1:
            errors.append("Position size must be between 0 and 1")
        if self.config.stop_loss_pct <= 0:
            errors.append("Stop loss percentage must be positive")
        if self.config.take_profit_pct <= self.config.stop_loss_pct:
            errors.append("Take profit must be greater than stop loss")
            
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
            
        return True