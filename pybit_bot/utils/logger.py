"""
Unified logging system for PyBit Bot
Provides consistent logging across all components with deduplication and data truncation
"""

import os
import sys
import time
import logging
import datetime
from typing import Any, Dict, List, Optional, Union


class Logger:
    """
    Unified logging system for PyBit Bot
    
    Features:
    - Configurable log level
    - Console and file output
    - Deduplication of repeated messages
    - Truncation of large data structures
    - CSV log output for important events
    """
    
    def __init__(self, name: str, level: int = logging.INFO, console: bool = True, 
                 file: Optional[str] = None, csv_file: Optional[str] = None):
        """
        Initialize logger
        
        Args:
            name: Logger name
            level: Logging level (default: INFO)
            console: Whether to output to console (default: True)
            file: Optional file path for log output
            csv_file: Optional CSV file path for structured event logging
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.last_message = None
        self.last_message_time = 0
        self.duplicate_count = 0
        self.csv_file = csv_file
        
        # Clear any existing handlers to prevent duplicate output
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Add console handler if requested
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(console_handler)
        
        # Add file handler if requested
        if file:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(file)), exist_ok=True)
            
            file_handler = logging.FileHandler(file)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(file_handler)
        
        # Initialize CSV log if requested
        if csv_file:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(csv_file)), exist_ok=True)
            
            # Create CSV file with headers if it doesn't exist
            if not os.path.exists(csv_file):
                with open(csv_file, 'w') as f:
                    f.write("timestamp,level,component,message,data\n")
    
    def _log(self, level: int, message: str, *args, **kwargs):
        """
        Internal logging method with deduplication
        
        Args:
            level: Log level
            message: Log message
            *args: Format arguments
            **kwargs: Additional parameters
        """
        # Format message with args if any
        if args:
            formatted_message = message % args
        else:
            formatted_message = message
            
        # Check for duplicate message
        current_time = time.time()
        if formatted_message == self.last_message:
            # If duplicate message within 1 second, increment counter instead of logging
            if current_time - self.last_message_time < 1:
                self.duplicate_count += 1
                return
            elif self.duplicate_count > 0:
                # Log count of suppressed duplicates
                self.logger.log(level, f"Previous message repeated {self.duplicate_count} times")
                self.duplicate_count = 0
        else:
            # Log count of suppressed duplicates from previous message if any
            if self.duplicate_count > 0:
                self.logger.log(level, f"Previous message repeated {self.duplicate_count} times")
                self.duplicate_count = 0
            
        # Update tracking variables
        self.last_message = formatted_message
        self.last_message_time = current_time
        
        # Actually log the message
        self.logger.log(level, formatted_message, **kwargs)
        
        # Write to CSV if enabled and level is high enough
        if self.csv_file and level >= logging.INFO:
            data = kwargs.get('data', '')
            if data and not isinstance(data, str):
                try:
                    import json
                    data = json.dumps(self.truncate_data(data))
                except:
                    data = str(data)
                    
            # Escape commas and quotes for CSV
            safe_message = formatted_message.replace('"', '""')
            safe_data = str(data).replace('"', '""') if data else ''
            
            try:
                with open(self.csv_file, 'a') as f:
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                    level_name = logging.getLevelName(level)
                    f.write(f'"{timestamp}","{level_name}","{self.name}","{safe_message}","{safe_data}"\n')
            except Exception as e:
                # Log to normal logger but don't recurse
                self.logger.error(f"Failed to write to CSV log: {str(e)}")
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message"""
        self._log(logging.DEBUG, message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message"""
        self._log(logging.INFO, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message"""
        self._log(logging.WARNING, message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message"""
        self._log(logging.ERROR, message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message"""
        self._log(logging.CRITICAL, message, *args, **kwargs)
    
    def log_event(self, event_type: str, data: Any = None):
        """
        Log a structured event with optional data
        
        Args:
            event_type: Type of event (e.g., 'trade', 'order', 'position')
            data: Data associated with the event
        """
        self.info(f"EVENT:{event_type}", data=data)
    
    def log_trade(self, symbol: str, side: str, price: float, quantity: float, order_id: str = None):
        """
        Log a trade event
        
        Args:
            symbol: Trading symbol
            side: Trade side (Buy/Sell)
            price: Execution price
            quantity: Trade quantity
            order_id: Optional order ID
        """
        data = {
            "symbol": symbol,
            "side": side,
            "price": price,
            "quantity": quantity,
            "order_id": order_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.log_event("TRADE", data)
    
    def log_order(self, order_type: str, symbol: str, side: str, status: str, data: Dict = None):
        """
        Log an order event
        
        Args:
            order_type: Type of order (market, limit, etc.)
            symbol: Trading symbol
            side: Order side (Buy/Sell)
            status: Order status (created, filled, cancelled, etc.)
            data: Additional order data
        """
        event_data = {
            "type": order_type,
            "symbol": symbol,
            "side": side,
            "status": status,
            "timestamp": datetime.datetime.now().isoformat()
        }
        if data:
            event_data.update(data)
        self.log_event("ORDER", event_data)
    
    def log_error(self, error_type: str, message: str, traceback: str = None):
        """
        Log an error event
        
        Args:
            error_type: Type of error
            message: Error message
            traceback: Optional traceback
        """
        data = {
            "type": error_type,
            "message": message,
            "traceback": traceback,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.error(f"ERROR:{error_type} - {message}")
        self.log_event("ERROR", data)
    
    @staticmethod
    def truncate_data(data: Any, max_items: int = 5, max_length: int = 100) -> Any:
        """
        Truncate large data structures for logging
        
        Args:
            data: Data to truncate
            max_items: Maximum number of items to include in lists/dicts
            max_length: Maximum string length
            
        Returns:
            Truncated data
        """
        if isinstance(data, dict):
            if len(data) > max_items:
                truncated = {k: Logger.truncate_data(v, max_items, max_length) 
                             for k, v in list(data.items())[:max_items]}
                truncated['...'] = f"[{len(data) - max_items} more items]"
                return truncated
            return {k: Logger.truncate_data(v, max_items, max_length) for k, v in data.items()}
        elif isinstance(data, list):
            if len(data) > max_items:
                return [Logger.truncate_data(item, max_items, max_length) 
                        for item in data[:max_items]] + [f"[{len(data) - max_items} more items]"]
            return [Logger.truncate_data(item, max_items, max_length) for item in data]
        elif isinstance(data, str) and len(data) > max_length:
            return data[:max_length] + f"... [{len(data) - max_length} more chars]"
        return data


# Singleton pattern to ensure we reuse logger instances
_loggers = {}

def get_logger(name: str, level: int = logging.INFO, console: bool = True, 
               file: Optional[str] = None, csv_file: Optional[str] = None) -> Logger:
    """
    Get a logger instance (singleton pattern)
    
    Args:
        name: Logger name
        level: Logging level
        console: Whether to output to console
        file: Optional file path for log output
        csv_file: Optional CSV file path for structured event logging
        
    Returns:
        Logger instance
    """
    global _loggers
    
    if name not in _loggers:
        _loggers[name] = Logger(name, level, console, file, csv_file)
    
    return _loggers[name]