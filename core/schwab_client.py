"""
Schwab API Client
Handles token management, refresh, and API calls
"""

import json
import os
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class SchwabClient:
    """Client for interacting with Charles Schwab API"""
    
    BASE_URL = "https://api.schwabapi.com"
    TOKEN_URL = f"{BASE_URL}/v1/oauth/token"
    ACCOUNTS_URL = f"{BASE_URL}/trader/v1/accounts"
    MARKET_DATA_URL = f"{BASE_URL}/marketdata/v1"
    
    def __init__(self, client_id: str, client_secret: str, token_file: str = "./data/schwab_tokens.json"):
        """
        Initialize Schwab API client
        
        Args:
            client_id: Schwab App Key (Client ID)
            client_secret: Schwab Secret
            token_file: Path to token file
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = token_file
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[float] = None
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Load existing tokens if available
        self._load_tokens()
    
    def _load_tokens(self) -> bool:
        """Load tokens from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                    self.access_token = token_data.get('access_token')
                    self.refresh_token = token_data.get('refresh_token')
                    
                    # Calculate expiration time
                    expires_in = token_data.get('expires_in', 1800)  # Default 30 minutes
                    issued_at = token_data.get('issued_at', time.time())
                    self.token_expires_at = issued_at + expires_in
                    
                    return True
        except Exception as e:
            print(f"Warning: Could not load tokens: {e}")
        return False
    
    def _save_tokens(self, token_data: Dict[str, Any]) -> None:
        """Save tokens to file with secure permissions"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            
            # Add issued_at timestamp
            token_data['issued_at'] = time.time()
            
            # Save to file
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            # Set secure file permissions (600 = owner read/write only)
            try:
                os.chmod(self.token_file, 0o600)
            except (OSError, AttributeError):
                # Windows doesn't support chmod the same way
                pass
            
            # Update in-memory tokens
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            expires_in = token_data.get('expires_in', 1800)
            self.token_expires_at = time.time() + expires_in
            
        except Exception as e:
            raise Exception(f"Failed to save tokens: {e}")
    
    def exchange_code_for_tokens(self, authorization_code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            authorization_code: Authorization code from OAuth redirect
            redirect_uri: Redirect URI used in OAuth flow
            
        Returns:
            Token data dictionary
        """
        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': redirect_uri
        }
        
        response = self.session.post(self.TOKEN_URL, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            self._save_tokens(token_data)
            return token_data
        else:
            error_msg = response.text
            raise Exception(f"Token exchange failed ({response.status_code}): {error_msg}")
    
    def refresh_access_token(self) -> bool:
        """
        Refresh access token using refresh token
        
        Returns:
            True if successful, False otherwise
        """
        if not self.refresh_token:
            return False
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = self.session.post(self.TOKEN_URL, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self._save_tokens(token_data)
                return True
            else:
                print(f"Token refresh failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return False
    
    def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token"""
        # Check if token exists and is not expired
        if self.access_token and self.token_expires_at:
            # Refresh if token expires in less than 5 minutes
            if time.time() < (self.token_expires_at - 300):
                return True
        
        # Try to refresh
        if self.refresh_token:
            return self.refresh_access_token()
        
        return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        if not self._ensure_valid_token():
            raise Exception("No valid access token available. Please authenticate first.")
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """
        Get list of all linked accounts
        
        Returns:
            List of account dictionaries
        """
        headers = self._get_headers()
        response = self.session.get(self.ACCOUNTS_URL, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get accounts ({response.status_code}): {response.text}")
    
    def get_account(self, account_number: str) -> Dict[str, Any]:
        """
        Get details for a specific account
        
        Args:
            account_number: Account number (may be encrypted value)
            
        Returns:
            Account details dictionary
        """
        headers = self._get_headers()
        url = f"{self.ACCOUNTS_URL}/{account_number}"
        response = self.session.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get account ({response.status_code}): {response.text}")
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time quote for a symbol
        
        Args:
            symbol: Stock symbol (e.g., 'SPY', 'AAPL')
            
        Returns:
            Quote data dictionary
        """
        headers = self._get_headers()
        url = f"{self.MARKET_DATA_URL}/quotes"
        params = {'symbols': symbol}
        
        response = self.session.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return data.get(symbol, {})
        else:
            raise Exception(f"Failed to get quote ({response.status_code}): {response.text}")
    
    def get_price_history(self, symbol: str, period_type: str = "day", period: int = 1,
                         frequency_type: str = "minute", frequency: int = 1) -> Dict[str, Any]:
        """
        Get price history for a symbol
        
        Args:
            symbol: Stock symbol
            period_type: day, month, year, ytd
            period: Number of periods
            frequency_type: minute, daily, weekly, monthly
            frequency: Frequency value
            
        Returns:
            Price history data
        """
        headers = self._get_headers()
        url = f"{self.MARKET_DATA_URL}/{symbol}/pricehistory"
        params = {
            'periodType': period_type,
            'period': period,
            'frequencyType': frequency_type,
            'frequency': frequency
        }
        
        response = self.session.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get price history ({response.status_code}): {response.text}")

