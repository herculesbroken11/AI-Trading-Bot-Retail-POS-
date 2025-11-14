"""
Helper utilities for HTTP requests, data processing, and common operations.
"""
import os
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

def load_tokens() -> Optional[Dict[str, Any]]:
    """Load tokens from /data/tokens.json"""
    token_file = Path("data/tokens.json")
    if token_file.exists():
        with open(token_file, 'r') as f:
            return json.load(f)
    return None

def save_tokens(tokens: Dict[str, Any]) -> None:
    """Save tokens to /data/tokens.json"""
    token_file = Path("data/tokens.json")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    with open(token_file, 'w') as f:
        json.dump(tokens, f, indent=2)

def get_schwab_headers(access_token: str) -> Dict[str, str]:
    """Get headers for Schwab API requests"""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

def schwab_api_request(
    method: str,
    url: str,
    access_token: str,
    params: Optional[Dict] = None,
    data: Optional[Dict] = None
) -> requests.Response:
    """
    Make a request to Schwab API with proper error handling.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: API endpoint URL
        access_token: OAuth access token
        params: Query parameters
        data: Request body data
        
    Returns:
        Response object
    """
    headers = get_schwab_headers(access_token)
    
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
    except requests.exceptions.RequestException as e:
        raise Exception(f"Schwab API request failed: {str(e)}")

def format_price(price: float, decimals: int = 2) -> str:
    """Format price to string with specified decimals"""
    return f"{price:.{decimals}f}"

def parse_time(time_str: str) -> tuple:
    """Parse time string (HH:MM) to hours and minutes"""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])

