"""
Charles Schwab API Wrapper
Handles market data retrieval and trade execution using Schwab API
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
from schwab.auth import client_from_login_flow, client_from_token_file
from schwab.client import Client
from core.config import config
from core.logger import logger

class SchwabAPI:
    """Charles Schwab API wrapper for trading operations"""
    
    def __init__(self):
        self.client_id = config.SCHWAB_CLIENT_ID
        self.client_secret = config.SCHWAB_CLIENT_SECRET
        self.redirect_uri = config.SCHWAB_REDIRECT_URI
        self.account_id = config.SCHWAB_ACCOUNT_ID
        self.client = None
        self.token_file_path = "./data/schwab_tokens.json"
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.authenticate()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.close()
    
    async def authenticate(self) -> bool:
        """
        Authenticate with Charles Schwab API
        """
        try:
            # Try to load existing tokens
            try:
                self.client = client_from_token_file(
                    self.token_file_path,
                    self.client_id,
                    self.client_secret
                )
                logger.info("Successfully authenticated with existing Schwab tokens")
                return True
            except Exception as e:
                logger.info(f"No existing tokens found, need to authenticate: {str(e)}")
            
            # If no existing tokens, start authentication flow
            logger.info("Starting Schwab authentication flow...")
            print("Please complete the authentication process in your browser...")
            
            # This will open a browser window for authentication
            # Note: This needs to be run in a separate thread to avoid asyncio conflicts
            import threading
            import time
            
            def auth_flow():
                try:
                    self.client = client_from_login_flow(
                        self.client_id,
                        self.client_secret,
                        self.redirect_uri,
                        self.token_file_path
                    )
                    self.auth_success = True
                except Exception as e:
                    logger.error(f"Authentication flow failed: {str(e)}")
                    self.auth_success = False
            
            self.auth_success = None
            auth_thread = threading.Thread(target=auth_flow)
            auth_thread.start()
            
            # Wait for authentication to complete (with timeout)
            timeout = 300  # 5 minutes
            start_time = time.time()
            while self.auth_success is None and (time.time() - start_time) < timeout:
                time.sleep(1)
            
            if self.auth_success is None:
                logger.error("Authentication timed out")
                return False
            elif not self.auth_success:
                logger.error("Authentication failed")
                return False
            
            logger.info("Successfully authenticated with Charles Schwab API")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False
    
    async def get_market_data(self, symbol: str, period_type: str = "day", 
                            period: int = 1, frequency_type: str = "minute", 
                            frequency: int = 1) -> Optional[pd.DataFrame]:
        """
        Get market data for a symbol using Schwab API
        
        Args:
            symbol: Stock symbol
            period_type: day, month, year, ytd
            period: Number of periods
            frequency_type: minute, daily, weekly, monthly
            frequency: Frequency value
        """
        try:
            if not self.client:
                logger.error("Client not authenticated")
                return None
            
            # Get price history from Schwab API
            price_history = self.client.get_price_history(
                symbol=symbol,
                period_type=period_type,
                period=period,
                frequency_type=frequency_type,
                frequency=frequency
            )
            
            if price_history and 'candles' in price_history:
                df = pd.DataFrame(price_history['candles'])
                df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                df.set_index('datetime', inplace=True)
                logger.info(f"Retrieved market data for {symbol}")
                return df
            else:
                logger.warning(f"No candle data found for {symbol}")
                return None
                    
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {str(e)}")
            return None
    
    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get real-time quote for a symbol"""
        try:
            if not self.client:
                logger.error("Client not authenticated")
                return None
            
            # Get quote from Schwab API
            quote = self.client.get_quotes([symbol])
            
            if quote and symbol in quote:
                logger.info(f"Retrieved quote for {symbol}")
                return quote[symbol]
            else:
                logger.warning(f"No quote data found for {symbol}")
                return None
                    
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {str(e)}")
            return None
    
    async def place_order(self, order_data: Dict) -> Optional[Dict]:
        """Place a trade order"""
        try:
            if not self.client:
                logger.error("Client not authenticated")
                return None
            
            # Place order using Schwab API
            order_response = self.client.place_order(
                account_id=self.account_id,
                order_spec=order_data
            )
            
            if order_response:
                logger.info(f"Order placed successfully: {order_data}")
                return {"status": "success", "order_id": order_response.get('order_id', 'pending')}
            else:
                logger.error("Failed to place order")
                return None
                    
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return None
    
    async def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        try:
            if not self.client:
                logger.error("Client not authenticated")
                return None
            
            # Get account info from Schwab API
            account_info = self.client.get_account(self.account_id)
            
            if account_info:
                logger.info("Retrieved account information")
                return account_info
            else:
                logger.error("Failed to get account info")
                return None
                    
        except Exception as e:
            logger.error(f"Error getting account info: {str(e)}")
            return None
    
    async def get_positions(self) -> Optional[List[Dict]]:
        """Get current positions"""
        try:
            account_info = await self.get_account_info()
            if account_info and 'positions' in account_info:
                positions = account_info['positions']
                logger.info(f"Retrieved {len(positions)} positions")
                return positions
            return None
            
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            return None
    
    def create_market_order(self, symbol: str, instruction: str, quantity: int) -> Dict:
        """Create a market order for Schwab API"""
        return {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": instruction,  # BUY, SELL, BUY_TO_COVER, SELL_SHORT
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }
    
    def create_limit_order(self, symbol: str, instruction: str, quantity: int, price: float) -> Dict:
        """Create a limit order for Schwab API"""
        return {
            "orderType": "LIMIT",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "price": str(price),
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }
