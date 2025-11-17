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
SCHWAB_QUOTES_URL = f"{SCHWAB_BASE_URL}/marketdata/v1/quotes"
SCHWAB_HISTORICAL_URL = f"{SCHWAB_BASE_URL}/marketdata/v1/pricehistory"

@quotes_bp.route('/<symbol>', methods=['GET'])
def get_quote(symbol: str):
    """
    Get real-time quote for a symbol.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_QUOTES_URL}?symbols={symbol}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved quote for {symbol}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get quote for {symbol}: {e}")
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

