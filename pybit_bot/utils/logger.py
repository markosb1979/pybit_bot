"""
Logger utility module for PyBit Bot.

Provides consistent logging across the application with formatting
and level control.
"""

import os
import logging
import logging.handlers
from datetime import datetime


class Logger:
    """
    Logger class to manage consistent logging
    """
    
    def __init__(self, name: str, level: str = "DEBUG"):
        """
        Initialize logger with name and level
        
        Args:
            name: Logger name
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.name = name
        
        # Create logger
        self.logger = logging.getLogger(name)
        
        # Set level
        level_value = getattr(logging, level, logging.DEBUG)
        self.logger.setLevel(level_value)
        
        # Only add handlers if not already configured
        if not self.logger.handlers:
            self._configure_logger()
    
    def _configure_logger(self):
        """Configure logger with console and file handlers"""
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        self.logger.addHandler(console)
        
        # File handler
        try:
            log_dir = 'logs'
            os.makedirs(log_dir, exist_ok=True)
            
            # Daily rotating file handler
            today = datetime.now().strftime('%Y-%m-%d')
            file_handler = logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, f'pybit_bot_{today}.log'),
                maxBytes=10*1024*1024,  # 10 MB
                backupCount=5
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            self.logger.error(f"Failed to setup file logging: {str(e)}")
    
    def debug(self, message: str):
        """
        Log debug message
        
        Args:
            message: Message to log
        """
        self.logger.debug(message)
    
    def info(self, message: str):
        """
        Log info message
        
        Args:
            message: Message to log
        """
        self.logger.info(message)
    
    def warning(self, message: str):
        """
        Log warning message
        
        Args:
            message: Message to log
        """
        self.logger.warning(message)
    
    def error(self, message: str):
        """
        Log error message
        
        Args:
            message: Message to log
        """
        self.logger.error(message)
    
    def critical(self, message: str):
        """
        Log critical message
        
        Args:
            message: Message to log
        """
        self.logger.critical(message)