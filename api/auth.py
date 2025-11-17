"""
Schwab OAuth authentication handler.
"""
import os
import webbrowser
import requests
from flask import Blueprint, request, redirect, jsonify, url_for
from urllib.parse import urlencode
from utils.logger import setup_logger
from utils.helpers import save_tokens, load_tokens
from dotenv import load_dotenv

load_dotenv()

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = setup_logger("auth")

# Schwab OAuth endpoints
SCHWAB_AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

@auth_bp.route('/login', methods=['GET'])
def login():
    """
    Initiate OAuth flow by redirecting to Schwab login page.
    """
    client_id = os.getenv("SCHWAB_CLIENT_ID")
    redirect_uri = os.getenv("SCHWAB_REDIRECT_URI", "http://localhost:5035")
    
    if not client_id:
        return jsonify({"error": "SCHWAB_CLIENT_ID not configured"}), 500
    
    # OAuth parameters
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "api"
    }
    
    auth_url = f"{SCHWAB_AUTH_URL}?{urlencode(params)}"
    
    logger.info(f"Initiating OAuth flow: {auth_url}")
    
    # Open browser for user to login
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        logger.warning(f"Could not open browser: {e}")
    
    return jsonify({
        "message": "Please complete authentication in your browser",
        "auth_url": auth_url
    }), 200

@auth_bp.route('/callback', methods=['GET'])
def callback():
    """
    Handle OAuth callback with authorization code.
    """
    from urllib.parse import unquote
    
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        logger.error(f"OAuth error: {error}")
        return jsonify({"error": error}), 400
    
    if not code:
        return jsonify({"error": "No authorization code received"}), 400
    
    # URL decode the code in case it's encoded
    code = unquote(code)
    
    logger.info(f"Received authorization code (length: {len(code)}), exchanging for tokens...")
    
    # Exchange code for tokens
    try:
        tokens = exchange_code_for_tokens(code)
        save_tokens(tokens)
        logger.info("Tokens saved successfully")
        
        return jsonify({
            "message": "Authentication successful",
            "access_token": tokens.get("access_token", "")[:20] + "...",
            "expires_in": tokens.get("expires_in")
        }), 200
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    Refresh access token using refresh token.
    """
    tokens = load_tokens()
    
    if not tokens or 'refresh_token' not in tokens:
        return jsonify({"error": "No refresh token available"}), 400
    
    try:
        new_tokens = refresh_access_token(tokens['refresh_token'])
        save_tokens(new_tokens)
        logger.info("Token refreshed successfully")
        
        return jsonify({
            "message": "Token refreshed",
            "access_token": new_tokens.get("access_token", "")[:20] + "..."
        }), 200
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/status', methods=['GET'])
def status():
    """
    Check authentication status.
    """
    tokens = load_tokens()
    
    if not tokens:
        return jsonify({
            "authenticated": False,
            "message": "Not authenticated"
        }), 200
    
    return jsonify({
        "authenticated": True,
        "has_access_token": "access_token" in tokens,
        "has_refresh_token": "refresh_token" in tokens,
        "expires_in": tokens.get("expires_in")
    }), 200

def exchange_code_for_tokens(code: str) -> dict:
    """
    Exchange authorization code for access and refresh tokens.
    
    Args:
        code: Authorization code from OAuth callback
        
    Returns:
        Dictionary with tokens
    """
    import base64
    
    client_id = os.getenv("SCHWAB_CLIENT_ID")
    client_secret = os.getenv("SCHWAB_CLIENT_SECRET")
    redirect_uri = os.getenv("SCHWAB_REDIRECT_URI", "http://localhost:5035")
    
    if not client_id or not client_secret:
        raise ValueError("SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET must be set")
    
    # Schwab API requires Basic Authentication
    # Encode client_id:client_secret as base64
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Form data (not JSON)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    
    logger.info(f"Exchanging code for tokens (redirect_uri: {redirect_uri})")
    
    try:
        response = requests.post(SCHWAB_TOKEN_URL, headers=headers, data=data, timeout=30)
        
        # Log detailed error if request fails
        if response.status_code != 200:
            logger.error(f"Token exchange failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            try:
                error_data = response.json()
                logger.error(f"Error details: {error_data}")
            except:
                pass
        
        response.raise_for_status()
        
        tokens = response.json()
        logger.info("Token exchange successful")
        return tokens
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error during token exchange: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response body: {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token exchange: {e}")
        raise

def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_token: Refresh token from stored tokens
        
    Returns:
        Dictionary with new tokens
    """
    import base64
    
    client_id = os.getenv("SCHWAB_CLIENT_ID")
    client_secret = os.getenv("SCHWAB_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise ValueError("SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET must be set")
    
    # Schwab API requires Basic Authentication
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    logger.info("Refreshing access token")
    
    try:
        response = requests.post(SCHWAB_TOKEN_URL, headers=headers, data=data, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Token refresh failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise

