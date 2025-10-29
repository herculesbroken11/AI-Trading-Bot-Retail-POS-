#!/usr/bin/env python3
"""
Simple Schwab Authentication Script
This will help you complete the OAuth authentication flow
"""

import asyncio
from core.schwab_api import SchwabAPI

async def authenticate():
    """Complete Schwab authentication"""
    print("🔐 Starting Schwab Authentication...")
    print("This will open a browser window for you to log in with your Schwab credentials.")
    print("After logging in, you'll be redirected back and tokens will be saved automatically.")
    print("\nPress ENTER to continue...")
    input()
    
    try:
        api = SchwabAPI()
        result = await api.authenticate()
        
        if result:
            print("✅ Authentication successful!")
            print("🎉 Your tokens have been saved to ./data/schwab_tokens.json")
            print("\nNext steps:")
            print("1. Run: python get_account_id.py (to get your account ID)")
            print("2. Run: python main.py (to start the trading bot)")
            print("3. Or run: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload (for API server)")
        else:
            print("❌ Authentication failed")
            print("Make sure your Schwab app callback URL is set to: https://127.0.0.1:5035")
            
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(authenticate())
