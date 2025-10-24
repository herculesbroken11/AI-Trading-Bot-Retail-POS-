"""
Configuration management for the AI Trading Bot
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TradingConfig:
    """Configuration class for trading bot settings"""
    
    # Charles Schwab API
    SCHWAB_CLIENT_ID: str = os.getenv("SCHWAB_CLIENT_ID", "")
    SCHWAB_CLIENT_SECRET: str = os.getenv("SCHWAB_CLIENT_SECRET", "")
    SCHWAB_REDIRECT_URI: str = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8080")
    SCHWAB_ACCOUNT_ID: str = os.getenv("SCHWAB_ACCOUNT_ID", "")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # Tastytrade API (Optional)
    TASTYTRADE_USERNAME: Optional[str] = os.getenv("TASTYTRADE_USERNAME")
    TASTYTRADE_PASSWORD: Optional[str] = os.getenv("TASTYTRADE_PASSWORD")
    
    # Trading Parameters
    MAX_LOSS_PER_TRADE: float = float(os.getenv("MAX_LOSS_PER_TRADE", "300"))
    MAX_POSITION_SIZE: float = float(os.getenv("MAX_POSITION_SIZE", "1000"))
    RISK_PERCENTAGE: float = float(os.getenv("RISK_PERCENTAGE", "0.02"))
    
    # FastAPI Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "./logs/trading_bot.log")
    
    # Database Configuration
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/trading_bot.db")
    
    # Market Data Configuration
    MARKET_DATA_REFRESH_INTERVAL: int = int(os.getenv("MARKET_DATA_REFRESH_INTERVAL", "1"))
    WEBSOCKET_ENABLED: bool = os.getenv("WEBSOCKET_ENABLED", "True").lower() == "true"
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate that all required configuration is present"""
        required_fields = [
            cls.SCHWAB_CLIENT_ID,
            cls.OPENAI_API_KEY,
        ]
        
        return all(field for field in required_fields)
    
    @classmethod
    def get_missing_config(cls) -> list:
        """Get list of missing configuration fields"""
        missing = []
        
        if not cls.SCHWAB_CLIENT_ID:
            missing.append("SCHWAB_CLIENT_ID")
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not cls.SCHWAB_ACCOUNT_ID:
            missing.append("SCHWAB_ACCOUNT_ID")
            
        return missing

# Global configuration instance
config = TradingConfig()
