"""
Authentication helper functions for Schwab OAuth
"""

import urllib.parse
import secrets
from typing import Tuple
from core.config import Config

def generate_authorization_url(redirect_uri: str, client_id: str, scope: str = "api") -> Tuple[str, str]:
    """
    Generate OAuth authorization URL
    
    Args:
        redirect_uri: Callback redirect URI
        client_id: Schwab App Key (Client ID)
        scope: OAuth scope (default: "api" for full access)
        
    Returns:
        Tuple of (authorization_url, state)
    """
    state = secrets.token_urlsafe(32)
    
    base_url = "https://api.schwabapi.com/v1/oauth/authorize"
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': scope
    }
    
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return auth_url, state

def extract_code_from_url(redirect_url: str) -> str:
    """
    Extract authorization code from redirect URL
    
    Args:
        redirect_url: Full redirect URL from OAuth callback
        
    Returns:
        Authorization code
    """
    try:
        parsed = urllib.parse.urlparse(redirect_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        if 'code' not in params:
            raise ValueError("No 'code' parameter found in redirect URL")
        
        code = params['code'][0]
        return code
    except Exception as e:
        raise ValueError(f"Failed to extract code from URL: {e}")

def validate_redirect_uri(redirect_uri: str) -> bool:
    """
    Validate redirect URI format
    
    Args:
        redirect_uri: Redirect URI to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        parsed = urllib.parse.urlparse(redirect_uri)
        
        # Must be HTTPS or HTTP for localhost
        if parsed.scheme not in ['https', 'http']:
            return False
        
        # For localhost, allow HTTP
        if parsed.hostname == '127.0.0.1' or parsed.hostname == 'localhost':
            return True
        
        # For external, must be HTTPS
        if parsed.scheme != 'https':
            return False
        
        return True
    except Exception:
        return False

