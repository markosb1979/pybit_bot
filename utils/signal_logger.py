"""
Signal logger utility for recording trade signals and outcomes.
Records signals to CSV for later analysis and visualization.
"""

import os
import csv
import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from strategies.base_strategy import TradeSignal, SignalType


class SignalLogger:
    """
    Utility class for logging trade signals and outcomes.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize the signal logger.
        
        Args:
            log_dir: Directory for log files
        """
        self.log_dir = log_dir
        self.logger = logging.getLogger(__name__)
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Create signal log file
        self.signal_log_file = os.path.join(log_dir, f"signals_{datetime.now().strftime('%Y%m%d')}.csv")
        self.trade_log_file = os.path.join(log_dir, f"trades_{datetime.now().strftime('%Y%m%d')}.csv")
        
        # Initialize log files if they don't exist
        self._init_signal_log()
        self._init_trade_log()
    
    def _init_signal_log(self) -> None:
        """
        Initialize the signal log file with headers if it doesn't exist.
        """
        if not os.path.exists(self.signal_log_file):
            with open(self.signal_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'strategy', 'signal_type', 'price', 
                    'order_type', 'sl_price', 'tp_price', 'indicator_values'
                ])
    
    def _init_trade_log(self) -> None:
        """
        Initialize the trade log file with headers if it doesn't exist.
        """
        if not os.path.exists(self.trade_log_file):
            with open(self.trade_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'entry_time', 'exit_time', 'symbol', 'strategy', 'side', 
                    'entry_price', 'exit_price', 'quantity', 'pnl', 'exit_reason'
                ])
    
    def log_signal(self, signal: TradeSignal, strategy_name: str) -> None:
        """
        Log a trade signal to CSV.
        
        Args:
            signal: TradeSignal object
            strategy_name: Name of the strategy that generated the signal
        """
        try:
            with open(self.signal_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.fromtimestamp(signal.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    signal.symbol,
                    strategy_name,
                    signal.signal_type.value,
                    signal.price,
                    signal.order_type.value,
                    signal.sl_price,
                    signal.tp_price,
                    str(signal.indicator_values)
                ])
            
            self.logger.debug(f"Logged signal: {signal.signal_type.value} for {signal.symbol} at {signal.price}")
        
        except Exception as e:
            self.logger.error(f"Error logging signal: {str(e)}")
    
    def log_trade(
        self,
        entry_time: int,
        exit_time: int,
        symbol: str,
        strategy_name: str,
        side: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        pnl: float,
        exit_reason: str
    ) -> None:
        """
        Log a completed trade to CSV.
        
        Args:
            entry_time: Entry timestamp (ms)
            exit_time: Exit timestamp (ms)
            symbol: Trading symbol
            strategy_name: Strategy name
            side: Trade side ('Buy' or 'Sell')
            entry_price: Entry price
            exit_price: Exit price
            quantity: Trade quantity
            pnl: Profit/loss
            exit_reason: Reason for exit (TP, SL, manual, etc.)
        """
        try:
            with open(self.trade_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.fromtimestamp(entry_time / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    datetime.fromtimestamp(exit_time / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    symbol,
                    strategy_name,
                    side,
                    entry_price,
                    exit_price,
                    quantity,
                    pnl,
                    exit_reason
                ])
            
            self.logger.info(f"Logged trade: {side} {symbol} - PnL: {pnl}")
        
        except Exception as e:
            self.logger.error(f"Error logging trade: {str(e)}")
    
    def get_signals_as_dataframe(self) -> pd.DataFrame:
        """
        Get all logged signals as a pandas DataFrame.
        
        Returns:
            DataFrame of signals
        """
        try:
            if os.path.exists(self.signal_log_file):
                return pd.read_csv(self.signal_log_file)
            else:
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error reading signal log: {str(e)}")
            return pd.DataFrame()
    
    def get_trades_as_dataframe(self) -> pd.DataFrame:
        """
        Get all logged trades as a pandas DataFrame.
        
        Returns:
            DataFrame of trades
        """
        try:
            if os.path.exists(self.trade_log_file):
                return pd.read_csv(self.trade_log_file)
            else:
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error reading trade log: {str(e)}")
            return pd.DataFrame()