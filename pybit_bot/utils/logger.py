"""
Logging functionality for PyBit Bot
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, TextIO


class Logger:
    """
    Custom logger with file and console output
    """
    
    LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    def __init__(
        self,
        name: str,
        level: str = "INFO",
        log_to_file: bool = True,
        log_dir: Optional[Union[str, Path]] = None
    ):
        self.name = name
        self.logger = logging.getLogger(name)
        
        # Set level
        self.set_level(level)
        
        # Avoid duplicate handlers
        if self.logger.handlers:
            return
            
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (optional)
        if log_to_file:
            log_dir = Path(log_dir) if log_dir else Path("logs")
            log_dir.mkdir(exist_ok=True, parents=True)
            
            timestamp = datetime.now().strftime("%Y%m%d")
            log_file = log_dir / f"{name}_{timestamp}.log"
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def set_level(self, level: str):
        """Set the logging level"""
        log_level = self.LEVEL_MAP.get(level.upper(), logging.INFO)
        self.logger.setLevel(log_level)
    
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