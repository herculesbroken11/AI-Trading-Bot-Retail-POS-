"""
AI Trading Bot Main Entry Point
"""

import asyncio
import sys
import os
from typing import List

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import config
from core.logger import logger
from core.trading_engine import trading_engine

async def main():
    """Main entry point for the AI Trading Bot"""
    try:
        logger.info("=== AI Trading Bot Starting ===")
        
        # Validate configuration
        if not config.validate_config():
            missing_config = config.get_missing_config()
            logger.error(f"Missing required configuration: {missing_config}")
            print(f"Missing required configuration: {missing_config}")
            print("Please check your .env file and ensure all required fields are set.")
            return False
        
        # Custom watchlist (you can modify this)
        watchlist = [
            "SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA",
            "META", "NFLX", "AMD", "INTC", "CRM", "ADBE", "PYPL", "UBER",
            "SQ", "ROKU", "ZM", "PTON", "DOCU", "SNOW", "PLTR", "CRWD"
        ]
        
        # Start the trading engine
        success = await trading_engine.start(watchlist)
        
        if success:
            logger.info("Trading engine started successfully")
            
            # Keep the main thread alive
            try:
                while trading_engine.is_running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
            finally:
                await trading_engine.stop()
        else:
            logger.error("Failed to start trading engine")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        return False

if __name__ == "__main__":
    # Run the main function
    try:
        result = asyncio.run(main())
        if result:
            print("Trading bot completed successfully")
        else:
            print("Trading bot failed to start")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nTrading bot interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)
