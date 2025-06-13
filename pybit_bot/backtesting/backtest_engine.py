"""
Backtesting engine for strategy evaluation.
Simulates strategy execution on historical data.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
import time
import json
import os

from pybit_bot.backtesting.data_loader import DataLoader
from pybit_bot.backtesting.position_simulator import PositionSimulator, OrderType, ExitReason
from pybit_bot.strategies.base_strategy import BaseStrategy, TradeSignal, SignalType


class BacktestEngine:
    """
    Engine for backtesting trading strategies.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the backtesting engine.
        
        Args:
            config_path: Path to configuration file
        """
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.data_loader = DataLoader()
        self.position_simulator = PositionSimulator(
            initial_balance=self.config.get('initial_balance', 10000.0),
            maker_fee=self.config.get('maker_fee', 0.0002),
            taker_fee=self.config.get('taker_fee', 0.0005)
        )
        
        # Test data
        self.data: Dict[str, Dict[str, pd.DataFrame]] = {}  # symbol -> timeframe -> DataFrame
        
        # Strategies
        self.strategies: Dict[str, BaseStrategy] = {}
        
        # Results
        self.results = {
            'trades': [],
            'equity_curve': [],
            'performance_metrics': {}
        }
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
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
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")
            raise
    
    def load_data(self, 
                 data_sources: Dict[str, str], 
                 symbols: List[str], 
                 timeframes: List[str],
                 start_time: Optional[datetime] = None,
                 end_time: Optional[datetime] = None) -> bool:
        """
        Load historical data for backtesting.
        
        Args:
            data_sources: Dictionary mapping symbols to data source paths
            symbols: List of symbols to