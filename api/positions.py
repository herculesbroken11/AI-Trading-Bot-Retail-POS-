"""
Position Management API Endpoints
"""
from flask import Blueprint, request, jsonify
from utils.logger import setup_logger
from core.position_manager import PositionManager
from utils.helpers import load_tokens

positions_bp = Blueprint('positions', __name__, url_prefix='/positions')
logger = setup_logger("positions")

position_manager = PositionManager()

@positions_bp.route('/active', methods=['GET'])
def get_active_positions():
    """Get all active positions being tracked."""
    try:
        positions = position_manager.load_active_positions()
        return jsonify({"positions": positions, "count": len(positions)}), 200
    except Exception as e:
        logger.error(f"Failed to get active positions: {e}")
        return jsonify({"error": str(e)}), 500

@positions_bp.route('/add', methods=['POST'])
def add_position():
    """Add a position to tracking."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON data required"}), 400
    
    required_fields = ['symbol', 'account_id', 'entry_price', 'stop_loss', 'quantity', 'direction']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} required"}), 400
    
    try:
        position_manager.add_position(data)
        return jsonify({"status": "added", "position": data}), 200
    except Exception as e:
        logger.error(f"Failed to add position: {e}")
        return jsonify({"error": str(e)}), 500

@positions_bp.route('/update/<symbol>/<account_id>', methods=['PUT'])
def update_position(symbol: str, account_id: str):
    """Update position data."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON data required"}), 400
    
    try:
        success = position_manager.update_position(symbol, account_id, data)
        if success:
            return jsonify({"status": "updated"}), 200
        else:
            return jsonify({"error": "Position not found"}), 404
    except Exception as e:
        logger.error(f"Failed to update position: {e}")
        return jsonify({"error": str(e)}), 500

@positions_bp.route('/remove/<symbol>/<account_id>', methods=['DELETE'])
def remove_position(symbol: str, account_id: str):
    """Remove position from tracking."""
    try:
        position_manager.remove_position(symbol, account_id)
        return jsonify({"status": "removed"}), 200
    except Exception as e:
        logger.error(f"Failed to remove position: {e}")
        return jsonify({"error": str(e)}), 500

@positions_bp.route('/close-all', methods=['POST'])
def close_all_positions():
    """Manually close all positions."""
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        closed = position_manager.close_all_positions()
        return jsonify({
            "status": "closed",
            "count": len(closed),
            "positions": closed
        }), 200
    except Exception as e:
        logger.error(f"Failed to close positions: {e}")
        return jsonify({"error": str(e)}), 500

@positions_bp.route('/update-prices', methods=['POST'])
def update_prices():
    """Update positions with current prices."""
    data = request.get_json()
    if not data or 'prices' not in data:
        return jsonify({"error": "prices dictionary required"}), 400
    
    try:
        position_manager.update_all_positions(data['prices'])
        return jsonify({"status": "updated"}), 200
    except Exception as e:
        logger.error(f"Failed to update prices: {e}")
        return jsonify({"error": str(e)}), 500

@positions_bp.route('/add-to/<symbol>/<account_id>', methods=['POST'])
def add_to_position(symbol: str, account_id: str):
    """Add shares to existing position (scaling)."""
    data = request.get_json()
    if not data or 'shares' not in data or 'price' not in data:
        return jsonify({"error": "shares and price required"}), 400
    
    positions = position_manager.load_active_positions()
    position = next(
        (p for p in positions if p.get('symbol') == symbol and p.get('account_id') == account_id),
        None
    )
    
    if not position:
        return jsonify({"error": "Position not found"}), 404
    
    try:
        position_manager.add_to_position(position, data['shares'], data['price'])
        position_manager.save_active_positions(positions)
        return jsonify({"status": "added", "position": position}), 200
    except Exception as e:
        logger.error(f"Failed to add to position: {e}")
        return jsonify({"error": str(e)}), 500

