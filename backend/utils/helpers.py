"""
Helper utilities for HTTP requests, data processing, and common operations.
"""
import os
import json
import requests
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from utils.logger import setup_logger

load_dotenv()
logger = setup_logger("helpers")

def load_tokens() -> Optional[Dict[str, Any]]:
    """Load tokens from /data/tokens.json"""
    token_file = Path("data/tokens.json")
    if token_file.exists():
        with open(token_file, 'r') as f:
            return json.load(f)
    return None

def save_tokens(tokens: Dict[str, Any]) -> None:
    """
    Save tokens to /data/tokens.json
    Also calculates and stores expires_at timestamp for automatic refresh.
    """
    token_file = Path("data/tokens.json")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Calculate expiration timestamp if expires_in is provided
    if 'expires_in' in tokens and 'expires_at' not in tokens:
        # expires_in is in seconds, calculate absolute timestamp
        expires_in = int(tokens.get('expires_in', 1800))  # Default 30 minutes
        expires_at = time.time() + expires_in - 300  # Refresh 5 minutes before expiration
        tokens['expires_at'] = expires_at
        logger.info(f"Token expires in {expires_in}s, will refresh at {expires_at} (5 min buffer)")
    elif 'expires_in' in tokens:
        # Update expires_at if expires_in changed
        expires_in = int(tokens.get('expires_in', 1800))
        expires_at = time.time() + expires_in - 300
        tokens['expires_at'] = expires_at
    
    with open(token_file, 'w') as f:
        json.dump(tokens, f, indent=2)

def get_schwab_headers(access_token: str, include_content_type: bool = False) -> Dict[str, str]:
    """Get headers for Schwab API requests"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    # Only include Content-Type for POST/PUT requests (with body)
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers

def ensure_valid_token() -> Optional[str]:
    """
    Ensure access token is valid and refresh if needed.
    Automatically refreshes token if it's about to expire (within 5 minutes).
    
    Returns:
        Valid access token, or None if refresh failed
    """
    tokens = load_tokens()
    if not tokens:
        logger.warning("No tokens found")
        return None
    
    if 'access_token' not in tokens:
        logger.warning("No access token found")
        return None
    
    # Check if token is about to expire
    current_time = time.time()
    expires_at = tokens.get('expires_at')
    
    if expires_at and current_time >= expires_at:
        # Token expired or about to expire, refresh it
        logger.info("Token expired or about to expire, refreshing...")
        
        if 'refresh_token' not in tokens:
            logger.error("No refresh token available for automatic refresh")
            return None
        
        try:
            from api.auth import refresh_access_token
            new_tokens = refresh_access_token(tokens['refresh_token'])
            save_tokens(new_tokens)
            logger.info("Token automatically refreshed successfully")
            return new_tokens.get('access_token')
        except Exception as e:
            logger.error(f"Automatic token refresh failed: {e}")
            return None
    
    # Token is still valid
    return tokens.get('access_token')

def get_valid_access_token() -> Optional[str]:
    """
    Get a valid access token, automatically refreshing if needed.
    This is a convenience wrapper around ensure_valid_token().
    
    Returns:
        Valid access token, or None if not available
    """
    return ensure_valid_token()

def schwab_api_request(
    method: str,
    url: str,
    access_token: Optional[str] = None,
    params: Optional[Dict] = None,
    data: Optional[Dict] = None
) -> requests.Response:
    """
    Make a request to Schwab API with proper error handling.
    Automatically ensures token is valid before making request.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: API endpoint URL
        access_token: OAuth access token (optional - will auto-load and refresh if not provided)
        params: Query parameters
        data: Request body data
        
    Returns:
        Response object
    """
    # Always ensure token is valid before making request (auto-refresh if needed)
    # If access_token provided, we still check if it needs refresh
    # If not provided, we load it automatically
    if access_token is None:
        access_token = ensure_valid_token()
        if not access_token:
            raise Exception("No valid access token available. Please authenticate.")
    else:
        # Even if token provided, check if it needs refresh
        valid_token = ensure_valid_token()
        if valid_token:
            access_token = valid_token
    
    # GET/DELETE requests don't need Content-Type (no body)
    # POST/PUT requests need Content-Type (have body)
    include_content_type = method.upper() in ["POST", "PUT"]
    headers = get_schwab_headers(access_token, include_content_type=include_content_type)
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data, params=params, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, params=params, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        # For 400/401/403 errors, try to include response body for better debugging
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            if hasattr(e.response, 'text') and e.response.text:
                try:
                    error_body = e.response.json()
                    # Format the error body nicely
                    if isinstance(error_body, dict):
                        error_msg = f"{error_msg}. Response: {error_body}"
                    else:
                        error_msg = f"{error_msg}. Response: {error_body}"
                except:
                    # If not JSON, include text (truncated)
                    error_msg = f"{error_msg}. Response body: {e.response.text[:500]}"
        raise Exception(f"Schwab API request failed: {error_msg}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Schwab API request failed: {str(e)}")

def format_price(price: float, decimals: int = 2) -> str:
    """Format price to string with specified decimals"""
    return f"{price:.{decimals}f}"

def parse_time(time_str: str) -> tuple:
    """Parse time string (HH:MM) to hours and minutes"""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])

