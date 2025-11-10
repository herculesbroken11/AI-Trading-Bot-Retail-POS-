#!/usr/bin/env python3
"""
Test Connection Script
Verifies tokens and tests Schwab API calls
"""

import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config
from core.schwab_client import SchwabClient

def main():
    """Main function"""
    print("=" * 60)
    print("Schwab API Connection Test")
    print("=" * 60)
    
    # Check if tokens exist
    token_file = "./data/schwab_tokens.json"
    if not os.path.exists(token_file):
        print(f"\n[ERROR] Token file not found: {token_file}")
        print("Please authenticate first:")
        print("  - Windows: python scripts/auth_local.py")
        print("  - Manual: python scripts/exchange_code.py")
        return 1
    
    # Validate configuration
    is_valid, missing = Config.validate_schwab_config()
    if not is_valid:
        print(f"\n[ERROR] Missing required configuration: {', '.join(missing)}")
        return 1
    
    # Initialize client
    print("\nInitializing Schwab API client...")
    try:
        client = SchwabClient(
            Config.SCHWAB_CLIENT_ID,
            Config.SCHWAB_CLIENT_SECRET
        )
    except Exception as e:
        print(f"[ERROR] Failed to initialize client: {e}")
        return 1
    
    # Test 1: Get Accounts
    print("\n" + "=" * 60)
    print("Test 1: Get Account List")
    print("=" * 60)
    try:
        accounts = client.get_accounts()
        print(f"[OK] Successfully retrieved {len(accounts)} account(s)")
        
        for i, account in enumerate(accounts, 1):
            account_number = account.get('accountNumber', 'N/A')
            account_type = account.get('type', 'N/A')
            print(f"\n  Account {i}:")
            print(f"    Number: {account_number}")
            print(f"    Type: {account_type}")
            
            # If account ID not set, suggest using this one
            if not Config.SCHWAB_ACCOUNT_ID and i == 1:
                print(f"\n  [INFO] Consider setting SCHWAB_ACCOUNT_ID={account_number} in .env")
        
        # Print full JSON for first account
        if accounts:
            print("\n  Full account data (first account):")
            print(json.dumps(accounts[0], indent=2))
            
    except Exception as e:
        print(f"[ERROR] Failed to get accounts: {e}")
        print("\nTroubleshooting:")
        print("1. Check if tokens are valid (try re-authenticating)")
        print("2. Verify your API credentials")
        print("3. Check if your account has API access enabled")
        return 1
    
    # Test 2: Get Account Details (if account ID is set)
    if Config.SCHWAB_ACCOUNT_ID:
        print("\n" + "=" * 60)
        print("Test 2: Get Account Details")
        print("=" * 60)
        try:
            account = client.get_account(Config.SCHWAB_ACCOUNT_ID)
            print(f"[OK] Successfully retrieved account details")
            print("\n  Account Summary:")
            
            # Extract key information
            account_type = account.get('type', 'N/A')
            print(f"    Type: {account_type}")
            
            # Balance information
            if 'securitiesAccount' in account:
                sec_account = account['securitiesAccount']
                if 'currentBalances' in sec_account:
                    balances = sec_account['currentBalances']
                    cash_balance = balances.get('cashBalance', 0)
                    print(f"    Cash Balance: ${cash_balance:,.2f}")
            
            print("\n  Full account data:")
            print(json.dumps(account, indent=2))
            
        except Exception as e:
            print(f"[WARNING] Failed to get account details: {e}")
            print("This is not critical - account list test passed")
    
    # Test 3: Get Quote
    print("\n" + "=" * 60)
    print("Test 3: Get Market Quote")
    print("=" * 60)
    test_symbol = "SPY"
    try:
        quote = client.get_quote(test_symbol)
        print(f"[OK] Successfully retrieved quote for {test_symbol}")
        print("\n  Quote Data:")
        print(json.dumps(quote, indent=2))
        
    except Exception as e:
        print(f"[ERROR] Failed to get quote: {e}")
        print("\nTroubleshooting:")
        print("1. Check if market is open")
        print("2. Verify symbol is valid")
        print("3. Check API permissions for market data")
        return 1
    
    # Test 4: Get Price History
    print("\n" + "=" * 60)
    print("Test 4: Get Price History")
    print("=" * 60)
    try:
        history = client.get_price_history(
            symbol=test_symbol,
            period_type="day",
            period=1,
            frequency_type="minute",
            frequency=5
        )
        
        if 'candles' in history:
            candles = history['candles']
            print(f"[OK] Successfully retrieved {len(candles)} price history data points")
            if candles:
                print(f"\n  Latest candle:")
                print(json.dumps(candles[-1], indent=2))
        else:
            print("[WARNING] No candles in response")
            
    except Exception as e:
        print(f"[WARNING] Failed to get price history: {e}")
        print("This is not critical - other tests passed")
    
    # Summary
    print("\n" + "=" * 60)
    print("Connection Test Summary")
    print("=" * 60)
    print("[OK] All critical tests passed!")
    print("\nYour Schwab API integration is working correctly.")
    print("\nNext steps:")
    print("1. Set SCHWAB_ACCOUNT_ID in .env if you want to use a specific account")
    print("2. Run: python scripts/init_db.py (to initialize database)")
    print("3. Run: uvicorn api.main:app --host 0.0.0.0 --port 8000 (to start API server)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

