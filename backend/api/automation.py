"""
Automation API Endpoints
Control the automated trading scheduler.
"""
import threading
from flask import Blueprint, request, jsonify
from utils.logger import setup_logger
from core.scheduler import TradingScheduler

automation_bp = Blueprint('automation', __name__, url_prefix='/automation')
logger = setup_logger("automation")

# Global scheduler instance (can be imported by other modules)
scheduler = None
scheduler_thread = None

def start_automation():
    """Start automated trading scheduler (internal function)."""
    global scheduler, scheduler_thread
    
    if scheduler and scheduler.is_running:
        return jsonify({"status": "already_running"}), 200
    
    try:
        scheduler = TradingScheduler()
        scheduler_thread = threading.Thread(target=scheduler.start)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        logger.info("Automated trading started")
        return jsonify({
            "status": "started",
            "watchlist": scheduler.watchlist
        }), 200
    except Exception as e:
        logger.error(f"Failed to start automation: {e}")
        return jsonify({"error": str(e)}), 500

@automation_bp.route('/start', methods=['POST'])
def start_automation_endpoint():
    """Start automated trading scheduler (API endpoint)."""
    return start_automation()

@automation_bp.route('/stop', methods=['POST'])
def stop_automation():
    """Stop automated trading scheduler."""
    global scheduler
    
    if not scheduler or not scheduler.is_running:
        return jsonify({"status": "not_running"}), 200
    
    try:
        scheduler.stop()
        logger.info("Automated trading stopped")
        return jsonify({"status": "stopped"}), 200
    except Exception as e:
        logger.error(f"Failed to stop automation: {e}")
        return jsonify({"error": str(e)}), 500

@automation_bp.route('/status', methods=['GET'])
def automation_status():
    """Get automation status."""
    global scheduler
    
    if not scheduler:
        return jsonify({
            "status": "not_initialized",
            "running": False
        }), 200
    
    return jsonify({
        "status": "running" if scheduler.is_running else "stopped",
        "running": scheduler.is_running,
        "watchlist": scheduler.watchlist,
        "market_hours": scheduler.is_market_hours() if scheduler else False
    }), 200

@automation_bp.route('/watchlist', methods=['GET', 'POST'])
def manage_watchlist():
    """Get or update trading watchlist."""
    global scheduler
    
    if request.method == 'GET':
        if not scheduler:
            return jsonify({"watchlist": []}), 200
        return jsonify({"watchlist": scheduler.watchlist}), 200
    
    # POST - Update watchlist
    data = request.get_json()
    if not data or 'watchlist' not in data:
        return jsonify({"error": "watchlist required"}), 400
    
    try:
        watchlist = [s.strip().upper() for s in data['watchlist']]
        scheduler.watchlist = watchlist
        logger.info(f"Watchlist updated: {watchlist}")
        return jsonify({"watchlist": watchlist}), 200
    except Exception as e:
        logger.error(f"Failed to update watchlist: {e}")
        return jsonify({"error": str(e)}), 500

