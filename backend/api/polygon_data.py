"""
Polygon.io Market Data API Endpoints
Provides access to numeric data and chart images for AI consumption.
"""
from flask import Blueprint, request, jsonify, send_file
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
from utils.logger import setup_logger
from utils.market_data_db import get_market_data, get_chart_metadata, detect_data_gaps
from core.chart_renderer import generate_chart_image, generate_chart_on_candle_complete
import pandas as pd

polygon_data_bp = Blueprint('polygon_data', __name__, url_prefix='/polygon')
logger = setup_logger("polygon_data")

@polygon_data_bp.route('/data/<symbol>', methods=['GET'])
def get_numeric_data(symbol: str):
    """
    Get numeric market data for AI analysis.
    
    Query params:
        timeframe: '1min', '5min', 'daily' (default: '1min')
        start_timestamp: Start timestamp in milliseconds (optional)
        end_timestamp: End timestamp in milliseconds (optional)
        limit: Maximum number of records (optional, default: 100)
    
    Returns:
        JSON with OHLCV data, VWAP, EMA 20, EMA 200
    """
    try:
        timeframe = request.args.get('timeframe', '1min')
        start_timestamp = request.args.get('start_timestamp', type=int)
        end_timestamp = request.args.get('end_timestamp', type=int)
        limit = request.args.get('limit', type=int, default=100)
        
        # Get data from database
        df = get_market_data(
            symbol=symbol.upper(),
            timeframe=timeframe,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            limit=limit
        )
        
        if df.empty:
            return jsonify({
                "error": f"No data available for {symbol} ({timeframe})",
                "symbol": symbol.upper(),
                "timeframe": timeframe
            }), 404
        
        # Convert to list of dictionaries
        data = []
        for idx, row in df.iterrows():
            data_point = {
                "timestamp": int(idx.timestamp() * 1000) if isinstance(idx, pd.Timestamp) else int(row.get('timestamp', 0)),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": int(row['volume'])
            }
            
            if 'vwap' in row and pd.notna(row['vwap']):
                data_point['vwap'] = float(row['vwap'])
            
            if 'ema_20' in row and pd.notna(row['ema_20']):
                data_point['ema_20'] = float(row['ema_20'])
            
            if 'ema_200' in row and pd.notna(row['ema_200']):
                data_point['ema_200'] = float(row['ema_200'])
            
            data.append(data_point)
        
        return jsonify({
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "count": len(data),
            "data": data
        }), 200
    
    except Exception as e:
        logger.error(f"Failed to get numeric data: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@polygon_data_bp.route('/chart/<symbol>', methods=['GET'])
def get_chart_image(symbol: str):
    """
    Get chart image for AI vision analysis.
    
    Query params:
        timeframe: '1min', '5min', 'daily' (default: '1min')
        timestamp: Specific timestamp in milliseconds (optional, defaults to latest)
        format: 'base64' or 'file' (default: 'base64')
    
    Returns:
        Chart image (base64 encoded or file)
    """
    try:
        timeframe = request.args.get('timeframe', '1min')
        timestamp = request.args.get('timestamp', type=int)
        format_type = request.args.get('format', 'base64')
        
        # Get data
        end_time = timestamp if timestamp else int(datetime.now().timestamp() * 1000)
        start_time = end_time - (24 * 60 * 60 * 1000)  # Last 24 hours
        
        df = get_market_data(
            symbol=symbol.upper(),
            timeframe=timeframe,
            start_timestamp=start_time,
            end_timestamp=end_time
        )
        
        if df.empty:
            return jsonify({
                "error": f"No data available for chart: {symbol} ({timeframe})"
            }), 404
        
        # Generate chart
        chart_result = generate_chart_image(
            df=df,
            symbol=symbol.upper(),
            timeframe=timeframe,
            timestamp=timestamp or end_time,
            save_to_disk=(format_type == 'file')
        )
        
        if not chart_result:
            return jsonify({"error": "Failed to generate chart"}), 500
        
        if format_type == 'base64':
            return jsonify({
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "timestamp": timestamp or end_time,
                "image": chart_result,
                "format": "base64"
            }), 200
        else:
            # Return file
            filepath = Path(chart_result)
            if filepath.exists():
                return send_file(str(filepath), mimetype='image/png')
            else:
                return jsonify({"error": "Chart file not found"}), 404
    
    except Exception as e:
        logger.error(f"Failed to get chart image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@polygon_data_bp.route('/charts/list', methods=['GET'])
def list_charts():
    """
    List available chart images.
    
    Query params:
        symbol: Filter by symbol (optional)
        timeframe: Filter by timeframe (optional)
        start_timestamp: Start timestamp (optional)
        end_timestamp: End timestamp (optional)
        limit: Maximum number of records (default: 50)
    
    Returns:
        List of chart metadata
    """
    try:
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe')
        start_timestamp = request.args.get('start_timestamp', type=int)
        end_timestamp = request.args.get('end_timestamp', type=int)
        limit = request.args.get('limit', type=int, default=50)
        
        charts = get_chart_metadata(
            symbol=symbol,
            timeframe=timeframe,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            limit=limit
        )
        
        return jsonify({
            "count": len(charts),
            "charts": charts
        }), 200
    
    except Exception as e:
        logger.error(f"Failed to list charts: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@polygon_data_bp.route('/gaps/<symbol>', methods=['GET'])
def get_data_gaps(symbol: str):
    """
    Detect data gaps for a symbol.
    
    Query params:
        timeframe: '1min', '5min', 'daily' (default: '1min')
        start_timestamp: Start timestamp in milliseconds
        end_timestamp: End timestamp in milliseconds
    
    Returns:
        List of detected gaps
    """
    try:
        timeframe = request.args.get('timeframe', '1min')
        start_timestamp = request.args.get('start_timestamp', type=int)
        end_timestamp = request.args.get('end_timestamp', type=int)
        
        if not start_timestamp or not end_timestamp:
            return jsonify({
                "error": "start_timestamp and end_timestamp are required"
            }), 400
        
        gaps = detect_data_gaps(
            symbol=symbol.upper(),
            timeframe=timeframe,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp
        )
        
        return jsonify({
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "gaps_count": len(gaps),
            "gaps": gaps
        }), 200
    
    except Exception as e:
        logger.error(f"Failed to detect gaps: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@polygon_data_bp.route('/generate/<symbol>', methods=['POST'])
def generate_chart_now(symbol: str):
    """
    Manually trigger chart generation for a symbol.
    
    Query params:
        timeframe: '1min', '5min', 'daily' (default: '1min')
    
    Returns:
        Chart filepath or base64
    """
    try:
        timeframe = request.args.get('timeframe', '1min')
        timestamp = int(datetime.now().timestamp() * 1000)
        
        filepath = generate_chart_on_candle_complete(
            symbol=symbol.upper(),
            timeframe=timeframe,
            timestamp=timestamp
        )
        
        if not filepath:
            return jsonify({"error": "Failed to generate chart"}), 500
        
        return jsonify({
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "timestamp": timestamp,
            "filepath": filepath,
            "status": "success"
        }), 200
    
    except Exception as e:
        logger.error(f"Failed to generate chart: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

