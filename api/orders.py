"""
Trade execution API endpoints.
"""
import os
import requests
from flask import Blueprint, request, jsonify
from datetime import datetime, time
from utils.logger import setup_logger
from utils.helpers import load_tokens, schwab_api_request, save_tokens
from utils.risk_control import (
    validate_trade_signal,
    calculate_position_size,
    MAX_TRADE_AMOUNT
)
from utils.helpers import parse_time

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')
logger = setup_logger("orders")

# Schwab API endpoints
SCHWAB_BASE_URL = "https://api.schwabapi.com"
SCHWAB_ACCOUNTS_URL = f"{SCHWAB_BASE_URL}/trader/v1/accounts"
SCHWAB_ORDERS_URL = f"{SCHWAB_BASE_URL}/trader/v1/orders"

@orders_bp.route('/accounts', methods=['GET'])
def get_accounts():
    """
    Get list of trading accounts.
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = SCHWAB_ACCOUNTS_URL
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info("Retrieved accounts")
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
                    logger.info("Retrieved accounts after token refresh")
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
        
        logger.error(f"Failed to get accounts: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/place', methods=['POST'])
def place_order():
    """
    Place a trade order.
    
    Request body:
    {
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 10,
        "orderType": "MARKET",
        "price": 150.00 (optional for MARKET orders),
        "stopPrice": 145.00 (optional),
        "accountId": "account_id"
    }
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Validate required fields
    required = ["symbol", "action", "quantity", "orderType", "accountId"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Check if market is open (basic check - should be enhanced)
    if not is_market_open():
        return jsonify({"error": "Market is closed"}), 400
    
    # Validate trade signal
    signal = {
        "action": data["action"],
        "symbol": data["symbol"],
        "entry": data.get("price", 0),
        "stop": data.get("stopPrice", 0),
        "target": data.get("targetPrice", 0)
    }
    
    is_valid, error_msg = validate_trade_signal(signal)
    if not is_valid:
        return jsonify({"error": error_msg}), 400
    
    try:
        # Build order payload for Schwab API
        order_payload = build_order_payload(data)
        
        # Place order
        account_id = data["accountId"]
        url = f"{SCHWAB_ORDERS_URL}/{account_id}/orders"
        response = schwab_api_request("POST", url, tokens['access_token'], data=order_payload)
        order_response = response.json()
        
        logger.info(f"Order placed: {data['symbol']} {data['action']} {data['quantity']}")
        
        # Log trade to CSV
        log_trade(data, order_response)
        
        return jsonify({
            "message": "Order placed successfully",
            "order": order_response
        }), 200
    except Exception as e:
        logger.error(f"Failed to place order: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/signal', methods=['POST'])
def execute_signal():
    """
    Execute a trading signal from AI analysis.
    
    Request body:
    {
        "symbol": "AAPL",
        "action": "BUY",
        "entry": 150.00,
        "stop": 145.00,
        "target": 160.00,
        "setup_type": "PULLBACK_LONG",
        "position_size": 10,
        "accountId": "account_id"
    }
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    signal = request.get_json()
    
    if not signal:
        return jsonify({"error": "No signal provided"}), 400
    
    # Validate signal
    is_valid, error_msg = validate_trade_signal(signal)
    if not is_valid:
        return jsonify({"error": error_msg}), 400
    
    # Get account ID if not provided
    if "accountId" not in signal:
        try:
            accounts_response = schwab_api_request("GET", SCHWAB_ACCOUNTS_URL, tokens['access_token'])
            accounts = accounts_response.json()
            if accounts and len(accounts) > 0:
                signal["accountId"] = accounts[0].get("accountNumber", "")
            else:
                return jsonify({"error": "No accounts found"}), 400
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            return jsonify({"error": "Could not retrieve account"}), 500
    
    # Calculate position size if not provided
    if "position_size" not in signal or signal["position_size"] == 0:
        # Get account value (simplified - should fetch actual account value)
        account_value = 10000  # Default
        signal["position_size"] = calculate_position_size(
            account_value,
            signal["entry"],
            signal["stop"],
            MAX_TRADE_AMOUNT
        )
    
    # Build order
    order_data = {
        "symbol": signal["symbol"],
        "action": signal["action"],
        "quantity": signal["position_size"],
        "orderType": "LIMIT",  # Use LIMIT for better execution
        "price": signal["entry"],
        "stopPrice": signal["stop"],
        "accountId": signal["accountId"]
    }
    
    try:
        order_payload = build_order_payload(order_data)
        account_id = signal["accountId"]
        url = f"{SCHWAB_ORDERS_URL}/{account_id}/orders"
        response = schwab_api_request("POST", url, tokens['access_token'], data=order_payload)
        order_response = response.json()
        
        logger.info(f"Signal executed: {signal['symbol']} {signal['action']} @ {signal['entry']}")
        
        # Log trade
        log_trade(order_data, order_response, signal)
        
        return jsonify({
            "message": "Signal executed successfully",
            "order": order_response,
            "signal": signal
        }), 200
    except Exception as e:
        logger.error(f"Failed to execute signal: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/positions', methods=['GET'])
def get_positions():
    """
    Get current positions.
    Schwab API: GET /accounts/{accountNumber}/positions
    """
    import requests
    
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    account_id = request.args.get('accountId')
    if not account_id:
        return jsonify({"error": "accountId required"}), 400
    
    try:
        # Try the positions endpoint
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}/positions"
        headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Accept": "application/json"
        }
        
        logger.info(f"Requesting positions from: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Positions request failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            
            # Try alternative: get account details which includes positions
            if response.status_code == 400:
                logger.warning("Direct positions endpoint failed, trying account details...")
                account_url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}"
                account_response = requests.get(account_url, headers=headers, timeout=30)
                if account_response.status_code == 200:
                    account_data = account_response.json()
                    # Extract positions from account data if available
                    positions = []
                    if isinstance(account_data, list) and len(account_data) > 0:
                        securities_account = account_data[0].get('securitiesAccount', {})
                        positions = securities_account.get('positions', [])
                    return jsonify({"positions": positions}), 200
            
            try:
                error_data = response.json()
                return jsonify({
                    "error": f"Schwab API error: {response.status_code}",
                    "details": error_data
                }), response.status_code
            except:
                return jsonify({
                    "error": f"Schwab API error: {response.status_code}",
                    "details": response.text[:500]
                }), response.status_code
        
        data = response.json()
        logger.info("Retrieved positions successfully")
        return jsonify(data), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception getting positions: {e}")
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return jsonify({"error": str(e)}), 500

def build_order_payload(data: dict) -> dict:
    """
    Build order payload for Schwab API.
    
    Args:
        data: Order data dictionary
        
    Returns:
        Formatted order payload
    """
    order_type = data.get("orderType", "MARKET").upper()
    
    payload = {
        "orderType": order_type,
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [{
            "instruction": data["action"],
            "quantity": data["quantity"],
            "instrument": {
                "symbol": data["symbol"],
                "assetType": "EQUITY"
            }
        }]
    }
    
    # Add price for LIMIT orders
    if order_type == "LIMIT" and "price" in data:
        payload["price"] = float(data["price"])
    
    # Add stop price for STOP orders
    if order_type == "STOP" and "stopPrice" in data:
        payload["stopPrice"] = float(data["stopPrice"])
    
    return payload

def is_market_open() -> bool:
    """
    Check if market is currently open (simplified check).
    Should be enhanced with actual market hours and holidays.
    """
    now = datetime.now()
    current_time = now.time()
    
    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = time(9, 30)
    market_close = time(16, 0)
    
    # Simple check (should account for timezone and holidays)
    return market_open <= current_time <= market_close

def log_trade(order_data: dict, order_response: dict, signal: dict = None):
    """
    Log trade to CSV file.
    
    Args:
        order_data: Order data
        order_response: Order response from API
        signal: Optional signal data
    """
    from pathlib import Path
    import csv
    
    csv_path = Path("data/trades.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_exists = csv_path.exists()
    
    with open(csv_path, 'a', newline='') as f:
        writer = csv.writer(f)
        
        if not file_exists:
            writer.writerow([
                "timestamp", "symbol", "action", "quantity", "price",
                "stop_price", "target_price", "order_id", "status",
                "setup_type", "entry", "stop", "target"
            ])
        
        writer.writerow([
            datetime.now().isoformat(),
            order_data.get("symbol"),
            order_data.get("action"),
            order_data.get("quantity"),
            order_data.get("price"),
            order_data.get("stopPrice"),
            signal.get("target") if signal else None,
            order_response.get("orderId", ""),
            order_response.get("status", ""),
            signal.get("setup_type") if signal else None,
            signal.get("entry") if signal else None,
            signal.get("stop") if signal else None,
            signal.get("target") if signal else None
        ])
    
    logger.info(f"Trade logged to {csv_path}")

