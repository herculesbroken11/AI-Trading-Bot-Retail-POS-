"""
Chart Data API Endpoints
Provides OHLCV data and indicators for real-time charting.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import pandas as pd
from utils.logger import setup_logger
from utils.helpers import get_valid_access_token, schwab_api_request
from api.quotes import SCHWAB_HISTORICAL_URL
from core.ov_engine import OVStrategyEngine

charts_bp = Blueprint('charts', __name__, url_prefix='/charts')
logger = setup_logger("charts")

# Initialize OV engine for indicator calculation
ov_engine = OVStrategyEngine()

@charts_bp.route('/data/<symbol>', methods=['GET'])
def get_chart_data(symbol: str):
    """
    Get chart data (OHLCV + indicators) for a symbol.
    
    Query params:
        period: 'day', 'week', 'month', 'year' (default: 'day')
        periodType: 'day', 'week', 'month', 'year' (default: 'day')
        frequencyType: 'minute', 'daily' (default: 'minute')
        frequency: 1, 5, 15, 30, 60 for minutes (default: 5)
        periodValue: number of periods (default: 1)
    
    Returns:
        JSON with candles, indicators, and metadata
    """
    try:
        access_token = get_valid_access_token()
        
        # Get query parameters
        period_type = request.args.get('periodType', 'day')
        period_value = int(request.args.get('periodValue', 1))
        frequency_type = request.args.get('frequencyType', 'minute')
        frequency = int(request.args.get('frequency', 5))
        
        # Build Schwab API request
        params = {
            'symbol': symbol.upper(),
            'periodType': period_type,
            'period': period_value,
            'frequencyType': frequency_type,
            'frequency': frequency
        }
        
        # Request historical data from Schwab (include premarket/extended hours)
        url = f"{SCHWAB_HISTORICAL_URL}?symbol={symbol.upper()}&periodType={period_type}&period={period_value}&frequencyType={frequency_type}&frequency={frequency}&needExtendedHoursData=true"
        response = schwab_api_request("GET", url, access_token)
        data = response.json()
        
        if not data or 'candles' not in data:
            return jsonify({"error": "No data available"}), 404
        
        candles = data['candles']
        if not candles or len(candles) == 0:
            return jsonify({"error": "Empty data"}), 404
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        
        # Handle datetime column
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
        elif 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='ms')
            df = df.rename(columns={'time': 'datetime'})
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Calculate indicators using OV engine
        df = ov_engine.calculate_indicators(df)
        
        # Convert to chart-friendly format
        chart_data = {
            'symbol': symbol.upper(),
            'candles': [],
            'indicators': {
                'sma_8': [],
                'sma_20': [],
                'sma_200': [],
                'rsi_14': [],
                'volume': []
            },
            'metadata': {
                'period_type': period_type,
                'frequency': frequency,
                'total_candles': len(df),
                'last_update': datetime.now().isoformat()
            }
        }
        
        # Format candles and indicators
        for idx, row in df.iterrows():
            candle = {
                'time': int(row['datetime'].timestamp() * 1000) if 'datetime' in row else None,
                'open': float(row['open']) if pd.notna(row.get('open')) else None,
                'high': float(row['high']) if pd.notna(row.get('high')) else None,
                'low': float(row['low']) if pd.notna(row.get('low')) else None,
                'close': float(row['close']) if pd.notna(row.get('close')) else None,
                'volume': float(row['volume']) if pd.notna(row.get('volume')) else None
            }
            chart_data['candles'].append(candle)
            
            # Add indicators
            if 'sma_8' in row and pd.notna(row['sma_8']):
                chart_data['indicators']['sma_8'].append({
                    'time': candle['time'],
                    'value': float(row['sma_8'])
                })
            
            if 'sma_20' in row and pd.notna(row['sma_20']):
                chart_data['indicators']['sma_20'].append({
                    'time': candle['time'],
                    'value': float(row['sma_20'])
                })
            
            if 'sma_200' in row and pd.notna(row['sma_200']):
                chart_data['indicators']['sma_200'].append({
                    'time': candle['time'],
                    'value': float(row['sma_200'])
                })
            
            if 'rsi_14' in row and pd.notna(row['rsi_14']):
                chart_data['indicators']['rsi_14'].append({
                    'time': candle['time'],
                    'value': float(row['rsi_14'])
                })
        
        logger.info(f"Chart data retrieved for {symbol}: {len(chart_data['candles'])} candles")
        return jsonify(chart_data), 200
        
    except Exception as e:
        logger.error(f"Failed to get chart data for {symbol}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@charts_bp.route('/setup/<symbol>', methods=['GET'])
def get_chart_with_setup(symbol: str):
    """
    Get chart data with current setup analysis (if any).
    Includes entry/stop/target levels from AI analysis.
    """
    try:
        # Get basic chart data
        chart_response = get_chart_data(symbol)
        if chart_response[1] != 200:
            return chart_response
        
        chart_data = chart_response[0].get_json()
        
        # Try to get current setup from scheduler (if available)
        try:
            from api.automation import scheduler
            if scheduler and scheduler.is_running:
                # Get latest setup for this symbol
                # This would require storing recent setups - for now return basic data
                pass
        except:
            pass
        
        return jsonify(chart_data), 200
        
    except Exception as e:
        logger.error(f"Failed to get chart with setup for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

