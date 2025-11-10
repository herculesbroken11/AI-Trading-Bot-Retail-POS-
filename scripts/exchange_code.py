#!/usr/bin/env python3
"""
Manual Code Exchange Script
Accepts pasted redirect URL and exchanges authorization code for tokens
"""

import os
import sys
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config
from core.auth import extract_code_from_url, validate_redirect_uri
from core.schwab_client import SchwabClient

def main():
    """Main function"""
    print("=" * 60)
    print("Schwab OAuth Manual Code Exchange")
    print("=" * 60)
    
    # Validate configuration
    is_valid, missing = Config.validate_schwab_config()
    if not is_valid:
        print(f"\n[ERROR] Missing required configuration: {', '.join(missing)}")
        print("Please check your .env file")
        return 1
    
    # Check if tokens already exist
    token_file = "./data/schwab_tokens.json"
    if os.path.exists(token_file):
        response = input(f"\nTokens file already exists at {token_file}\nOverwrite? (y/N): ")
        if response.lower() != 'y':
            print("Exchange cancelled")
            return 0
    
    # Get redirect URL from user
    print("\nPlease paste the full redirect URL from your browser.")
    print("It should look like:")
    print("  https://127.0.0.1:5035/?code=ABC123&state=XYZ789")
    print("  or")
    print("  https://your-server.com/?code=ABC123&state=XYZ789")
    print("\nPaste the URL here (or just the code):")
    
    user_input = input().strip()
    
    # Extract code
    code = None
    if user_input.startswith('http'):
        # Full URL provided
        try:
            code = extract_code_from_url(user_input)
        except ValueError as e:
            print(f"\n[ERROR] {e}")
            print("\nPlease ensure you copied the complete URL with the ?code= parameter")
            return 1
    else:
        # Just the code provided
        code = user_input
    
    if not code:
        print("\n[ERROR] No authorization code found")
        return 1
    
    # Get redirect URI
    print(f"\nEnter the redirect URI used in the OAuth flow:")
    print(f"(Default: {Config.SCHWAB_REDIRECT_URI})")
    redirect_uri = input().strip()
    
    if not redirect_uri:
        redirect_uri = Config.SCHWAB_REDIRECT_URI
    
    # Validate redirect URI
    if not validate_redirect_uri(redirect_uri):
        print(f"\n[ERROR] Invalid redirect URI: {redirect_uri}")
        return 1
    
    # Exchange code for tokens
    print(f"\nExchanging authorization code for tokens...")
    print(f"Using redirect URI: {redirect_uri}")
    
    try:
        client = SchwabClient(
            Config.SCHWAB_CLIENT_ID,
            Config.SCHWAB_CLIENT_SECRET
        )
        
        client.exchange_code_for_tokens(code, redirect_uri)
        
        print(f"\n[OK] Authentication successful!")
        print(f"Tokens saved to: {token_file}")
        print("\nNext steps:")
        print("1. Run: python scripts/test_connection.py (to verify tokens)")
        print("2. Run: python scripts/init_db.py (to initialize database)")
        print("3. Run: uvicorn api.main:app --host 0.0.0.0 --port 8000 (to start API server)")
        
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Failed to exchange code for tokens: {e}")
        print("\nTroubleshooting:")
        print("1. Verify your SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET in .env")
        print("2. Check that the redirect URI matches exactly what's in Schwab Developer Portal")
        print("3. Make sure the authorization code hasn't expired (codes expire quickly)")
        print("4. Try generating a new authorization code if this one has expired")
        return 1

if __name__ == "__main__":
    sys.exit(main())

