"""
PyBit Bot - Trading Bot Core
----------------------------
High-level trading bot interface that simplifies interaction with the underlying
trading engine. Provides a clean facade for managing the trading system.
"""

import os
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

# Internal imports
from ..exceptions import ConfigError, TradingBotError
from ..utils.logger import Logger
from .client import BybitClient, APICredentials
from .order_manager import OrderManager
from ..engine import TradingEngine

class TradingBot:
    """
    High-level trading bot that provides a simplified interface to the
    underlying trading engine and components.
    """
    
    def __init__(
        self, 
        config_path: str = None,
        api_key: str = None,
        api_secret: str = None,
        testnet: bool = None,
        symbol: str = None,
        strategy: str = None,
        logger: Optional[Logger] = None
    ):
        """
        Initialize the trading bot with flexible configuration options.
        
        Args:
            config_path: Path to JSON configuration file
            api_key: Bybit API key (overrides config)
            api_secret: Bybit API secret (overrides config)
            testnet: Whether to use testnet (overrides config)
            symbol: Trading symbol (overrides config)
            strategy: Strategy name (overrides config)
            logger: Optional custom logger
        """
        self.logger = logger or Logger("TradingBot")
        self.logger.info("Initializing PyBit Trading Bot")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Apply overrides
        self._apply_overrides(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            symbol=symbol,
            strategy=strategy
        )
        
        # Initialize state
        self.engine = None
        self.client = None
        self.order_manager = None
        self.running = False
        self.start_time = None
        
        # Log configuration (without sensitive data)
        safe_config = self._get_safe_config()
        self.logger.info(f"Configuration loaded: {json.dumps(safe_config)}")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load and validate configuration from file"""
        # Default config
        default_config = {
            "trading": {
                "symbol": "BTCUSDT",
                "position_size_usdt": 100.0,
                "max_positions": 1,
                "timeframe": "15m"
            },
            "risk": {
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.03,
                "max_daily_loss_usdt": 100.0
            },
            "system": {
                "log_level": "INFO",
                "data_dir": "data"
            }
        }
        
        # No config path, use default
        if not config_path:
            self.logger.warning("No config provided, using default configuration")
            return default_config
        
        # Load from file
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Validate required sections
            required_sections = ["trading", "risk", "system"]
            for section in required_sections:
                if section not in config:
                    self.logger.warning(f"Missing {section} section in config, using default")
                    config[section] = default_config[section]
            
            return config
        
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading config: {str(e)}")
            self.logger.warning("Falling back to default configuration")
            return default_config
    
    def _apply_overrides(self, **kwargs):
        """Apply configuration overrides from constructor arguments"""
        # API credentials
        if kwargs.get('api_key') and kwargs.get('api_secret'):
            self.config['api'] = self.config.get('api', {})
            self.config['api']['key'] = kwargs['api_key']
            self.config['api']['secret'] = kwargs['api_secret']
        
        # Testnet setting
        if kwargs.get('testnet') is not None:
            self.config['api'] = self.config.get('api', {})
            self.config['api']['testnet'] = kwargs['testnet']
        
        # Symbol
        if kwargs.get('symbol'):
            self.config['trading']['symbol'] = kwargs['symbol']
        
        # Strategy
        if kwargs.get('strategy'):
            self.config['trading']['strategy'] = kwargs['strategy']
    
    def _get_safe_config(self) -> Dict[str, Any]:
        """Get a copy of config with sensitive data removed"""
        if not hasattr(self, 'config'):
            return {}
            
        safe_config = json.loads(json.dumps(self.config))
        if 'api' in safe_config:
            if 'key' in safe_config['api']:
                key = safe_config['api']['key']
                safe_config['api']['key'] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"
            if 'secret' in safe_config['api']:
                safe_config['api']['secret'] = "********"
        
        return safe_config
    
    def start(self) -> bool:
        """
        Start the trading bot with current configuration.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            self.logger.warning("Trading bot is already running")
            return True
        
        try:
            self.logger.info("Starting trading bot")
            
            # Check for API credentials
            if 'api' not in self.config or 'key' not in self.config['api'] or 'secret' not in self.config['api']:
                raise TradingBotError("API credentials not configured")
            
            # Initialize engine if not already done
            if not self.engine:
                self.engine = TradingEngine(self.config)
            
            # Start the engine
            result = self.engine.start()
            
            if result:
                self.running = True
                self.start_time = datetime.now()
                self.logger.info("Trading bot started successfully")
            else:
                self.logger.error("Failed to start trading engine")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error starting trading bot: {str(e)}")
            self.running = False
            return False
    
    def stop(self) -> bool:
        """
        Stop the trading bot.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.running:
            self.logger.warning("Trading bot is not running")
            return True
        
        try:
            self.logger.info("Stopping trading bot")
            
            if self.engine:
                self.engine.stop()
                
            self.running = False
            self.logger.info("Trading bot stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping trading bot: {str(e)}")
            # Force running state to False even on error
            self.running = False
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current trading bot status
        
        Returns:
            Dict containing current status information
        """
        status = {
            "running": self.running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime": str(datetime.now() - self.start_time) if self.start_time else "00:00:00",
            "symbol": self.config.get('trading', {}).get('symbol', 'UNKNOWN'),
            "testnet": self.config.get('api', {}).get('testnet', True)
        }
        
        # Add engine status if available
        if self.engine:
            engine_status = self.engine.get_status()
            status.update(engine_status)
        
        return status
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions
        
        Returns:
            List of position dictionaries
        """
        if not self.running or not self.engine:
            return []
            
        try:
            return self.engine.get_positions()
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            return []
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Get open orders
        
        Returns:
            List of order dictionaries
        """
        if not self.running or not self.engine:
            return []
            
        try:
            return self.engine.get_orders()
        except Exception as e:
            self.logger.error(f"Error getting orders: {str(e)}")
            return []
    
    def get_performance(self) -> Dict[str, Any]:
        """
        Get trading performance metrics
        
        Returns:
            Dict with performance metrics
        """
        if not self.running or not self.engine:
            return {
                "trades": 0,
                "win_rate": 0.0,
                "profit_loss": 0.0,
                "uptime": "00:00:00"
            }
            
        try:
            return self.engine.get_performance()
        except Exception as e:
            self.logger.error(f"Error getting performance: {str(e)}")
            return {
                "trades": 0,
                "win_rate": 0.0,
                "profit_loss": 0.0,
                "uptime": "00:00:00"
            }
    
    def update_risk_parameters(
        self,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        max_daily_loss_usdt: Optional[float] = None
    ) -> bool:
        """
        Update risk parameters while bot is running
        
        Args:
            stop_loss_pct: New stop loss percentage (0-1)
            take_profit_pct: New take profit percentage (0-1)
            max_daily_loss_usdt: New maximum daily loss in USDT
            
        Returns:
            bool: True if updated successfully
        """
        if not self.config.get('risk'):
            self.config['risk'] = {}
            
        if stop_loss_pct is not None:
            self.config['risk']['stop_loss_pct'] = float(stop_loss_pct)
            
        if take_profit_pct is not None:
            self.config['risk']['take_profit_pct'] = float(take_profit_pct)
            
        if max_daily_loss_usdt is not None:
            self.config['risk']['max_daily_loss_usdt'] = float(max_daily_loss_usdt)
        
        # Update engine if running
        if self.running and self.engine:
            try:
                self.engine.update_config(self.config)
                self.logger.info("Risk parameters updated successfully")
                return True
            except Exception as e:
                self.logger.error(f"Error updating risk parameters: {str(e)}")
                return False
        
        self.logger.info("Risk parameters updated (will apply on next start)")
        return True
    
    def update_position_size(self, position_size_usdt: float) -> bool:
        """
        Update position size while bot is running
        
        Args:
            position_size_usdt: New position size in USDT
            
        Returns:
            bool: True if updated successfully
        """
        if not self.config.get('trading'):
            self.config['trading'] = {}
        
        self.config['trading']['position_size_usdt'] = float(position_size_usdt)
        
        # Update engine if running
        if self.running and self.engine:
            try:
                self.engine.update_config(self.config)
                self.logger.info(f"Position size updated to {position_size_usdt} USDT")
                return True
            except Exception as e:
                self.logger.error(f"Error updating position size: {str(e)}")
                return False
        
        self.logger.info(f"Position size updated to {position_size_usdt} USDT (will apply on next start)")
        return True
    
    def save_config(self, path: str) -> bool:
        """
        Save current configuration to file
        
        Args:
            path: Path to save configuration file
            
        Returns:
            bool: True if saved successfully
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            # Save config
            with open(path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            self.logger.info(f"Configuration saved to {path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def __str__(self) -> str:
        """String representation of trading bot"""
        status = "RUNNING" if self.running else "STOPPED"
        symbol = self.config.get('trading', {}).get('symbol', 'UNKNOWN')
        testnet = "TESTNET" if self.config.get('api', {}).get('testnet', True) else "MAINNET"
        
        return f"PyBit Trading Bot [{status}] - {symbol} on {testnet}"