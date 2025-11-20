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
        
        # According to Schwab API docs:
        # - Successful order placement returns 201 (not 200)
        # - Response body is empty
        # - Location header contains link to newly created order
        # - Schwab-Client-CorrelId header contains correlation ID
        
        location = response.headers.get('Location', '')
        correl_id = response.headers.get('Schwab-Client-CorrelId', '')
        
        logger.info(f"Order placed: {data['symbol']} {data['action']} {data['quantity']} (Location: {location})")
        
        # Try to parse response if it has content, otherwise use empty dict
        try:
            order_response = response.json() if response.text else {}
        except:
            order_response = {}
        
        # Log trade to CSV
        log_trade(data, order_response if order_response else {"status": "PLACED", "location": location})
        
        return jsonify({
            "message": "Order placed successfully",
            "status": "PLACED",
            "location": location,
            "correlation_id": correl_id,
            "order": order_response if order_response else None
        }), 201  # Return 201 as per API docs
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
    
    # Handle 201 response with empty body and Location header
    location = response.headers.get('Location', '')
    correl_id = response.headers.get('Schwab-Client-CorrelId', '')
    
    # Try to parse response if it has content, otherwise use empty dict
    try:
        order_response = response.json() if response.text else {}
    except:
        order_response = {}
    
    logger.info(f"Signal executed: {signal['symbol']} {signal['action']} @ {signal['entry']} (Location: {location})")
    
    # Log trade
    log_trade(order_data, order_response if order_response else {"status": "PLACED", "location": location}, signal)
    
    return {
        "status": "success",
        "order": order_response if order_response else {"status": "PLACED", "location": location},
        "location": location,
        "correlation_id": correl_id,
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
        fromEnteredTime: Start date/time (ISO-8601 format: yyyy-MM-dd'T'HH:mm:ss.SSSZ)
                        REQUIRED for GET /orders (all accounts)
                        Must be within 60 days from today
                        Must be provided together with toEnteredTime
        toEnteredTime: End date/time (ISO-8601 format: yyyy-MM-dd'T'HH:mm:ss.SSSZ)
                      REQUIRED for GET /orders (all accounts)
                      Must be provided together with fromEnteredTime
        status: Order status filter (AWAITING_PARENT_ORDER, ACCEPTED, FILLED, etc.)
    
    Note: 
    - For GET /orders (all accounts): fromEnteredTime and toEnteredTime are REQUIRED
    - For GET /accounts/{accountNumber}/orders: date parameters are optional
    - Maximum date range is 60 days for GET /orders, 1 year for account-specific
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
            # For account-specific orders, date parameters are optional
            params = {}
            if max_results:
                params['maxResults'] = max_results
            
            # Both must be provided together if one is provided
            if from_entered_time or to_entered_time:
                if not from_entered_time or not to_entered_time:
                    return jsonify({
                        "error": "Both fromEnteredTime and toEnteredTime must be provided together",
                        "format": "ISO-8601: yyyy-MM-dd'T'HH:mm:ss.SSSZ",
                        "example": "2024-03-29T00:00:00.000Z"
                    }), 400
                params['fromEnteredTime'] = from_entered_time
                params['toEnteredTime'] = to_entered_time
            
            if status:
                params['status'] = status
        else:
            # Get all orders for all accounts - REQUIRES date parameters
            url = f"{SCHWAB_BASE_URL}/trader/v1/orders"
            
            # According to API docs: fromEnteredTime and toEnteredTime are REQUIRED for GET /orders
            if not from_entered_time or not to_entered_time:
                return jsonify({
                    "error": "fromEnteredTime and toEnteredTime are REQUIRED for GET /orders (all accounts)",
                    "format": "ISO-8601: yyyy-MM-dd'T'HH:mm:ss.SSSZ",
                    "example": "2024-03-29T00:00:00.000Z",
                    "note": "Date must be within 60 days from today"
                }), 400
            
            params = {
                'fromEnteredTime': from_entered_time,
                'toEnteredTime': to_entered_time
            }
            
            if max_results:
                params['maxResults'] = max_results
            
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
    
    According to Schwab API documentation, the preview response includes:
    - orderStrategy: Order details with projected values (available funds, buying power, commission)
    - orderValidationResult: Validation results (alerts, accepts, rejects, reviews, warns)
    - commissionAndFee: Detailed commission and fee breakdown
    
    Request body: Same as place order (Order Object)
    
    Returns: Preview response with validation results and projected values
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
        
        # Extract key information from preview response
        validation_result = preview_response.get('orderValidationResult', {})
        order_strategy = preview_response.get('orderStrategy', {})
        commission_fee = preview_response.get('commissionAndFee', {})
        
        # Check for validation issues
        has_rejects = len(validation_result.get('rejects', [])) > 0
        has_warns = len(validation_result.get('warns', [])) > 0
        has_reviews = len(validation_result.get('reviews', [])) > 0
        
        return jsonify({
            "message": "Order preview generated",
            "preview": preview_response,
            "summary": {
                "valid": not has_rejects,
                "has_warnings": has_warns,
                "has_reviews": has_reviews,
                "rejects_count": len(validation_result.get('rejects', [])),
                "warns_count": len(validation_result.get('warns', [])),
                "reviews_count": len(validation_result.get('reviews', [])),
                "projected_commission": order_strategy.get('projectedCommission', 0),
                "projected_buying_power": order_strategy.get('projectedBuyingPower', 0),
                "projected_available_fund": order_strategy.get('projectedAvailableFund', 0)
            }
        }), 200
    except Exception as e:
        logger.error(f"Failed to preview order: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/positions', methods=['GET'])
def get_positions():
    """
    Get current positions.
    Schwab API: GET /accounts/{accountNumber}?fields=positions
    
    According to Schwab API documentation:
    - Use GET /accounts/{accountNumber}?fields=positions to get positions for a specific account
    - The fields=positions parameter includes positions in the response
    
    Query params:
        accountId: (optional) Account number. If not provided, uses first account.
    """
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
        # Schwab API: Use /accounts/{accountNumber}?fields=positions
        # According to API docs: GET /accounts/{accountNumber}?fields=positions returns specific account with positions
        # This is more efficient than getting all accounts when we know the account number
        
        account_url = f"{SCHWAB_ACCOUNTS_URL}/{account_id}"
        params = {"fields": "positions"}
        logger.info(f"Requesting account {account_id} with positions from: {account_url}?fields=positions")
        
        account_response = schwab_api_request("GET", account_url, tokens['access_token'], params=params)
        account_data = account_response.json()
        
        # Extract positions from account data
        positions = []
        if isinstance(account_data, list) and len(account_data) > 0:
            securities_account = account_data[0].get('securitiesAccount', {})
            positions = securities_account.get('positions', [])
            logger.info(f"Found {len(positions)} positions for account {account_id}")
        elif isinstance(account_data, dict):
            securities_account = account_data.get('securitiesAccount', {})
            positions = securities_account.get('positions', [])
            logger.info(f"Found {len(positions)} positions for account {account_id}")
        
        return jsonify({
            "positions": positions,
            "account_id": account_id,
            "count": len(positions)
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return jsonify({"error": str(e)}), 500

def build_order_payload(data: dict) -> dict:
    """
    Build order payload for Schwab API.
    
    According to Schwab API documentation, the order object structure includes:
    - session: "NORMAL"
    - duration: "DAY"
    - orderType: "MARKET", "LIMIT", "STOP", etc.
    - orderStrategyType: "SINGLE"
    - orderLegCollection: array of order legs
    
    Args:
        data: Order data dictionary with:
            - symbol: Stock symbol
            - action: "BUY" or "SELL"
            - quantity: Number of shares
            - orderType: "MARKET", "LIMIT", "STOP", etc.
            - price: (optional) For LIMIT orders
            - stopPrice: (optional) For STOP orders
        
    Returns:
        Formatted order payload matching Schwab API structure
    """
    order_type = data.get("orderType", "MARKET").upper()
    action = data.get("action", "BUY").upper()
    symbol = data.get("symbol", "")
    quantity = int(data.get("quantity", 0))
    
    # Build base payload according to Schwab API structure
    # Based on official Schwab API Order Object documentation
    order_leg = {
        "orderLegType": "EQUITY",
        "instruction": action,
        "quantity": quantity,
        "instrument": {
            "symbol": symbol,
            "type": "EQUITY"
        },
        "positionEffect": data.get("positionEffect", "OPENING"),  # OPENING or CLOSING
        "quantityType": data.get("quantityType", "ALL_SHARES")  # ALL_SHARES, DOLLAR, etc.
    }
    
    # Add optional instrument fields if provided
    if "cusip" in data:
        order_leg["instrument"]["cusip"] = data["cusip"]
    if "description" in data:
        order_leg["instrument"]["description"] = data["description"]
    
    payload = {
        "session": data.get("session", "NORMAL"),  # NORMAL, AM, PM, SEAMLESS
        "duration": data.get("duration", "DAY"),  # DAY, GOOD_TILL_CANCEL, FILL_OR_KILL, etc.
        "orderType": order_type,
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [order_leg],
        "taxLotMethod": data.get("taxLotMethod", "FIFO")  # FIFO, LIFO, HIGH_COST, LOW_COST
    }
    
    if "specialInstruction" in data:
        payload["specialInstruction"] = data["specialInstruction"]
    
    if "activationPrice" in data:
        payload["activationPrice"] = float(data["activationPrice"])
    
    if "cancelTime" in data:
        payload["cancelTime"] = data["cancelTime"]
    
    if "releaseTime" in data:
        payload["releaseTime"] = data["releaseTime"]
    
    # Add price for LIMIT orders (according to API docs)
    if order_type == "LIMIT":
        if "price" in data:
            payload["price"] = float(data["price"])
            payload["priceLinkBasis"] = "MANUAL"
            payload["priceLinkType"] = "VALUE"
        else:
            raise ValueError("LIMIT orders require a price")
    
    # Add stop price for STOP orders (according to API docs)
    if order_type == "STOP":
        if "stopPrice" in data:
            payload["stopPrice"] = float(data["stopPrice"])
            payload["stopPriceLinkBasis"] = "MANUAL"
            payload["stopPriceLinkType"] = "VALUE"
            payload["stopType"] = "STANDARD"
        else:
            raise ValueError("STOP orders require a stopPrice")
    
    # Add tax lot method (default FIFO)
    payload["taxLotMethod"] = data.get("taxLotMethod", "FIFO")
    
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
    
    According to Schwab API documentation:
    - Maximum number of transactions: 3000
    - Maximum date range: 1 year
    - startDate and endDate are REQUIRED
    - types parameter is REQUIRED
    
    Query params:
        startDate: REQUIRED - ISO-8601 format: yyyy-MM-dd'T'HH:mm:ss.SSSZ
                  Example: 2024-03-28T21:10:42.000Z
        endDate: REQUIRED - ISO-8601 format: yyyy-MM-dd'T'HH:mm:ss.SSSZ
                Example: 2024-05-10T21:10:42.000Z
        types: REQUIRED - Transaction types (comma-separated)
              Options: TRADE, RECEIVE_AND_DELIVER, DIVIDEND_OR_INTEREST, ACH_RECEIPT,
                      ACH_DISBURSEMENT, CASH_RECEIPT, CASH_DISBURSEMENT, ELECTRONIC_FUND,
                      WIRE_OUT, WIRE_IN, JOURNAL, MEMORANDUM, MARGIN_CALL, MONEY_MARKET,
                      SMA_ADJUSTMENT
        symbol: Optional - Filter by symbol (URL encoded if special characters)
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    symbol = request.args.get('symbol')
    transaction_types = request.args.get('types')
    
    # Validate required parameters
    if not start_date or not end_date:
        return jsonify({
            "error": "startDate and endDate are REQUIRED",
            "format": "ISO-8601: yyyy-MM-dd'T'HH:mm:ss.SSSZ",
            "example_startDate": "2024-03-28T21:10:42.000Z",
            "example_endDate": "2024-05-10T21:10:42.000Z",
            "note": "Maximum date range is 1 year"
        }), 400
    
    if not transaction_types:
        return jsonify({
            "error": "types parameter is REQUIRED",
            "available_types": [
                "TRADE", "RECEIVE_AND_DELIVER", "DIVIDEND_OR_INTEREST", "ACH_RECEIPT",
                "ACH_DISBURSEMENT", "CASH_RECEIPT", "CASH_DISBURSEMENT", "ELECTRONIC_FUND",
                "WIRE_OUT", "WIRE_IN", "JOURNAL", "MEMORANDUM", "MARGIN_CALL", "MONEY_MARKET",
                "SMA_ADJUSTMENT"
            ],
            "example": "types=TRADE,DIVIDEND_OR_INTEREST"
        }), 400
    
    try:
        url = f"{SCHWAB_TRANSACTIONS_URL}/{account_id}/transactions"
        
        params = {
            'startDate': start_date,
            'endDate': end_date,
            'types': transaction_types
        }
        
        if symbol:
            params['symbol'] = symbol
        
        response = schwab_api_request("GET", url, tokens['access_token'], params=params)
        data = response.json()
        
        logger.info(f"Retrieved transactions for account {account_id} (types: {transaction_types})")
        return jsonify({
            "transactions": data if isinstance(data, list) else data.get('transactions', []),
            "account_id": account_id,
            "count": len(data) if isinstance(data, list) else len(data.get('transactions', [])),
            "note": "Maximum 3000 transactions returned, maximum date range is 1 year"
        }), 200
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

