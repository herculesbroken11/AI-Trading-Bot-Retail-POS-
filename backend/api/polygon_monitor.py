"""
Polygon.io Service Monitoring and Control API
Provides endpoints for monitoring service health, controlling service, and viewing status.
"""
import time
from flask import Blueprint, request, jsonify
from utils.logger import setup_logger
from core.polygon_service import get_polygon_service

polygon_monitor_bp = Blueprint('polygon_monitor', __name__, url_prefix='/polygon/monitor')
logger = setup_logger("polygon_monitor")

@polygon_monitor_bp.route('/status', methods=['GET'])
def get_service_status():
    """Get Polygon.io service status."""
    try:
        service = get_polygon_service()
        status = service.get_status()
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Failed to get service status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@polygon_monitor_bp.route('/start', methods=['POST'])
def start_service():
    """Start the Polygon.io market data service."""
    try:
        service = get_polygon_service()
        if service.is_running:
            return jsonify({
                "status": "already_running",
                "message": "Service is already running"
            }), 200
        
        service.start()
        return jsonify({
            "status": "started",
            "message": "Polygon.io service started successfully"
        }), 200
    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@polygon_monitor_bp.route('/stop', methods=['POST'])
def stop_service():
    """Stop the Polygon.io market data service."""
    try:
        service = get_polygon_service()
        if not service.is_running:
            return jsonify({
                "status": "not_running",
                "message": "Service is not running"
            }), 200
        
        service.stop()
        return jsonify({
            "status": "stopped",
            "message": "Polygon.io service stopped successfully"
        }), 200
    except Exception as e:
        logger.error(f"Failed to stop service: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@polygon_monitor_bp.route('/health', methods=['GET'])
def health_check():
    """Perform health check on Polygon.io service."""
    try:
        service = get_polygon_service()
        status = service.get_status()
        
        # Check if service is running and WebSocket is connected
        is_healthy = (
            status.get('running', False) and
            status.get('streamer_status', {}).get('connected', False) and
            status.get('streamer_status', {}).get('authenticated', False)
        )
        
        return jsonify({
            "healthy": is_healthy,
            "status": status,
            "timestamp": int(time.time() * 1000)
        }), 200 if is_healthy else 503
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            "healthy": False,
            "error": str(e)
        }), 503

@polygon_monitor_bp.route('/backfill/<symbol>', methods=['POST'])
def backfill_symbol(symbol: str):
    """Trigger historical data backfill for a symbol."""
    try:
        days = request.args.get('days', type=int, default=10)
        
        service = get_polygon_service()
        service.backfill_historical_data(symbol=symbol.upper(), days=days)
        
        return jsonify({
            "status": "success",
            "symbol": symbol.upper(),
            "days": days,
            "message": f"Backfill initiated for {symbol}"
        }), 200
    except Exception as e:
        logger.error(f"Failed to backfill: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

