"""
Market data and quotes API endpoints.
"""
import os
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
from utils.logger import setup_logger
from utils.helpers import load_tokens, schwab_api_request, save_tokens, polygon_api_request
from core.ov_engine import OVStrategyEngine

quotes_bp = Blueprint('quotes', __name__, url_prefix='/quotes')
logger = setup_logger("quotes")

# Schwab API endpoints
SCHWAB_BASE_URL = "https://api.schwabapi.com"
SCHWAB_MARKETDATA_BASE = f"{SCHWAB_BASE_URL}/marketdata/v1"
SCHWAB_QUOTES_URL = f"{SCHWAB_MARKETDATA_BASE}/quotes"
SCHWAB_HISTORICAL_URL = f"{SCHWAB_MARKETDATA_BASE}/pricehistory"
SCHWAB_CHAINS_URL = f"{SCHWAB_MARKETDATA_BASE}/chains"
SCHWAB_EXPIRATION_CHAIN_URL = f"{SCHWAB_MARKETDATA_BASE}/expirationchain"
SCHWAB_MOVERS_URL = f"{SCHWAB_MARKETDATA_BASE}/movers"
SCHWAB_MARKETS_URL = f"{SCHWAB_MARKETDATA_BASE}/markets"
SCHWAB_INSTRUMENTS_URL = f"{SCHWAB_MARKETDATA_BASE}/instruments"

@quotes_bp.route('/<symbol>', methods=['GET'])
def get_quote(symbol: str):
    """
    Get real-time quote for a symbol.
    Schwab API: GET /quotes?symbols={symbol} or GET /{symbol_id}/quotes
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Try the list format first
        url = f"{SCHWAB_QUOTES_URL}?symbols={symbol}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved quote for {symbol}")
        return jsonify(data), 200
    except Exception as e:
        # If 401 error, try to refresh token and retry
        if "401" in str(e) or "Unauthorized" in str(e):
            logger.warning("401 error detected, attempting token refresh...")
            try:
                from api.auth import refresh_access_token
                if tokens.get('refresh_token'):
                    new_tokens = refresh_access_token(tokens['refresh_token'])
                    save_tokens(new_tokens)
                    logger.info("Token refreshed, retrying request...")
                    # Retry with new token
                    response = schwab_api_request("GET", url, new_tokens['access_token'])
                    data = response.json()
                    logger.info(f"Retrieved quote for {symbol} after token refresh")
                    return jsonify(data), 200
                else:
                    return jsonify({
                        "error": "Token expired. Please re-authenticate.",
                        "re_auth_url": "/auth/login"
                    }), 401
            except Exception as refresh_error:
                logger.error(f"Token refresh failed: {refresh_error}")
                return jsonify({
                    "error": "Token expired and refresh failed. Please re-authenticate.",
                    "re_auth_url": "/auth/login"
                }), 401
        
        logger.error(f"Failed to get quote for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@quotes_bp.route('/batch', methods=['GET'])
def get_quotes_batch():
    """
    Get quotes for multiple symbols.
    Schwab API: GET /quotes?symbols={symbol1,symbol2,...}
    
    Query params:
        symbols: Comma-separated list of symbols (e.g., "AAPL,MSFT,GOOGL")
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    symbols = request.args.get('symbols')
    if not symbols:
        return jsonify({"error": "symbols parameter required (comma-separated)"}), 400
    
    try:
        url = f"{SCHWAB_QUOTES_URL}?symbols={symbols}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved quotes for {len(symbols.split(','))} symbols")
        return jsonify(data), 200
    except Exception as e:
        # If 401 error, try to refresh token and retry
        if "401" in str(e) or "Unauthorized" in str(e):
            logger.warning("401 error detected, attempting token refresh...")
            try:
                from api.auth import refresh_access_token
                if tokens.get('refresh_token'):
                    new_tokens = refresh_access_token(tokens['refresh_token'])
                    save_tokens(new_tokens)
                    logger.info("Token refreshed, retrying request...")
                    # Retry with new token
                    response = schwab_api_request("GET", url, new_tokens['access_token'])
                    data = response.json()
                    logger.info(f"Retrieved batch quotes after token refresh")
                    return jsonify(data), 200
                else:
                    return jsonify({
                        "error": "Token expired. Please re-authenticate.",
                        "re_auth_url": "/auth/login"
                    }), 401
            except Exception as refresh_error:
                logger.error(f"Token refresh failed: {refresh_error}")
                return jsonify({
                    "error": "Token expired and refresh failed. Please re-authenticate.",
                    "re_auth_url": "/auth/login"
                }), 401
        
        logger.error(f"Failed to get batch quotes: {e}")
        return jsonify({"error": str(e)}), 500

