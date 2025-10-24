"""
TD Ameritrade API Wrapper
Handles market data retrieval and trade execution
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
from core.config import config
from core.logger import logger

class TDAmeritradeAPI:
    """TD Ameritrade API wrapper for trading operations"""
    
    def __init__(self):
        self.client_id = config.TD_CLIENT_ID
        self.redirect_uri = config.TD_REDIRECT_URI
        self.account_id = config.TD_ACCOUNT_ID
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.base_url = "https://api.tdameritrade.com/v1"
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def authenticate(self, authorization_code: str = None) -> bool:
        """
        Authenticate with TD Ameritrade API
        If authorization_code is provided, complete OAuth flow
        """
        try:
            if authorization_code:
                # Complete OAuth flow
                token_data = await self._get_access_token(authorization_code)
                if token_data:
                    self.access_token = token_data.get('access_token')
                    self.refresh_token = token_data.get('refresh_token')
                    self.token_expiry = datetime.now() + timedelta(seconds=token_data.get('expires_in', 1800))
                    logger.info("Successfully authenticated with TD Ameritrade API")
                    return True
            
            # Check if we have a valid token
            if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
                return True
            
            # Try to refresh token
            if self.refresh_token:
                return await self._refresh_access_token()
            
            logger.error("No valid authentication found")
            return False
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False
    
    async def _get_access_token(self, authorization_code: str) -> Optional[Dict]:
        """Get access token using authorization code"""
        url = "https://api.tdameritrade.com/v1/oauth2/token"
        data = {
            'grant_type': 'authorization_code',
            'access_type': 'offline',
            'code': authorization_code,
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri
        }
        
        async with self.session.post(url, data=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(f"Failed to get access token: {response.status}")
                return None
    
    async def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token"""
        url = "https://api.tdameritrade.com/v1/oauth2/token"
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id
        }
        
        async with self.session.post(url, data=data) as response:
            if response.status == 200:
                token_data = await response.json()
                self.access_token = token_data.get('access_token')
                self.token_expiry = datetime.now() + timedelta(seconds=token_data.get('expires_in', 1800))
                logger.info("Successfully refreshed access token")
                return True
            else:
                logger.error(f"Failed to refresh access token: {response.status}")
                return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    async def get_market_data(self, symbol: str, period_type: str = "day", 
                            period: int = 1, frequency_type: str = "minute", 
                            frequency: int = 1) -> Optional[pd.DataFrame]:
        """
        Get market data for a symbol
        
        Args:
            symbol: Stock symbol
            period_type: day, month, year, ytd
            period: Number of periods
            frequency_type: minute, daily, weekly, monthly
            frequency: Frequency value
        """
        try:
            if not await self.authenticate():
                return None
            
            url = f"{self.base_url}/marketdata/{symbol}/pricehistory"
            params = {
                'apikey': self.client_id,
                'periodType': period_type,
                'period': period,
                'frequencyType': frequency_type,
                'frequency': frequency
            }
            
            headers = self._get_headers()
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'candles' in data:
                        df = pd.DataFrame(data['candles'])
                        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                        df.set_index('datetime', inplace=True)
                        logger.info(f"Retrieved market data for {symbol}")
                        return df
                    else:
                        logger.warning(f"No candle data found for {symbol}")
                        return None
                else:
                    logger.error(f"Failed to get market data: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {str(e)}")
            return None
    
    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get real-time quote for a symbol"""
        try:
            if not await self.authenticate():
                return None
            
            url = f"{self.base_url}/marketdata/{symbol}/quotes"
            params = {'apikey': self.client_id}
            headers = self._get_headers()
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if symbol in data:
                        logger.info(f"Retrieved quote for {symbol}")
                        return data[symbol]
                    else:
                        logger.warning(f"No quote data found for {symbol}")
                        return None
                else:
                    logger.error(f"Failed to get quote: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {str(e)}")
            return None
    
    async def place_order(self, order_data: Dict) -> Optional[Dict]:
        """Place a trade order"""
        try:
            if not await self.authenticate():
                return None
            
            url = f"{self.base_url}/accounts/{self.account_id}/orders"
            headers = self._get_headers()
            
            async with self.session.post(url, json=order_data, headers=headers) as response:
                if response.status == 201:
                    logger.info(f"Order placed successfully: {order_data}")
                    return {"status": "success", "order_id": "pending"}
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to place order: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return None
    
    async def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        try:
            if not await self.authenticate():
                return None
            
            url = f"{self.base_url}/accounts/{self.account_id}"
            params = {'apikey': self.client_id}
            headers = self._get_headers()
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("Retrieved account information")
                    return data
                else:
                    logger.error(f"Failed to get account info: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting account info: {str(e)}")
            return None
    
    async def get_positions(self) -> Optional[List[Dict]]:
        """Get current positions"""
        try:
            account_info = await self.get_account_info()
            if account_info and 'securitiesAccount' in account_info:
                positions = account_info['securitiesAccount'].get('positions', [])
                logger.info(f"Retrieved {len(positions)} positions")
                return positions
            return None
            
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            return None
    
    def create_market_order(self, symbol: str, instruction: str, quantity: int) -> Dict:
        """Create a market order"""
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
        """Create a limit order"""
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
