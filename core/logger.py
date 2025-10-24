"""
Logging configuration for the AI Trading Bot
"""

import logging
import os
from datetime import datetime
from typing import Optional
from core.config import config

class TradingLogger:
    """Custom logger for trading bot operations"""
    
    def __init__(self, name: str = "trading_bot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)
        
        # File handler
        file_handler = logging.FileHandler(config.LOG_FILE_PATH)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers if not already added
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)
    
    def log_trade(self, trade_data: dict):
        """Log trade execution details"""
        self.info(f"Trade Executed: {trade_data}")
    
    def log_signal(self, signal_data: dict):
        """Log trading signal details"""
        self.info(f"Trading Signal: {signal_data}")
    
    def log_ai_analysis(self, analysis_data: dict):
        """Log AI analysis results"""
        self.info(f"AI Analysis: {analysis_data}")

# Global logger instance
logger = TradingLogger()
