#!/usr/bin/env python3
"""
Headless Schwab Authentication for Server Deployment
This script generates an authorization URL and provides instructions for manual completion
"""

import asyncio
import aiohttp
import json
import os
from core.config import config
import urllib.parse
import secrets

def generate_auth_url():
    """Generate authorization URL for manual completion"""
    state = secrets.token_urlsafe(32)
    
    base_url = "https://api.schwabapi.com/v1/oauth/authorize"
    params = {
        'response_type': 'code',
        'client_id': config.SCHWAB_CLIENT_ID,
        'redirect_uri': config.SCHWAB_REDIRECT_URI,
        'state': state,
        'scope': 'api'
    }
    
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return auth_url, state

async def complete_auth_with_code(authorization_code):
    """Complete authentication using authorization code"""
    print("🔐 Completing Schwab Authentication on server...")
    
    try:
        async with aiohttp.ClientSession() as session:
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
                    
                    # Ensure data directory exists
                    os.makedirs('./data', exist_ok=True)
                    
                    # Save tokens
                    with open('./data/schwab_tokens.json', 'w') as f:
                        json.dump(token_data, f, indent=2)
                    
                    print("✅ Authentication completed successfully!")
                    print("🎉 Tokens saved to ./data/schwab_tokens.json")
                    
                    # Test API connection
                    print("\n🧪 Testing API connection...")
                    from core.schwab_api import SchwabAPI
                    
                    async with SchwabAPI() as api:
                        account_info = await api.get_account_info()
                        if account_info:
                            account_id = account_info.get('accountNumber')
                            print(f"✅ API connection successful!")
                            print(f"📋 Account ID: {account_id}")
                            
                            # Update .env file with account ID
                            if account_id:
                                with open('.env', 'r') as f:
                                    content = f.read()
                                
                                updated_content = content.replace(
                                    'SCHWAB_ACCOUNT_ID=your_schwab_account_id',
                                    f'SCHWAB_ACCOUNT_ID={account_id}'
                                )
                                
                                with open('.env', 'w') as f:
                                    f.write(updated_content)
                                
                                print(f"✅ Account ID saved to .env file!")
                        else:
                            print("⚠️  Could not retrieve account information")
                    
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Token exchange failed: {response.status}")
                    print(f"Error: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Error completing authentication: {str(e)}")
        return False

def main():
    """Main function for server authentication"""
    print("🚀 Schwab Authentication for Server Deployment")
    print("=" * 50)
    
    # Check if tokens already exist
    if os.path.exists('./data/schwab_tokens.json'):
        print("✅ Tokens already exist!")
        print("If you need to re-authenticate, delete ./data/schwab_tokens.json first")
        return
    
    # Generate authorization URL
    auth_url, state = generate_auth_url()
    
    print("📋 Step 1: Generate Authorization URL")
    print(f"Authorization URL: {auth_url}")
    print(f"State: {state}")
    
    print("\n📋 Step 2: Manual Authentication")
    print("1. Copy the URL above")
    print("2. Open it in your local browser (not on the server)")
    print("3. Log in with your Schwab credentials")
    print("4. Approve the app permissions")
    print("5. You'll be redirected to a URL with ?code=")
    print("6. Copy the FULL redirect URL")
    
    print("\n📋 Step 3: Complete Authentication")
    print("Once you have the redirect URL, run:")
    print("python server_auth.py complete <authorization_code>")
    
    # Check if completing authentication
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "complete":
        if len(sys.argv) != 3:
            print("Usage: python server_auth.py complete <authorization_code>")
            return
        
        authorization_code = sys.argv[2]
        asyncio.run(complete_auth_with_code(authorization_code))

if __name__ == "__main__":
    main()
