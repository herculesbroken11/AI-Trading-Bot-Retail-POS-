#!/usr/bin/env python3
"""
Test script for Schwab API authentication
"""

import asyncio
from core.schwab_api import SchwabAPI

async def test_auth():
    """Test Schwab API authentication"""
    print("Testing Schwab API authentication...")
    
    try:
        api = SchwabAPI()
        result = await api.authenticate()
        print(f"Authentication result: {result}")
        
        if result:
            print("✅ Authentication successful!")
        else:
            print("❌ Authentication failed")
            
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_auth())
