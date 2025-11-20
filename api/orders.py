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
SCHWAB_TRANSACTIONS_URL = f"{SCHWAB_BASE_URL}/trader/v1/accounts"
SCHWAB_USER_PREF_URL = f"{SCHWAB_BASE_URL}/trader/v1/userPreference"

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
        
        # Place order - Correct URL: /accounts/{accountNumber}/orders
        account_id = data["accountId"]
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}/orders"
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

def execute_signal_helper(signal: dict, access_token: str) -> dict:
    """
    Helper function to execute a trading signal (can be called directly).
    
    Args:
        signal: Signal dictionary with symbol, action, entry, stop, target, etc.
        access_token: Schwab API access token
        
    Returns:
        Dictionary with status, order response, and account_id
    """
    # Validate signal
    is_valid, error_msg = validate_trade_signal(signal)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Get account ID if not provided
    if "accountId" not in signal:
        try:
            accounts_response = schwab_api_request("GET", SCHWAB_ACCOUNTS_URL, access_token)
            accounts = accounts_response.json()
            if accounts and len(accounts) > 0:
                signal["accountId"] = accounts[0].get("accountNumber", "")
            else:
                raise ValueError("No accounts found")
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            raise ValueError("Could not retrieve account")
    
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
    
    order_payload = build_order_payload(order_data)
    account_id = signal["accountId"]
    url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}/orders"
    response = schwab_api_request("POST", url, access_token, data=order_payload)
    order_response = response.json()
    
    logger.info(f"Signal executed: {signal['symbol']} {signal['action']} @ {signal['entry']}")
    
    # Log trade
    log_trade(order_data, order_response, signal)
    
    return {
        "status": "success",
        "order": order_response,
        "account_id": account_id,
        "signal": signal
    }

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
    
    try:
        result = execute_signal_helper(signal, tokens['access_token'])
        return jsonify({
            "message": "Signal executed successfully",
            "order": result["order"],
            "signal": result["signal"]
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to execute signal: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/account/<account_id>', methods=['GET'])
def get_account(account_id: str):
    """
    Get a specific account balance and positions.
    Schwab API: GET /accounts/{accountNumber}
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved account {account_id}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get account {account_id}: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/account-numbers', methods=['GET'])
def get_account_numbers():
    """
    Get list of account numbers and their encrypted values.
    Schwab API: GET /accounts/accountNumbers
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_ACCOUNTS_URL}/accountNumbers"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info("Retrieved account numbers")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get account numbers: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/all-orders', methods=['GET'])
def get_all_orders():
    """
    Get all orders for all accounts or a specific account.
    Schwab API: GET /orders or GET /accounts/{accountNumber}/orders
    
    Query params:
        accountId: Optional - if provided, get orders for specific account
        maxResults: Max number of results (default: 3000)
        fromEnteredTime: Start date/time
        toEnteredTime: End date/time
        status: Order status filter
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    account_id = request.args.get('accountId')
    max_results = request.args.get('maxResults', '3000')
    from_entered_time = request.args.get('fromEnteredTime')
    to_entered_time = request.args.get('toEnteredTime')
    status = request.args.get('status')  # AWAITING_PARENT_ORDER, AWAITING_CONDITION, etc.
    
    try:
        # If accountId provided, get orders for specific account
        if account_id:
            url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}/orders"
        else:
            # Get all orders for all accounts
            url = f"{SCHWAB_BASE_URL}/trader/v1/orders"
        
        params = {}
        if max_results:
            params['maxResults'] = max_results
        if from_entered_time:
            params['fromEnteredTime'] = from_entered_time
        if to_entered_time:
            params['toEnteredTime'] = to_entered_time
        if status:
            params['status'] = status
        
        response = schwab_api_request("GET", url, tokens['access_token'], params=params)
        data = response.json()
        
        logger.info(f"Retrieved orders for {'account ' + account_id if account_id else 'all accounts'}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/<account_id>/orders/<order_id>', methods=['GET'])
def get_order(account_id: str, order_id: str):
    """
    Get a specific order by its ID.
    Schwab API: GET /accounts/{accountNumber}/orders/{orderId}
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}/orders/{order_id}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved order {order_id} for account {account_id}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get order {order_id}: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/<account_id>/orders/<order_id>', methods=['DELETE'])
def cancel_order(account_id: str, order_id: str):
    """
    Cancel an order for a specific account.
    Schwab API: DELETE /accounts/{accountNumber}/orders/{orderId}
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}/orders/{order_id}"
        response = schwab_api_request("DELETE", url, tokens['access_token'])
        
        logger.info(f"Cancelled order {order_id} for account {account_id}")
        return jsonify({
            "message": "Order cancelled successfully",
            "order_id": order_id,
            "account_id": account_id
        }), 200
    except Exception as e:
        logger.error(f"Failed to cancel order {order_id}: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/<account_id>/orders/<order_id>', methods=['PUT'])
def replace_order(account_id: str, order_id: str):
    """
    Replace an order for a specific account.
    Schwab API: PUT /accounts/{accountNumber}/orders/{orderId}
    
    Request body: Same as place order
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        # Build order payload
        order_payload = build_order_payload(data)
        
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}/orders/{order_id}"
        response = schwab_api_request("PUT", url, tokens['access_token'], data=order_payload)
        order_response = response.json()
        
        logger.info(f"Replaced order {order_id} for account {account_id}")
        return jsonify({
            "message": "Order replaced successfully",
            "order": order_response
        }), 200
    except Exception as e:
        logger.error(f"Failed to replace order {order_id}: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/<account_id>/preview', methods=['POST'])
def preview_order(account_id: str):
    """
    Preview an order before placing it.
    Schwab API: POST /accounts/{accountNumber}/previewOrder
    
    Request body: Same as place order
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        # Build order payload
        order_payload = build_order_payload(data)
        
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}/previewOrder"
        response = schwab_api_request("POST", url, tokens['access_token'], data=order_payload)
        preview_response = response.json()
        
        logger.info(f"Previewed order for account {account_id}")
        return jsonify({
            "message": "Order preview generated",
            "preview": preview_response
        }), 200
    except Exception as e:
        logger.error(f"Failed to preview order: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/positions', methods=['GET'])
def get_positions():
    """
    Get current positions.
    Schwab API: GET /accounts/{accountNumber}/positions
    
    Query params:
        accountId: (optional) Account number. If not provided, uses first account.
    """
    import requests
    
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    account_id = request.args.get('accountId')
    
    # If no accountId provided, get the first account
    if not account_id:
        try:
            accounts_response = schwab_api_request("GET", SCHWAB_ACCOUNTS_URL, tokens['access_token'])
            accounts = accounts_response.json()
            if accounts and len(accounts) > 0:
                account_id = accounts[0].get("securitiesAccount", {}).get("accountNumber", "")
                if not account_id:
                    # Try alternative structure
                    account_id = accounts[0].get("accountNumber", "")
                logger.info(f"No accountId provided, using first account: {account_id}")
            else:
                return jsonify({"error": "No accounts found"}), 404
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            return jsonify({"error": "Could not retrieve account. Please provide accountId parameter."}), 500
    
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

# ============================================================================
# Transactions Endpoints
# ============================================================================

@orders_bp.route('/<account_id>/transactions', methods=['GET'])
def get_transactions(account_id: str):
    """
    Get all transactions for a specific account.
    Schwab API: GET /accounts/{accountNumber}/transactions
    
    Query params:
        startDate: YYYY-MM-DD
        endDate: YYYY-MM-DD
        symbol: Filter by symbol
        types: Transaction types (TRADE, RECEIVE_AND_DELIVER, DIVIDEND_OR_INTEREST, etc.)
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    symbol = request.args.get('symbol')
    transaction_types = request.args.get('types')
    
    try:
        url = f"{SCHWAB_TRANSACTIONS_URL}/{account_id}/transactions"
        
        params = {}
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date
        if symbol:
            params['symbol'] = symbol
        if transaction_types:
            params['types'] = transaction_types
        
        response = schwab_api_request("GET", url, tokens['access_token'], params=params)
        data = response.json()
        
        logger.info(f"Retrieved transactions for account {account_id}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get transactions: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/<account_id>/transactions/<transaction_id>', methods=['GET'])
def get_transaction(account_id: str, transaction_id: str):
    """
    Get specific transaction information for an account.
    Schwab API: GET /accounts/{accountNumber}/transactions/{transactionId}
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = f"{SCHWAB_TRANSACTIONS_URL}/{account_id}/transactions/{transaction_id}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved transaction {transaction_id} for account {account_id}")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get transaction {transaction_id}: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# User Preferences Endpoint
# ============================================================================

@orders_bp.route('/user-preference', methods=['GET'])
def get_user_preference():
    """
    Get user preference information.
    Schwab API: GET /userPreference
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        url = SCHWAB_USER_PREF_URL
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info("Retrieved user preferences")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get user preferences: {e}")
        return jsonify({"error": str(e)}), 500

