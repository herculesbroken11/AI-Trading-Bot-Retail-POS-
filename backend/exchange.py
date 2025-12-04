"""
Token exchange helper script.
Exchanges authorization code for access and refresh tokens.
"""
import os
import sys
import requests
from dotenv import load_dotenv
from utils.helpers import save_tokens

load_dotenv()

def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for tokens."""
    client_id = os.getenv("SCHWAB_CLIENT_ID")
    client_secret = os.getenv("SCHWAB_CLIENT_SECRET")
    redirect_uri = os.getenv("SCHWAB_REDIRECT_URI", "http://localhost:5035")
    
    if not all([client_id, client_secret]):
        print("❌ Missing SCHWAB_CLIENT_ID or SCHWAB_CLIENT_SECRET in .env")
        sys.exit(1)
    
    url = "https://api.schwabapi.com/v1/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri
    }
    
    print("🔄 Exchanging authorization code for tokens...")
    
    try:
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        
        tokens = response.json()
        save_tokens(tokens)
        
        print("✅ Tokens saved successfully!")
        print(f"   Access token: {tokens.get('access_token', '')[:20]}...")
        print(f"   Expires in: {tokens.get('expires_in', 0)} seconds")
        
        return tokens
    except requests.exceptions.RequestException as e:
        print(f"❌ Token exchange failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python exchange.py <authorization_code>")
        print("\nGet the authorization code from the OAuth callback URL.")
        sys.exit(1)
    
    code = sys.argv[1]
    exchange_code_for_tokens(code)

