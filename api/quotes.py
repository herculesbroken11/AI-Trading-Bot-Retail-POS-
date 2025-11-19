"""
Market data and quotes API endpoints.
"""
import os
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
from utils.logger import setup_logger
from utils.helpers import load_tokens, schwab_api_request
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
    Get historical price data for a symbol.
    
    Query params:
        periodType: day, month, year, ytd
        period: 1, 2, 3, 4, 5, 10, 15, 20
        frequencyType: minute, daily, weekly, monthly
        frequency: 1, 5, 10, 15, 30
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Default parameters for intraday data
    period_type = request.args.get('periodType', 'day')
    period = request.args.get('period', '1')
    frequency_type = request.args.get('frequencyType', 'minute')
    frequency = request.args.get('frequency', '1')  # Default to 1 minute
    
    try:
        params = {
            "symbol": symbol,
            "periodType": period_type,
            "period": period,
            "frequencyType": frequency_type,
            "frequency": frequency,
            "needExtendedHoursData": "false"
        }
        
        url = SCHWAB_HISTORICAL_URL
        logger.info(f"Requesting historical data: {params}")
        response = schwab_api_request("GET", url, tokens['access_token'], params=params)
        data = response.json()
        
        # Convert to DataFrame if candles are present
        if 'candles' in data:
            df = pd.DataFrame(data['candles'])
            df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
            df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
            
            # Calculate indicators
            engine = OVStrategyEngine()
            df = engine.calculate_indicators(df)
            
            # Save to CSV
            csv_path = Path(f"data/{symbol}_{datetime.now().strftime('%Y%m%d')}.csv")
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(csv_path, index=False)
            
            logger.info(f"Retrieved and processed historical data for {symbol}")
            
            # Return summary
            summary = engine.get_market_summary(df)
            setup = engine.identify_setup(df)
            
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
        return jsonify({"error": str(e)}), 500

@quotes_bp.route('/analyze/<symbol>', methods=['GET'])
def analyze_symbol(symbol: str):
    """
    Get quote, historical data, and strategy analysis for a symbol.
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Get historical data - use valid parameter combinations
        # For intraday minute data, use periodType=day with appropriate period
        # Try with extended hours data if needed
        params = {
            "symbol": symbol,
            "periodType": "day",
            "period": "1",
            "frequencyType": "minute",
            "frequency": "1",  # Try frequency=1 first (more common)
            "needExtendedHoursData": "false"
        }
        
        url = SCHWAB_HISTORICAL_URL
        logger.info(f"Requesting historical data with params: {params}")
        
        try:
            response = schwab_api_request("GET", url, tokens['access_token'], params=params)
            data = response.json()
        except Exception as e:
            # If frequency=1 fails, try frequency=5
            if "frequency" in str(e).lower() or "400" in str(e):
                logger.warning("Frequency=1 failed, trying frequency=5")
                params["frequency"] = "5"
                response = schwab_api_request("GET", url, tokens['access_token'], params=params)
                data = response.json()
            else:
                raise
        
        if 'candles' not in data:
            return jsonify({"error": "No historical data available"}), 404
        
        # Process data
        df = pd.DataFrame(data['candles'])
        df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
        
        # Calculate indicators and identify setup
        engine = OVStrategyEngine()
        df = engine.calculate_indicators(df)
        summary = engine.get_market_summary(df)
        setup = engine.identify_setup(df)
        
        return jsonify({
            "symbol": symbol,
            "summary": summary,
            "setup": setup,
            "data_points": len(df)
        }), 200
    except Exception as e:
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

