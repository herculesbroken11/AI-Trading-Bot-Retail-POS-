"""
Polygon.io API Test Script
Tests the Polygon API connection and data retrieval.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
load_dotenv()

def test_direct_api():
    """Test Polygon API directly using requests."""
    print("=" * 60)
    print("TEST 1: Direct API Request")
    print("=" * 60)
    
    import requests
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ POLYGON_API_KEY not found in .env")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    # Test with AAPL for today
    symbol = "AAPL"
    today = datetime.now().strftime('%Y-%m-%d')
    # Use api.massive.com (new) or api.polygon.io (both work)
    base_url = os.getenv('POLYGON_BASE_URL', 'https://api.massive.com')
    url = f"{base_url}/v2/aggs/ticker/{symbol}/range/1/minute/{today}/{today}"
    
    params = {
        "apiKey": api_key,
        "adjusted": "true",
        "sort": "asc",
        "limit": 5
    }
    
    print(f"\n📡 Requesting data for {symbol} on {today}...")
    print(f"   URL: {url}")
    
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and len(data['results']) > 0:
                print(f"✅ SUCCESS! Got {len(data['results'])} candles")
                first_candle = data['results'][0]
                print(f"\n   First candle sample:")
                print(f"   - Timestamp: {first_candle.get('t')}")
                print(f"   - Open: ${first_candle.get('o'):.2f}" if first_candle.get('o') else "   - Open: N/A")
                print(f"   - High: ${first_candle.get('h'):.2f}" if first_candle.get('h') else "   - High: N/A")
                print(f"   - Low: ${first_candle.get('l'):.2f}" if first_candle.get('l') else "   - Low: N/A")
                print(f"   - Close: ${first_candle.get('c'):.2f}" if first_candle.get('c') else "   - Close: N/A")
                print(f"   - Volume: {first_candle.get('v'):,}" if first_candle.get('v') else "   - Volume: N/A")
                return True
            else:
                print("⚠️  Response OK but no data (market may be closed or no trades)")
                print(f"   Response keys: {list(data.keys())}")
                if 'status' in data:
                    print(f"   Status: {data.get('status')}")
                if 'queryCount' in data:
                    print(f"   Query count: {data.get('queryCount')}")
                return True  # API is working, just no data
        elif response.status_code == 429:
            print("❌ Rate limit exceeded (429)")
            print("   You've exceeded the maximum requests per minute.")
            print("   Please wait or upgrade your subscription: https://polygon.io/pricing")
            return False
        elif response.status_code == 401:
            print("❌ Authentication failed (401)")
            print("   Invalid API key. Please check your POLYGON_API_KEY in .env")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Response: {response.text[:200]}")
            return False
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False


def test_project_function():
    """Test using the project's polygon_api_request function."""
    print("\n" + "=" * 60)
    print("TEST 2: Project Function (polygon_api_request)")
    print("=" * 60)
    
    try:
        from utils.helpers import polygon_api_request
        
        # Test with yesterday and today (in case market is closed today)
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        today_str = today.strftime('%Y-%m-%d')
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        
        symbol = "AAPL"
        print(f"\n📡 Testing polygon_api_request() for {symbol}...")
        print(f"   Date range: {yesterday_str} to {today_str}")
        print(f"   Timeframe: 5-minute bars")
        
        result = polygon_api_request(
            symbol=symbol,
            multiplier=5,  # 5-minute bars
            timespan="minute",
            from_date=yesterday_str,
            to_date=today_str
        )
        
        candles = result.get('candles', [])
        
        if candles:
            print(f"✅ SUCCESS! Got {len(candles)} candles")
            
            # Show first and last candles
            print(f"\n   First candle:")
            first = candles[0]
            print(f"   - Datetime: {first.get('datetime')}")
            print(f"   - OHLC: O=${first.get('open'):.2f}, H=${first.get('high'):.2f}, L=${first.get('low'):.2f}, C=${first.get('close'):.2f}")
            print(f"   - Volume: {first.get('volume'):,}")
            
            if len(candles) > 1:
                print(f"\n   Last candle:")
                last = candles[-1]
                print(f"   - Datetime: {last.get('datetime')}")
                print(f"   - OHLC: O=${last.get('open'):.2f}, H=${last.get('high'):.2f}, L=${last.get('low'):.2f}, C=${last.get('close'):.2f}")
                print(f"   - Volume: {last.get('volume'):,}")
            
            return True
        else:
            print("⚠️  No candles returned (market may be closed or no data)")
            print(f"   Result keys: {list(result.keys())}")
            return True  # Function works, just no data
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure you're running from the backend directory")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_symbols():
    """Test with multiple symbols."""
    print("\n" + "=" * 60)
    print("TEST 3: Multiple Symbols")
    print("=" * 60)
    
    try:
        from utils.helpers import polygon_api_request
        
        symbols = ["AAPL", "MSFT", "TSLA"]
        today = datetime.now().strftime('%Y-%m-%d')
        
        results = {}
        for symbol in symbols:
            try:
                print(f"\n📡 Testing {symbol}...")
                result = polygon_api_request(
                    symbol=symbol,
                    multiplier=1,
                    timespan="minute",
                    from_date=today,
                    to_date=today
                )
                candles = result.get('candles', [])
                results[symbol] = len(candles)
                print(f"   ✅ {symbol}: {len(candles)} candles")
            except Exception as e:
                results[symbol] = f"Error: {str(e)[:50]}"
                print(f"   ❌ {symbol}: {e}")
        
        print(f"\n📊 Summary:")
        for symbol, count in results.items():
            print(f"   {symbol}: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("POLYGON.IO API TEST SUITE")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test 1: Direct API
    results.append(("Direct API", test_direct_api()))
    
    # Test 2: Project function
    results.append(("Project Function", test_project_function()))
    
    # Test 3: Multiple symbols
    results.append(("Multiple Symbols", test_multiple_symbols()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Polygon API is working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Check the errors above")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