@quotes_bp.route('/single/<symbol_id>', methods=['GET'])
def get_quote_single(symbol_id: str):
    """
    Get quote by single symbol (alternative format).
    Schwab API: GET /{symbol_id}/quotes
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_MARKETDATA_BASE}/{symbol_id}/quotes"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved quote for {symbol_id} (single format)")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get quote for {symbol_id}: {e}")
        return jsonify({"error": str(e)}), 500

@quotes_bp.route('/historical/<symbol>', methods=['GET'])
def get_historical(symbol: str):
    """
    Get historical price data for a symbol using Polygon.io.
    
    Query params:
        periodType: day, month, year, ytd
        period: 1, 2, 3, 4, 5, 10, 15, 20
        frequencyType: minute, daily, weekly, monthly
        frequency: 1, 5, 10, 15, 30
    """
    # Default parameters for intraday data
    period_type = request.args.get('periodType', 'day')
    period = int(request.args.get('period', '1'))
    frequency_type = request.args.get('frequencyType', 'minute')
    frequency = int(request.args.get('frequency', '1'))  # Default to 1 minute
    
    try:
        # Calculate date range for Polygon.io API
        # Polygon.io requires from_date and to_date in YYYY-MM-DD format
        import pytz
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        
        # Calculate end date (today)
        to_date = now_et.date()
        
        # Calculate start date based on period_value and period_type
        if period_type == 'day':
            from_date = to_date - timedelta(days=period - 1)  # -1 because we include today
        elif period_type == 'week':
            from_date = to_date - timedelta(weeks=period - 1)
        elif period_type == 'month':
            from_date = to_date - timedelta(days=30 * (period - 1))
        elif period_type == 'year':
            from_date = to_date - timedelta(days=365 * (period - 1))
        else:
            from_date = to_date - timedelta(days=period - 1)
        
        # Map frequency_type to Polygon timespan
        timespan = 'minute' if frequency_type == 'minute' else 'day'
        
        # Request historical data from Polygon.io
        logger.info(f"Fetching data from Polygon.io for {symbol}: {from_date} to {to_date}, frequency: {frequency}min")
        data = polygon_api_request(
            symbol=symbol.upper(),
            multiplier=frequency,
            timespan=timespan,
            from_date=from_date.strftime('%Y-%m-%d'),
            to_date=to_date.strftime('%Y-%m-%d')
        )
        
        # Convert to DataFrame if candles are present
        if 'candles' in data:
            if not data['candles'] or len(data['candles']) == 0:
                return jsonify({
                    "error": "No candle data available",
                    "symbol": symbol,
                    "message": "Historical data request returned empty candles array"
                }), 404
            
            # Process candles - handle both dict and array formats
            candles = data['candles']
            
            if candles and isinstance(candles[0], dict):
                # Dictionary format - use directly
                df = pd.DataFrame(candles)
                if 'datetime' in df.columns:
                    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                elif 'time' in df.columns:
                    df['datetime'] = pd.to_datetime(df['time'], unit='ms')
                    df = df.rename(columns={'time': 'datetime'})
            else:
                # Array format - auto-detect column order
                df = pd.DataFrame(candles)
                if len(df.columns) == 6:
                    raw_values = [float(df.iloc[0, i]) for i in range(6)]
                    datetime_idx = raw_values.index(max(raw_values))
                    non_datetime = [(i, v) for i, v in enumerate(raw_values) if i != datetime_idx]
                    volume_candidates = [(i, v) for i, v in non_datetime if 1e6 <= v < 1e10]
                    volume_idx = volume_candidates[0][0] if volume_candidates else non_datetime[-1][0]
                    price_indices = [i for i in range(6) if i not in [datetime_idx, volume_idx]]
                    price_vals = [(i, raw_values[i]) for i in price_indices]
                    price_vals.sort(key=lambda x: x[1])
                    low_idx = price_vals[0][0]
                    high_idx = price_vals[-1][0]
                    open_idx = price_vals[1][0] if len(price_vals) > 1 else price_indices[0]
                    close_idx = price_vals[2][0] if len(price_vals) > 2 else price_indices[1]
                    col_map = [''] * 6
                    col_map[datetime_idx] = 'datetime'
                    col_map[open_idx] = 'open'
                    col_map[high_idx] = 'high'
                    col_map[low_idx] = 'low'
                    col_map[close_idx] = 'close'
                    col_map[volume_idx] = 'volume'
                    df.columns = col_map
                    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                else:
                    logger.error(f"Unexpected candle format: {len(df.columns)} columns")
                    return jsonify({
                        "error": "Unexpected data format from API",
                        "columns_count": len(df.columns)
                    }), 500
            
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Calculate indicators
            engine = OVStrategyEngine()
            df = engine.calculate_indicators(df)
            
            # Check if we have enough data for indicators
            if len(df) < 200:  # Need at least 200 periods for SMA200
                logger.warning(f"Insufficient data for {symbol}: only {len(df)} candles (need 200+)")
                return jsonify({
                    "symbol": symbol,
                    "candles_count": len(df),
                    "warning": f"Insufficient data for full indicator calculation (need 200+ candles, got {len(df)})",
                    "summary": engine.get_market_summary(df),  # Will handle missing indicators gracefully
                    "setup": None
                }), 200
            
            # Save to CSV
            csv_path = Path(f"data/{symbol}_{datetime.now().strftime('%Y%m%d')}.csv")
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(csv_path, index=False)
            
            logger.info(f"Retrieved and processed historical data for {symbol}")
            
            # Return summary
            try:
                summary = engine.get_market_summary(df)
                setup = engine.identify_setup(df)
            except Exception as e:
                logger.error(f"Error generating summary/setup for {symbol}: {e}")
                summary = engine.get_market_summary(df)  # Try summary only
                setup = None
            
            return jsonify({
                "symbol": symbol,
                "candles_count": len(df),
                "summary": summary,
                "setup": setup,
                "csv_path": str(csv_path)
            }), 200
        
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get historical data for {symbol}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@quotes_bp.route('/analyze/<symbol>', methods=['GET'])
def analyze_symbol(symbol: str):
    """
    Get quote, historical data, and strategy analysis for a symbol.
    Historical data uses Polygon.io, quotes use Schwab API.
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Get historical data from Polygon.io
        import pytz
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        to_date = now_et.date()
        from_date = to_date - timedelta(days=0)  # Today's data
        
        # Try frequency=1 first, fallback to frequency=5 if needed
        frequency = 1
        try:
            logger.info(f"Fetching data from Polygon.io for {symbol}: {from_date} to {to_date}, frequency: {frequency}min")
            data = polygon_api_request(
                symbol=symbol.upper(),
                multiplier=frequency,
                timespan='minute',
                from_date=from_date.strftime('%Y-%m-%d'),
                to_date=to_date.strftime('%Y-%m-%d')
            )
        except Exception as e:
            # If frequency=1 fails, try frequency=5
            logger.warning(f"Frequency=1 failed, trying frequency=5: {e}")
            frequency = 5
            try:
                data = polygon_api_request(
                    symbol=symbol.upper(),
                    multiplier=frequency,
                    timespan='minute',
                    from_date=from_date.strftime('%Y-%m-%d'),
                    to_date=to_date.strftime('%Y-%m-%d')
                )
            except Exception as e2:
                logger.error(f"Historical data request failed with both frequencies: {e2}")
                return jsonify({
                    "error": "Failed to retrieve historical data",
                    "details": str(e2),
                    "symbol": symbol,
                    "suggestion": "Check if market is open or try a different symbol"
                }), 500
        
        # Log the response structure for debugging
        logger.info(f"Historical data response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        if 'candles' not in data:
            logger.warning(f"No 'candles' key in response. Response: {data}")
            return jsonify({
                "error": "No historical data available",
                "symbol": symbol,
                "response": data,
                "suggestion": "Market may be closed or symbol may be invalid. Try during market hours (9:30 AM - 4:00 PM ET)"
            }), 404
        
        candles = data.get('candles', [])
        if not candles or len(candles) == 0:
            logger.warning(f"Empty candles array for {symbol}. Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Try getting data for previous day if today has no data
            # This can happen if market is closed or it's before market open
            logger.info(f"Trying to get data for previous day for {symbol}")
            try:
                from_date_prev = to_date - timedelta(days=1)
                data_prev = polygon_api_request(
                    symbol=symbol.upper(),
                    multiplier=5,
                    timespan='minute',
                    from_date=from_date_prev.strftime('%Y-%m-%d'),
                    to_date=from_date_prev.strftime('%Y-%m-%d')
                )
                candles_prev = data_prev.get('candles', [])
                
                if candles_prev and len(candles_prev) > 0:
                    logger.info(f"Found data for previous day, using that instead")
                    candles = candles_prev
                    data['candles'] = candles
                else:
                    return jsonify({
                        "error": "No historical data available",
                        "symbol": symbol,
                        "reason": "Empty candles array in API response for both today and previous day",
                        "suggestion": "Market may be closed, symbol may be invalid, or no trading data available. Try during market hours (9:30 AM - 4:00 PM ET) or verify the symbol is correct"
                    }), 404
            except Exception as e:
                logger.warning(f"Failed to get previous day data: {e}")
                return jsonify({
                    "error": "No historical data available",
                    "symbol": symbol,
                    "reason": "Empty candles array in API response",
                    "suggestion": "Market may be closed or no data for this symbol. Try during market hours (9:30 AM - 4:00 PM ET)"
                }), 404
        
        # Process data
        # Schwab API returns candles as list of arrays: [datetime, open, high, low, close, volume]
        candles = data['candles']
        
        if not candles or len(candles) == 0:
            return jsonify({"error": "No candle data in response"}), 404
        
        # Log first candle to understand structure
        logger.info(f"First candle sample (raw): {candles[0] if candles else 'None'}")
        logger.info(f"Candle type: {type(candles[0])}, length: {len(candles[0]) if isinstance(candles[0], (list, tuple)) else 'N/A'}")
        
        # Check if candles are dictionaries or arrays
        if isinstance(candles[0], dict):
            # Dictionary format - use directly
            df = pd.DataFrame(candles)
            # Ensure column names are correct
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
            elif 'time' in df.columns:
                df['datetime'] = pd.to_datetime(df['time'], unit='ms')
                df = df.rename(columns={'time': 'datetime'})
        else:
            # Array format - Schwab returns: [datetime, open, high, low, close, volume]
            # But we need to detect the actual order
            df = pd.DataFrame(candles)
            if len(df.columns) == 6:
                # Log raw values to help debug
                logger.info(f"Raw candle values: {[df.iloc[0, i] for i in range(6)]}")
                
                # Try to auto-detect column order by analyzing values
                # datetime: very large (timestamp in ms, 13 digits, > 1e12)
                # prices: moderate (usually $1-$1000, sometimes up to $5000)
                # volume: large but reasonable (usually 1e6 to 1e9)
                
                raw_values = [float(df.iloc[0, i]) for i in range(6)]
                
                # Find datetime (largest value, looks like timestamp)
                datetime_idx = raw_values.index(max(raw_values))
                
                # Find volume (large but not timestamp, typically 1e6-1e9 range)
                non_datetime = [(i, v) for i, v in enumerate(raw_values) if i != datetime_idx]
                volume_candidates = [(i, v) for i, v in non_datetime if 1e6 <= v < 1e10]
                volume_idx = volume_candidates[0][0] if volume_candidates else non_datetime[-1][0]
                
                # Remaining 4 are prices
                price_indices = [i for i in range(6) if i not in [datetime_idx, volume_idx]]
                price_vals = [(i, raw_values[i]) for i in price_indices]
                price_vals.sort(key=lambda x: x[1])
                
                # Assign: lowest = low, highest = high, middle two = open/close
                low_idx = price_vals[0][0]
                high_idx = price_vals[-1][0]
                open_idx = price_vals[1][0] if len(price_vals) > 1 else price_indices[0]
                close_idx = price_vals[2][0] if len(price_vals) > 2 else price_indices[1]
                
                # Create column mapping
                col_map = [''] * 6
                col_map[datetime_idx] = 'datetime'
                col_map[open_idx] = 'open'
                col_map[high_idx] = 'high'
                col_map[low_idx] = 'low'
                col_map[close_idx] = 'close'
                col_map[volume_idx] = 'volume'
                
                logger.info(f"Auto-detected column order: {col_map}")
                df.columns = col_map
                df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
            else:
                logger.error(f"Unexpected candle format: {len(df.columns)} columns. First row: {candles[0]}")
                return jsonify({
                    "error": "Unexpected data format from API",
                    "columns_count": len(df.columns),
                    "sample": candles[0] if candles else None
                }), 500
        
        # Ensure we have the required columns with correct types
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                logger.error(f"Missing required column: {col}. Available columns: {df.columns.tolist()}")
                return jsonify({"error": f"Missing required column: {col}"}), 500
            # Convert to numeric
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Validate and fix column order if needed
        # Check if prices look reasonable (most stocks are $1-$1000 range)
        if len(df) > 0:
            sample_close = float(df['close'].iloc[0])
            sample_volume = float(df['volume'].iloc[0])
            
            # If close price is suspiciously high (>$10,000) and volume looks like a timestamp
            if sample_close > 10000 and sample_volume > 1000000000:
                logger.warning(f"Detected misaligned columns: close={sample_close}, volume={sample_volume}")
                logger.warning("Original candle structure might be different. Attempting to fix...")
                
                # Rebuild DataFrame - Schwab might return: [datetime, open, high, low, close, volume]
                # But if misaligned, try different orders
                df_new = pd.DataFrame(candles)
                
                # Try standard order first
                if len(df_new.columns) == 6:
                    # Common API formats to try - Schwab might use different orders
                    orders_to_try = [
                        ['datetime', 'open', 'high', 'low', 'close', 'volume'],  # Standard
                        ['datetime', 'close', 'high', 'low', 'open', 'volume'],  # Close first  
                        ['volume', 'close', 'low', 'high', 'open', 'datetime'],  # Reversed
                        ['datetime', 'volume', 'open', 'high', 'low', 'close'],  # Volume second
                        ['open', 'high', 'low', 'close', 'volume', 'datetime'],  # Datetime last
                        ['volume', 'open', 'high', 'low', 'close', 'datetime'],  # Volume first
                    ]
                    
                    for col_order in orders_to_try:
                        df_test = df_new.copy()
                        df_test.columns = col_order
                        df_test['datetime'] = pd.to_datetime(df_test['datetime'], unit='ms')
                        for col in ['open', 'high', 'low', 'close', 'volume']:
                            df_test[col] = pd.to_numeric(df_test[col], errors='coerce')
                        
                        test_close = float(df_test['close'].iloc[0])
                        test_volume = float(df_test['volume'].iloc[0])
                        
                        # Check if this order makes sense
                        if 1 < test_close < 10000 and 1000 < test_volume < 10000000000:
                            logger.info(f"Fixed column order. Using: {col_order}")
                            df = df_test
                            break
                    else:
                        logger.error("Could not determine correct column order")
                        return jsonify({
                            "error": "Unable to parse candle data - column order unclear",
                            "sample": candles[0] if candles else None
                        }), 500
        
        # Log first row for debugging
        logger.info(f"Processed {len(df)} candles. Sample: close={df['close'].iloc[0]:.2f}, volume={df['volume'].iloc[0]}")
        
        # Calculate indicators and identify setup
        engine = OVStrategyEngine()
        df = engine.calculate_indicators(df)
        
        # Get summary (handles missing indicators gracefully)
        try:
            summary = engine.get_market_summary(df)
            # Always check fantastics, even if no setup is found
            fantastics = engine.check_4_fantastics(df) if len(df) >= 200 else {
                "fantastic_1": False,
                "fantastic_2": False,
                "fantastic_3": False,
                "fantastic_4": False,
                "all_fantastics": False
            }
            setup = engine.identify_setup(df) if len(df) >= 200 else None
        except Exception as e:
            logger.error(f"Error generating summary/setup for {symbol}: {e}")
            summary = engine.get_market_summary(df)  # Will handle missing indicators
            # Try to get fantastics even if setup fails
            try:
                fantastics = engine.check_4_fantastics(df) if len(df) >= 200 else {
                    "fantastic_1": False,
                    "fantastic_2": False,
                    "fantastic_3": False,
                    "fantastic_4": False,
                    "all_fantastics": False
                }
            except:
                fantastics = {
                    "fantastic_1": False,
                    "fantastic_2": False,
                    "fantastic_3": False,
                    "fantastic_4": False,
                    "all_fantastics": False
                }
            setup = None
        
        # Perform AI analysis
        ai_signal = None
        ai_error = None
        try:
            from ai.analyze import TradingAIAnalyzer
            ai_analyzer = TradingAIAnalyzer()
            ai_signal = ai_analyzer.analyze_market_data(symbol, summary, setup)
            logger.info(f"AI analysis completed for {symbol}: {ai_signal.get('action', 'NONE')}")
        except Exception as e:
            logger.error(f"AI analysis failed for {symbol}: {e}")
            ai_error = str(e)
            # Don't fail the entire request if AI fails
        
        return jsonify({
            "symbol": symbol,
            "summary": summary,
            "setup": setup,
            "fantastics": fantastics,  # Always include fantastics, even if setup is None
            "ai_signal": ai_signal,  # AI analysis result
            "ai_error": ai_error,  # AI error if any
            "data_points": len(df),
            "warning": "Insufficient data for full analysis" if len(df) < 200 else None
        }), 200
    except Exception as e:
        # Note: Historical data uses Polygon (no auth needed), but quotes use Schwab (auth required)
        # If 401 error, it's likely from the quote endpoint, try to refresh token
        if "401" in str(e) or "Unauthorized" in str(e):
            logger.warning("401 error detected, attempting token refresh...")
            try:
                from api.auth import refresh_access_token
                if tokens.get('refresh_token'):
                    new_tokens = refresh_access_token(tokens['refresh_token'])
                    save_tokens(new_tokens)
                    logger.info("Token refreshed successfully. Please retry the request.")
                    return jsonify({
                        "symbol": symbol,
                        "message": "Token refreshed successfully. Please retry the request.",
                        "re_auth_required": False
                    }), 200
                else:
                    return jsonify({
                        "error": "Token expired. Please re-authenticate.",
                        "re_auth_url": "/auth/login"
                    }), 401
            except Exception as refresh_error:
                logger.error(f"Token refresh failed: {refresh_error}")
                return jsonify({
                    "error": "Token expired and refresh failed. Please re-authenticate.",
                    "re_auth_url": "/auth/login"
                }), 401
        
        logger.error(f"Failed to analyze {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# Option Chains Endpoints
# ============================================================================

@quotes_bp.route('/options/chains', methods=['GET'])
def get_option_chains():
    """
    Get option chain for an optionable symbol.
    Schwab API: GET /chains
    
    Query params:
        symbol: Optionable symbol (e.g., 'AAPL')
        contractType: CALL, PUT, or ALL
        strikeCount: Number of strikes to return
        includeQuotes: Include quotes in response
        strategy: SINGLE, ANALYTICAL, COVERED, VERTICAL, CALENDAR, STRANGLE, STRADDLE, BUTTERFLY, CONDOR, DIAGONAL, COLLAR, ROLL
        interval: Strike interval
        strike: Strike price
        range: ITM, NTM, OTM, SAK, SBK, SNK, ALL
        fromDate: Start date (YYYY-MM-DD)
        toDate: End date (YYYY-MM-DD)
        volatility: Volatility
        underlyingPrice: Underlying price
        interestRate: Interest rate
        daysToExpiration: Days to expiration
        expMonth: Expiration month
        optionType: S (Standard), NS (Non-standard)
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({"error": "symbol parameter required"}), 400
    
    try:
        params = {
            "symbol": symbol,
            "contractType": request.args.get('contractType', 'ALL'),
            "strikeCount": request.args.get('strikeCount', '10'),
            "includeQuotes": request.args.get('includeQuotes', 'TRUE'),
            "strategy": request.args.get('strategy', 'SINGLE'),
            "interval": request.args.get('interval'),
            "strike": request.args.get('strike'),
            "range": request.args.get('range', 'ALL'),
            "fromDate": request.args.get('fromDate'),
            "toDate": request.args.get('toDate'),
            "volatility": request.args.get('volatility'),
            "underlyingPrice": request.args.get('underlyingPrice'),
            "interestRate": request.args.get('interestRate'),
            "daysToExpiration": request.args.get('daysToExpiration'),
            "expMonth": request.args.get('expMonth'),
            "optionType": request.args.get('optionType', 'S')
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        response = schwab_api_request("GET", SCHWAB_CHAINS_URL, tokens['access_token'], params=params)
        data = response.json()
        
        logger.info(f"Retrieved option chain for {symbol}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get option chain: {e}")
        return jsonify({"error": str(e)}), 500

@quotes_bp.route('/options/expiration-chain', methods=['GET'])
def get_expiration_chain():
    """
    Get option expiration chain for an optionable symbol.
    Schwab API: GET /expirationchain
    
    Query params:
        symbol: Optionable symbol (e.g., 'AAPL')
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({"error": "symbol parameter required"}), 400
    
    try:
        params = {"symbol": symbol}
        response = schwab_api_request("GET", SCHWAB_EXPIRATION_CHAIN_URL, tokens['access_token'], params=params)
        data = response.json()
        
        logger.info(f"Retrieved expiration chain for {symbol}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get expiration chain: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# Movers Endpoints
# ============================================================================

@quotes_bp.route('/movers/<symbol_id>', methods=['GET'])
def get_movers(symbol_id: str):
    """
    Get movers for a specific index.
    Schwab API: GET /movers/{symbol_id}
    
    Args:
        symbol_id: Index symbol (e.g., '$DJI' for Dow Jones, '$SPX.X' for S&P 500)
    
    Query params:
        direction: up, down
        change: percent, value
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    direction = request.args.get('direction', 'up')  # up or down
    change = request.args.get('change', 'percent')  # percent or value
    
    try:
        params = {
            "direction": direction,
            "change": change
        }
        
        url = f"{SCHWAB_MOVERS_URL}/{symbol_id}"
        response = schwab_api_request("GET", url, tokens['access_token'], params=params)
        data = response.json()
        
        logger.info(f"Retrieved movers for {symbol_id}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get movers for {symbol_id}: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# Market Hours Endpoints
# ============================================================================

@quotes_bp.route('/markets', methods=['GET'])
def get_markets():
    """
    Get market hours for different markets.
    Schwab API: GET /markets
    
    Query params:
        market: EQUITY, OPTION, FUTURE, BOND, FOREX
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    market = request.args.get('market')
    
    try:
        params = {}
        if market:
            params['market'] = market
        
        response = schwab_api_request("GET", SCHWAB_MARKETS_URL, tokens['access_token'], params=params)
        data = response.json()
        
        logger.info("Retrieved market hours")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get market hours: {e}")
        return jsonify({"error": str(e)}), 500

@quotes_bp.route('/markets/<market_id>', methods=['GET'])
def get_market(market_id: str):
    """
    Get market hours for a single market.
    Schwab API: GET /markets/{market_id}
    
    Args:
        market_id: Market identifier (e.g., 'EQUITY', 'OPTION')
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_MARKETS_URL}/{market_id}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved market hours for {market_id}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get market hours for {market_id}: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# Instruments Endpoints
# ============================================================================

@quotes_bp.route('/instruments', methods=['GET'])
def get_instruments():
    """
    Get instruments by symbols and projections.
    Schwab API: GET /instruments
    
    Query params:
        symbol: Symbol to search for
        projection: symbol-search, symbol-regex, desc-search, desc-regex, fundamental
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    symbol = request.args.get('symbol')
    projection = request.args.get('projection', 'symbol-search')
    
    if not symbol:
        return jsonify({"error": "symbol parameter required"}), 400
    
    try:
        params = {
            "symbol": symbol,
            "projection": projection
        }
        
        response = schwab_api_request("GET", SCHWAB_INSTRUMENTS_URL, tokens['access_token'], params=params)
        data = response.json()
        
        logger.info(f"Retrieved instruments for {symbol}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get instruments: {e}")
        return jsonify({"error": str(e)}), 500

@quotes_bp.route('/instruments/<cusip_id>', methods=['GET'])
def get_instrument(cusip_id: str):
    """
    Get instrument by specific CUSIP.
    Schwab API: GET /instruments/{cusip_id}
    
    Args:
        cusip_id: CUSIP identifier
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_INSTRUMENTS_URL}/{cusip_id}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved instrument for CUSIP {cusip_id}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get instrument for CUSIP {cusip_id}: {e}")
        return jsonify({"error": str(e)}), 500

