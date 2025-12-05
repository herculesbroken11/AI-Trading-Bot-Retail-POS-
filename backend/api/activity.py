"""
Activity Log and Rules Verification API
Provides real-time activity logs and rule verification status.
"""
import os
import json
from flask import Blueprint, request, jsonify
from datetime import datetime
from pathlib import Path
from utils.logger import setup_logger
from api.automation import scheduler

activity_bp = Blueprint('activity', __name__, url_prefix='/activity')
logger = setup_logger("activity")

# In-memory activity log (in production, use Redis or database)
activity_log = []

def add_activity_log(log_type, message, rule=None, symbol=None):
    """Add entry to activity log."""
    entry = {
        "time": datetime.now().isoformat(),
        "type": log_type,
        "message": message,
        "rule": rule,
        "symbol": symbol
    }
    activity_log.append(entry)
    # Keep only last 100 entries
    if len(activity_log) > 100:
        activity_log.pop(0)
    return entry

@activity_bp.route('/logs', methods=['GET'])
def get_activity_logs():
    """
    Get recent activity logs.
    
    Query params:
        limit: Number of logs to return (default: 50)
    """
    try:
        limit = int(request.args.get('limit', 50))
        logs = activity_log[-limit:] if activity_log else []
        
        # Format time for display
        for log in logs:
            try:
                dt = datetime.fromisoformat(log['time'])
                log['time'] = dt.strftime('%H:%M:%S')
            except:
                pass
        
        return jsonify({
            "logs": logs,
            "total": len(activity_log)
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get activity logs: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@activity_bp.route('/rules/status', methods=['GET'])
def get_rules_status():
    """
    Get current status of OV trading rules.
    """
    try:
        # Import scheduler from automation module
        from api.automation import scheduler
        
        is_running = scheduler and scheduler.is_running if scheduler else False
        is_market_hours = scheduler.is_market_hours() if scheduler else False
        
        # Get current time
        now = datetime.now()
        hour = now.hour
        
        rules = [
            {
                "name": "4 Fantastics",
                "description": "Price above SMA200, SMA8 > SMA20, Volume > Average, RSI in range",
                "status": "monitoring" if is_running else "idle"
            },
            {
                "name": "75% Candle Rule",
                "description": "Candle body must be at least 75% of total range",
                "status": "monitoring" if is_running else "idle"
            },
            {
                "name": "Whale Setup",
                "description": "Large volume spike with price movement above SMA8",
                "status": "monitoring" if is_running else "idle"
            },
            {
                "name": "Kamikaze Setup",
                "description": "Rapid price reversal after strong move",
                "status": "monitoring" if is_running else "idle"
            },
            {
                "name": "RBI Setup",
                "description": "Rapid Breakout with volume confirmation",
                "status": "monitoring" if is_running else "idle"
            },
            {
                "name": "GBI Setup",
                "description": "Gap Breakout with continuation",
                "status": "monitoring" if is_running else "idle"
            },
            {
                "name": "Risk Control",
                "description": "Maximum $300 loss per trade enforced",
                "status": "active" if is_running else "idle"
            },
            {
                "name": "Stop Loss",
                "description": "ATR-based stop loss calculated for each trade",
                "status": "active" if is_running else "idle"
            },
            {
                "name": "Take Profit",
                "description": "ATR-based take profit targets set",
                "status": "active" if is_running else "idle"
            },
            {
                "name": "Auto-Close",
                "description": "All positions closed at 4:00 PM ET",
                "status": "active" if hour >= 16 else ("pending" if is_running else "idle")
            },
            {
                "name": "Position Sizing",
                "description": "Position size calculated based on risk and ATR",
                "status": "active" if is_running else "idle"
            },
            {
                "name": "Trailing Stops",
                "description": "Trailing stops updated every minute",
                "status": "active" if is_running and is_market_hours else "idle"
            }
        ]
        
        return jsonify({
            "rules": rules,
            "automation_running": is_running,
            "market_hours": is_market_hours,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get rules status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Initialize with some default logs
add_activity_log("info", "Activity log system initialized")
add_activity_log("info", "Waiting for automation to start...")

