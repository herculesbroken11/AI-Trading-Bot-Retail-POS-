#!/usr/bin/env python3
"""
Manual Schwab Authentication Script
This will give you the authorization URL to open in your preferred browser
"""

from core.config import config
import urllib.parse
import secrets

def get_auth_url():
    """Generate the Schwab authorization URL"""
    # Generate a random state parameter for security
    state = secrets.token_urlsafe(32)
    
    # Build the authorization URL
    # For Trader API, we need api scope for trading operations
    base_url = "https://api.schwabapi.com/v1/oauth/authorize"
    params = {
        'response_type': 'code',
        'client_id': config.SCHWAB_CLIENT_ID,
        'redirect_uri': config.SCHWAB_REDIRECT_URI,
        'state': state,
        'scope': 'api'  # Required scope for trading operations with Trader API
    }
    
    # Create the full URL
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    
    return auth_url, state

def main():
    """Main function to get authorization URL"""
    print("🔐 Manual Schwab Authentication")
    print("=" * 50)
    
    try:
        auth_url, state = get_auth_url()
        
        print(f"✅ Authorization URL generated:")
        print(f"\n{auth_url}")
        print(f"\n📋 State parameter: {state}")
        
        print(f"\n🚀 Instructions:")
        print(f"1. Copy the URL above")
        print(f"2. Open Google Chrome")
        print(f"3. Paste the URL and press ENTER")
        print(f"4. Log in with your Schwab credentials")
        print(f"5. Grant permissions to the app")
        print(f"6. You'll be redirected to: {config.SCHWAB_REDIRECT_URI}")
        print(f"7. Copy the 'code' parameter from the redirect URL")
        print(f"8. Run: python complete_auth.py <code>")
        
        print(f"\n⚠️  Important:")
        print(f"- Make sure your Schwab app callback URL is: {config.SCHWAB_REDIRECT_URI}")
        print(f"- The redirect will show a security warning - that's normal")
        print(f"- Click 'Advanced' → 'Proceed to 127.0.0.1' to continue")
        
    except Exception as e:
        print(f"❌ Error generating auth URL: {str(e)}")

if __name__ == "__main__":
    main()
