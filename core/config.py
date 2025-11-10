"""
Configuration management
"""

import os
from typing import Optional, Tuple, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration"""
    
    # Schwab API Configuration
    SCHWAB_CLIENT_ID: str = os.getenv("SCHWAB_CLIENT_ID", "")
    SCHWAB_CLIENT_SECRET: str = os.getenv("SCHWAB_CLIENT_SECRET", "")
    SCHWAB_REDIRECT_URI: str = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:5035")
    SCHWAB_ACCOUNT_ID: Optional[str] = os.getenv("SCHWAB_ACCOUNT_ID")
    
    # OpenAI Configuration (optional)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # Trading Configuration
    SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    ENABLE_LIVE_TRADING: bool = os.getenv("ENABLE_LIVE_TRADING", "false").lower() == "true"
    MAX_LOSS_PER_TRADE: float = float(os.getenv("MAX_LOSS_PER_TRADE", "300"))
    MAX_POSITION_SIZE: float = float(os.getenv("MAX_POSITION_SIZE", "1000"))
    RISK_PERCENTAGE: float = float(os.getenv("RISK_PERCENTAGE", "0.02"))
    
    # FastAPI Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "./logs/trading_bot.log")
    
    # Database Configuration
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/trading_bot.db")
    
    @classmethod
    def validate_schwab_config(cls) -> Tuple[bool, List[str]]:
        """
        Validate Schwab API configuration
        
        Returns:
            Tuple of (is_valid, list_of_missing_fields)
        """
        missing = []
        
        if not cls.SCHWAB_CLIENT_ID:
            missing.append("SCHWAB_CLIENT_ID")
        if not cls.SCHWAB_CLIENT_SECRET:
            missing.append("SCHWAB_CLIENT_SECRET")
        if not cls.SCHWAB_REDIRECT_URI:
            missing.append("SCHWAB_REDIRECT_URI")
        
        return len(missing) == 0, missing
