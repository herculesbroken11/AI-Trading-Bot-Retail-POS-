#!/usr/bin/env python3
"""
Complete Schwab Authentication Script
This will complete the OAuth flow using the authorization code
"""

import asyncio
import sys
from core.schwab_api import SchwabAPI
from core.config import config

async def complete_auth(authorization_code):
    """Complete authentication using authorization code"""
    print("🔐 Completing Schwab Authentication...")
    
    try:
        api = SchwabAPI()
        
        # Complete the OAuth flow manually
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Exchange authorization code for tokens
            token_url = "https://api.schwabapi.com/v1/oauth/token"
            data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'client_id': config.SCHWAB_CLIENT_ID,
                'client_secret': config.SCHWAB_CLIENT_SECRET,
                'redirect_uri': config.SCHWAB_REDIRECT_URI
            }
            
            async with session.post(token_url, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    
                    # Save tokens to file
                    import json
                    import os
                    
                    # Ensure data directory exists
                    os.makedirs('./data', exist_ok=True)
                    
                    # Save tokens
                    with open('./data/schwab_tokens.json', 'w') as f:
                        json.dump(token_data, f, indent=2)
                    
                    print("✅ Authentication completed successfully!")
                    print("🎉 Tokens saved to ./data/schwab_tokens.json")
                    
                    # Test the API
                    print("\n🧪 Testing API connection...")
                    api.client = None  # Reset client
                    result = await api.authenticate()
                    
                    if result:
                        print("✅ API connection test successful!")
                        print("\nNext steps:")
                        print("1. Run: python get_account_id.py")
                        print("2. Run: python main.py (to start trading bot)")
                    else:
                        print("❌ API connection test failed")
                        
                else:
                    error_text = await response.text()
                    print(f"❌ Token exchange failed: {response.status}")
                    print(f"Error: {error_text}")
                    
    except Exception as e:
        print(f"❌ Error completing authentication: {str(e)}")

def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python complete_auth.py <authorization_code>")
        print("Get the authorization code from the redirect URL after logging in")
        return
    
    authorization_code = sys.argv[1]
    asyncio.run(complete_auth(authorization_code))

if __name__ == "__main__":
    main()
