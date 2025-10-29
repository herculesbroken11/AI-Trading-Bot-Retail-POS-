#!/usr/bin/env python3
"""
Script to get Schwab Account ID after authentication
"""

import asyncio
from core.schwab_api import SchwabAPI

async def get_account_id():
    """Get Schwab account ID after authentication"""
    print("Getting Schwab Account ID...")
    
    try:
        async with SchwabAPI() as schwab_api:
            # Get account information
            account_info = await schwab_api.get_account_info()
            
            if account_info:
                print("✅ Account information retrieved successfully!")
                print(f"Account ID: {account_info.get('accountNumber', 'Not found')}")
                print(f"Account Type: {account_info.get('type', 'Not specified')}")
                print(f"Account Status: {account_info.get('accountStatus', 'Not specified')}")
                
                # Save account ID to .env file
                account_id = account_info.get('accountNumber')
                if account_id:
                    print(f"\n🔧 Add this to your .env file:")
                    print(f"SCHWAB_ACCOUNT_ID={account_id}")
                    
                    # Update the .env file
                    with open('.env', 'r') as f:
                        content = f.read()
                    
                    # Replace the placeholder
                    updated_content = content.replace('SCHWAB_ACCOUNT_ID=your_schwab_account_id', f'SCHWAB_ACCOUNT_ID={account_id}')
                    
                    with open('.env', 'w') as f:
                        f.write(updated_content)
                    
                    print(f"✅ Account ID automatically added to .env file!")
                
            else:
                print("❌ Could not retrieve account information")
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(get_account_id())
