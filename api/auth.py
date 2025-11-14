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
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        logger.error(f"OAuth error: {error}")
        return jsonify({"error": error}), 400
    
    if not code:
        return jsonify({"error": "No authorization code received"}), 400
    
    logger.info("Received authorization code, exchanging for tokens...")
    
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
    client_id = os.getenv("SCHWAB_CLIENT_ID")
    client_secret = os.getenv("SCHWAB_CLIENT_SECRET")
    redirect_uri = os.getenv("SCHWAB_REDIRECT_URI", "http://localhost:5035")
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri
    }
    
    response = requests.post(SCHWAB_TOKEN_URL, data=data, timeout=30)
    response.raise_for_status()
    
    return response.json()

def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_token: Refresh token from stored tokens
        
    Returns:
        Dictionary with new tokens
    """
    client_id = os.getenv("SCHWAB_CLIENT_ID")
    client_secret = os.getenv("SCHWAB_CLIENT_SECRET")
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    response = requests.post(SCHWAB_TOKEN_URL, data=data, timeout=30)
    response.raise_for_status()
    
    return response.json()

