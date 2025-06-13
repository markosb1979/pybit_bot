#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuration Manager for PyBit Bot

Manages configuration files, performs validation, and provides a CLI
for creating and modifying configurations.
"""

import os
import sys
import json
import logging
import argparse
import shutil
from typing import Dict, List, Any, Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration files for PyBit Bot."""
    
    def __init__(self):
        """Initialize the configuration manager."""
        self.config_dir = "pybit_bot/configs"
        self.template_dir = os.path.join(self.config_dir, "templates")
        
        # Ensure directories exist
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.template_dir, exist_ok=True)
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
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
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in configuration file: {config_path}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            return {}
    
    def save_config(self, config: Dict[str, Any], config_path: str) -> bool:
        """
        Save configuration to a JSON file.
        
        Args:
            config: Configuration dictionary
            config_path: Path to save the configuration file
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Configuration saved to {config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            return False
    
    def validate_config(self, config: Dict[str, Any], config_type: str = "general") -> Tuple[bool, List[str]]:
        """
        Validate a configuration dictionary.
        
        Args:
            config: Configuration dictionary to validate
            config_type: Type of configuration (general, strategy, indicators, execution)
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Basic structure validation
        if not isinstance(config, dict):
            errors.append("Configuration must be a dictionary")
            return False, errors
        
        # Validate based on config type
        if config_type == "general":
            if "trading" not in config:
                errors.append("Missing 'trading' section in general config")
            
            if "connection" not in config:
                errors.append("Missing 'connection' section in general config")
            
            # Check required trading fields
            trading = config.get("trading", {})
            if not isinstance(trading, dict):
                errors.append("'trading' section must be a dictionary")
            elif "symbols" not in trading:
                errors.append("Missing 'symbols' in trading section")
            
            # Check connection fields
            connection = config.get("connection", {})
            if not isinstance(connection, dict):
                errors.append("'connection' section must be a dictionary")
            elif "api_key" not in connection and not connection.get("paper_trading", False):
                errors.append("Missing 'api_key' in connection section (required unless paper_trading=true)")
        
        elif config_type == "strategy":
            if "strategies" not in config:
                errors.append("Missing 'strategies' section in strategy config")
            
            strategies = config.get("strategies", {})
            if not isinstance(strategies, dict):
                errors.append("'strategies' section must be a dictionary")
            else:
                for strategy_name, strategy_config in strategies.items():
                    if not isinstance(strategy_config, dict):
                        errors.append(f"Strategy '{strategy_name}' configuration must be a dictionary")
                    elif "enabled" not in strategy_config:
                        errors.append(f"Missing 'enabled' flag in strategy '{strategy_name}'")
        
        elif config_type == "indicators":
            if "indicators" not in config:
                errors.append("Missing 'indicators' section in indicators config")
            
            indicators = config.get("indicators", {})
            if not isinstance(indicators, dict):
                errors.append("'indicators' section must be a dictionary")
        
        elif config_type == "execution":
            if "order_execution" not in config:
                errors.append("Missing 'order_execution' section in execution config")
            
            execution = config.get("order_execution", {})
            if not isinstance(execution, dict):
                errors.append("'order_execution' section must be a dictionary")
            
            if "risk_management" not in config:
                errors.append("Missing 'risk_management' section in execution config")
            
            risk = config.get("risk_management", {})
            if not isinstance(risk, dict):
                errors.append("'risk_management' section must be a dictionary")
        
        return len(errors) == 0, errors
    
    def create_template_config(self, config_type: str) -> Dict[str, Any]:
        """
        Create a template configuration dictionary.
        
        Args:
            config_type: Type of configuration to create
            
        Returns:
            Template configuration dictionary
        """
        if config_type == "general":
            return {
                "trading": {
                    "symbols": ["BTCUSDT", "ETHUSDT"],
                    "timeframes": ["5m", "15m", "1h"],
                    "default_quantity": 0.001,
                    "max_open_positions": 5
                },
                "connection": {
                    "testnet": True,
                    "paper_trading": False,
                    "api_key": "YOUR_API_KEY_HERE",
                    "api_secret": "YOUR_API_SECRET_HERE",
                    "recv_window": 5000
                },
                "system": {
                    "log_level": "INFO",
                    "log_dir": "logs",
                    "data_dir": "data"
                }
            }
        
        elif config_type == "strategy":
            return {
                "strategies": {
                    "strategy_a": {
                        "enabled": True,
                        "symbols": ["BTCUSDT"],
                        "timeframes": ["5m", "15m"],
                        "params": {
                            "fast_length": 12,
                            "slow_length": 26,
                            "signal_length": 9
                        }
                    },
                    "strategy_b": {
                        "enabled": False,
                        "symbols": ["ETHUSDT"],
                        "timeframes": ["15m", "1h"],
                        "params": {
                            "length": 14,
                            "threshold": 70
                        }
                    }
                }
            }
        
        elif config_type == "indicators":
            return {
                "indicators": {
                    "luxfvgtrend": {
                        "params": {
                            "length": 14,
                            "threshold": 0.5
                        }
                    },
                    "tva": {
                        "params": {
                            "fast_length": 20,
                            "slow_length": 40
                        }
                    },
                    "cvd": {
                        "params": {
                            "length": 20
                        }
                    },
                    "vfi": {
                        "params": {
                            "length": 130,
                            "coef": 0.2,
                            "vcoef": 2.5,
                            "signalLength": 5
                        }
                    },
                    "atr": {
                        "params": {
                            "length": 14
                        }
                    }
                }
            }
        
        elif config_type == "execution":
            return {
                "order_execution": {
                    "default_order_type": "LIMIT",
                    "price_offset_ticks": 2,
                    "retry_attempts": 3,
                    "retry_delay_ms": 500,
                    "use_post_only": True
                },
                "risk_management": {
                    "max_risk_per_trade_pct": 1.0,
                    "max_risk_total_pct": 5.0,
                    "default_stop_pct": 2.0,
                    "default_take_profit_pct": 3.0,
                    "use_trailing_stop": True,
                    "trailing_stop_activation_pct": 1.0,
                    "trailing_stop_callback_rate": 0.5
                },
                "tpsl_manager": {
                    "check_interval_ms": 1000,
                    "use_exchange_stops": True,
                    "use_local_stops": True
                }
            }
        
        return {}
    
    def create_config(self, args: argparse.Namespace) -> bool:
        """
        Create a new configuration file.
        
        Args:
            args: Command-line arguments
            
        Returns:
            True if created successfully, False otherwise
        """
        config_type = args.type
        output_path = args.output
        
        # Create template
        template = self.create_template_config(config_type)
        if not template:
            logger.error(f"Unknown configuration type: {config_type}")
            return False
        
        # Save template
        return self.save_config(template, output_path)
    
    def validate_config_file(self, args: argparse.Namespace) -> bool:
        """
        Validate a configuration file.
        
        Args:
            args: Command-line arguments
            
        Returns:
            True if valid, False otherwise
        """
        config_path = args.config
        config_type = args.type
        
        # Load config
        config = self.load_config(config_path)
        if not config:
            return False
        
        # Validate
        is_valid, errors = self.validate_config(config, config_type)
        
        if is_valid:
            logger.info(f"Configuration file {config_path} is valid")
            return True
        else:
            logger.error(f"Configuration file {config_path} is invalid:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
    
    def merge_configs(self, args: argparse.Namespace) -> bool:
        """
        Merge multiple configuration files.
        
        Args:
            args: Command-line arguments
            
        Returns:
            True if merged successfully, False otherwise
        """
        config_paths = args.configs
        output_path = args.output
        
        # Load all configs
        configs = []
        for path in config_paths:
            config = self.load_config(path)
            if config:
                configs.append(config)
            else:
                logger.error(f"Failed to load configuration: {path}")
                return False
        
        if not configs:
            logger.error("No valid configurations to merge")
            return False
        
        # Merge configs
        merged_config = {}
        for config in configs:
            self._recursive_merge(merged_config, config)
        
        # Save merged config
        return self.save_config(merged_config, output_path)
    
    def _recursive_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge two dictionaries.
        
        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from
            
        Returns:
            Merged dictionary
        """
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._recursive_merge(target[key], value)
            else:
                target[key] = value
        
        return target


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(description='PyBit Bot Configuration Manager')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new configuration file')
    create_parser.add_argument('--type', type=str, required=True, 
                              choices=['general', 'strategy', 'indicators', 'execution'],
                              help='Type of configuration to create')
    create_parser.add_argument('--output', type=str, required=True, 
                              help='Output path for the configuration file')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate a configuration file')
    validate_parser.add_argument('--config', type=str, required=True, 
                                help='Path to the configuration file to validate')
    validate_parser.add_argument('--type', type=str, required=True, 
                                choices=['general', 'strategy', 'indicators', 'execution'],
                                help='Type of configuration to validate')
    
    # Merge command
    merge_parser = subparsers.add_parser('merge', help='Merge multiple configuration files')
    merge_parser.add_argument('--configs', type=str, nargs='+', required=True, 
                             help='Paths to configuration files to merge')
    merge_parser.add_argument('--output', type=str, required=True, 
                             help='Output path for the merged configuration file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    manager = ConfigManager()
    
    if args.command == 'create':
        success = manager.create_config(args)
    elif args.command == 'validate':
        success = manager.validate_config_file(args)
    elif args.command == 'merge':
        success = manager.merge_configs(args)
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())