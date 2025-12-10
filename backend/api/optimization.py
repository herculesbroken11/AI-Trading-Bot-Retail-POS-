"""
Optimization API endpoints - Phase 7
Provides endpoints for viewing and managing optimization data.
"""
from flask import Blueprint, request, jsonify
from utils.helpers import get_valid_access_token
from utils.logger import setup_logger
from core.performance_analyzer import PerformanceAnalyzer

optimization_bp = Blueprint('optimization', __name__, url_prefix='/optimization')
logger = setup_logger("optimization")

@optimization_bp.route('/performance', methods=['GET'])
def get_performance():
    """
    Get performance analysis.
    
    Query params:
        days: Number of days to analyze (default: 30)
    """
    try:
        days = int(request.args.get('days', 30))
        
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze_performance(days=days)
        
        return jsonify(analysis), 200
        
    except Exception as e:
        logger.error(f"Failed to get performance: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@optimization_bp.route('/setup-weights', methods=['GET'])
def get_setup_weights():
    """Get current setup weights."""
    try:
        analyzer = PerformanceAnalyzer()
        weights = analyzer.setup_weights
        
        return jsonify({
            "setup_weights": weights,
            "description": "Higher weight = more likely to trade this setup type"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get setup weights: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@optimization_bp.route('/parameters', methods=['GET'])
def get_parameters():
    """Get optimized trading parameters."""
    try:
        analyzer = PerformanceAnalyzer()
        parameters = analyzer.get_optimized_parameters()
        
        return jsonify(parameters), 200
        
    except Exception as e:
        logger.error(f"Failed to get parameters: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@optimization_bp.route('/adjust-weights', methods=['POST'])
def adjust_weights():
    """
    Manually trigger setup weight adjustment.
    
    Body (optional):
        min_trades: Minimum trades needed to adjust (default: 10)
    """
    try:
        data = request.get_json() or {}
        min_trades = int(data.get('min_trades', 10))
        
        analyzer = PerformanceAnalyzer()
        new_weights = analyzer.adjust_setup_weights(min_trades=min_trades)
        
        return jsonify({
            "message": "Setup weights adjusted",
            "setup_weights": new_weights
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to adjust weights: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@optimization_bp.route('/optimize-parameters', methods=['POST'])
def optimize_parameters():
    """
    Manually trigger parameter optimization.
    Requires recent price data for volatility calculation.
    """
    try:
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({"error": "Not authenticated"}), 401
        
        # Get watchlist symbols from scheduler or environment
        import os
        from api.automation import scheduler
        
        if scheduler and scheduler.watchlist:
            watchlist = scheduler.watchlist
        else:
            # Fallback to environment variable
            watchlist_str = os.getenv("TRADING_WATCHLIST", "")
            if not watchlist_str:
                return jsonify({"error": "TRADING_WATCHLIST not found in environment. Please set it in .env file."}), 400
            watchlist = [s.strip().upper() for s in watchlist_str.split(",") if s.strip()]
        
        if not watchlist:
            return jsonify({"error": "TRADING_WATCHLIST is empty. Please set it in .env file."}), 400
        
        # Get recent prices for volatility calculation
        from api.quotes import SCHWAB_HISTORICAL_URL
        from utils.helpers import schwab_api_request
        
        recent_prices = []
        for symbol in watchlist[:5]:  # Use first 5 symbols
            try:
                url = f"{SCHWAB_HISTORICAL_URL}?symbol={symbol}&periodType=day&period=1&frequencyType=minute&frequency=5"
                response = schwab_api_request("GET", url, access_token)
                data = response.json()
                
                if isinstance(data, dict) and 'candles' in data:
                    prices = [c.get('close', 0) for c in data['candles'] if c.get('close')]
                    recent_prices.extend(prices)
            except Exception as e:
                logger.debug(f"Failed to get prices for {symbol}: {e}")
                continue
        
        if not recent_prices:
            return jsonify({"error": "No price data available"}), 400
        
        analyzer = PerformanceAnalyzer()
        recent_trades = analyzer.performance_data.get("trades", [])[-50:]
        
        optimized = analyzer.auto_tune_parameters(
            recent_prices=recent_prices,
            recent_trades=recent_trades
        )
        
        return jsonify({
            "message": "Parameters optimized",
            "parameters": optimized
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to optimize parameters: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@optimization_bp.route('/summary', methods=['GET'])
def get_summary():
    """Get optimization summary (weights, parameters, performance)."""
    try:
        analyzer = PerformanceAnalyzer()
        summary = analyzer.get_performance_summary()
        
        return jsonify(summary), 200
        
    except Exception as e:
        logger.error(f"Failed to get summary: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

