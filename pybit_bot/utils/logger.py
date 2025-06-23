"""
Logger utility for consistent logging across the application
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional


class Logger:
    """
    Unified logger for the application.
    Provides consistent formatting and log level control.
    """
    
    def __init__(self, name: str, level: int = logging.DEBUG):
        """
        Initialize logger with name and level
        
        Args:
            name: Name of the logger
            level: Logging level (default: DEBUG)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            
            # Formatter
            formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s', 
                                          datefmt='%Y-%m-%d %H:%M:%S')
            console_handler.setFormatter(formatter)
            
            # Add handler
            self.logger.addHandler(console_handler)
            
            # Create log directory if it doesn't exist
            log_dir = os.path.join(os.getcwd(), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # File handler (optional)
            try:
                log_file = os.path.join(log_dir, f'{datetime.now().strftime("%Y%m%d")}-pybit-bot.log')
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(level)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                self.logger.warning(f"Could not create file handler: {str(e)}")
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
        
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
        
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
        
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
        
    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)


# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,  # Set default level to DEBUG
    format='%(asctime)s,%(msecs)d [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)