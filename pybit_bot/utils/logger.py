"""
Comprehensive logging system with CSV output support
Windows-compatible version
"""

import logging
import csv
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class Logger:
    """
    Enhanced logger with CSV output for trade tracking
    Windows-compatible with proper encoding
    """
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup standard logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
            
        # CSV loggers for different data types
        self.trade_csv = self._setup_csv_logger("trades")
        self.order_csv = self._setup_csv_logger("orders") 
        self.position_csv = self._setup_csv_logger("positions")
        self.signal_csv = self._setup_csv_logger("signals")
        
    def _setup_handlers(self):
        """Setup file and console handlers with proper encoding"""
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # File handler with UTF-8 encoding
        file_handler = logging.FileHandler(
            self.log_dir / f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Console handler with proper encoding for Windows
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Set console encoding to UTF-8 if possible
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except:
                pass  # Fall back to default encoding
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
    def _setup_csv_logger(self, log_type: str) -> str:
        """Setup CSV file for structured data logging"""
        csv_file = self.log_dir / f"{log_type}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        # Create headers if file doesn't exist
        if not csv_file.exists():
            headers = self._get_csv_headers(log_type)
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                
        return str(csv_file)
    
    def _get_csv_headers(self, log_type: str) -> list:
        """Get CSV headers for different log types"""
        headers_map = {
            "trades": [
                "timestamp", "symbol", "side", "quantity", "price", 
                "order_id", "trade_id", "commission", "pnl", "strategy"
            ],
            "orders": [
                "timestamp", "symbol", "side", "order_type", "quantity", 
                "price", "order_id", "order_link_id", "status", "strategy"
            ],
            "positions": [
                "timestamp", "symbol", "side", "size", "entry_price", 
                "mark_price", "unrealized_pnl", "realized_pnl", "margin"
            ],
            "signals": [
                "timestamp", "symbol", "signal_type", "direction", "strength",
                "indicator_values", "strategy", "action_taken"
            ]
        }
        return headers_map.get(log_type, [])
    
    def _safe_log(self, level: str, message: str):
        """Safely log message with fallback for encoding issues"""
        try:
            # Try to log with Unicode characters
            getattr(self.logger, level.lower())(message)
        except UnicodeEncodeError:
            # Fallback: replace Unicode characters with ASCII equivalents
            safe_message = (message
                           .replace('✅', '[PASS]')
                           .replace('❌', '[FAIL]')
                           .replace('⚠️', '[WARN]')
                           .replace('🎉', '[SUCCESS]')
                           .replace('🔒', '[SECURE]'))
            getattr(self.logger, level.lower())(safe_message)
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """Log trade execution to CSV"""
        self._log_to_csv(self.trade_csv, trade_data)
        self._safe_log('info', f"Trade executed: {trade_data}")
        
    def log_order(self, order_data: Dict[str, Any]):
        """Log order to CSV"""
        self._log_to_csv(self.order_csv, order_data)
        self._safe_log('info', f"Order logged: {order_data}")
        
    def log_position(self, position_data: Dict[str, Any]):
        """Log position update to CSV"""
        self._log_to_csv(self.position_csv, position_data)
        
    def log_signal(self, signal_data: Dict[str, Any]):
        """Log trading signal to CSV"""
        self._log_to_csv(self.signal_csv, signal_data)
        self._safe_log('info', f"Signal generated: {signal_data}")
        
    def _log_to_csv(self, csv_file: str, data: Dict[str, Any]):
        """Write data to CSV file"""
        try:
            data_with_timestamp = {
                "timestamp": datetime.utcnow().isoformat(),
                **data
            }
            
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                # Get existing headers
                f.seek(0)
                reader = csv.reader(f)
                headers = next(reader, [])
                
                f.seek(0, 2)  # Go to end of file
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writerow(data_with_timestamp)
                
        except Exception as e:
            self._safe_log('error', f"Failed to write to CSV: {str(e)}")
    
    # Standard logging methods with safe Unicode handling
    def debug(self, message: str):
        self._safe_log('debug', message)
        
    def info(self, message: str):
        self._safe_log('info', message)
        
    def warning(self, message: str):
        self._safe_log('warning', message)
        
    def error(self, message: str):
        self._safe_log('error', message)
        
    def critical(self, message: str):
        self._safe_log('critical', message)