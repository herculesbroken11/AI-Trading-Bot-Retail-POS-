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
SCHWAB_ACCOUNT_NUMBERS_URL = f"{SCHWAB_ACCOUNTS_URL}/accountNumbers"
SCHWAB_ORDERS_URL = f"{SCHWAB_BASE_URL}/trader/v1/orders"
SCHWAB_TRANSACTIONS_URL = f"{SCHWAB_BASE_URL}/trader/v1/accounts"
SCHWAB_USER_PREF_URL = f"{SCHWAB_BASE_URL}/trader/v1/userPreference"

# Cache for account number to hash value mapping
_account_hash_cache = {}

def get_account_hash_value(account_number: str, access_token: str) -> str:
    """
    Get encrypted hash value for an account number.
    According to Schwab API: Account numbers in plain text cannot be used outside of headers.
    Must use encrypted hash values for all accountNumber requests.
    
    Args:
        account_number: Plain text account number (e.g., "18056335" or 18056335)
        access_token: OAuth access token
        
    Returns:
        Encrypted hash value for the account number
    """
    global _account_hash_cache
    
    # Ensure account_number is always a string for consistent comparison
    account_number_str = str(account_number).strip()
    
    # Check cache first (using string key)
    if account_number_str in _account_hash_cache:
        logger.debug(f"Using cached hash for account {account_number_str}")
        return _account_hash_cache[account_number_str]
    
    try:
        # Get all account numbers and their hash values
        logger.info(f"Fetching account numbers from Schwab API...")
        response = schwab_api_request("GET", SCHWAB_ACCOUNT_NUMBERS_URL, access_token)
        account_numbers = response.json()
        
        # Handle both single object and array responses
        if isinstance(account_numbers, dict):
            account_numbers = [account_numbers]
        
        logger.info(f"Received {len(account_numbers)} account number(s) from API")
        
        # Log all account numbers received for debugging
        all_accounts = []
        for acc in account_numbers:
            acc_num_raw = acc.get("accountNumber", "")
            acc_num = str(acc_num_raw).strip() if acc_num_raw else ""
            all_accounts.append(acc_num)
            logger.debug(f"API returned account: {acc_num} (type: {type(acc_num_raw)})")
        
        logger.info(f"Looking for account '{account_number_str}' (type: {type(account_number_str)}) in: {all_accounts}")
        
        # Find matching account number and cache all mappings
        for acc in account_numbers:
            # Account number can be string or number in API response - convert to string
            acc_num_raw = acc.get("accountNumber", "")
            acc_num = str(acc_num_raw).strip() if acc_num_raw else ""
            hash_val = str(acc.get("hashValue", "")).strip() if acc.get("hashValue") else ""
            
            if acc_num and hash_val:
                # Cache all account numbers we find (using string keys)
                _account_hash_cache[acc_num] = hash_val
                logger.debug(f"Cached: account '{acc_num}' -> hash '{hash_val[:20]}...'")
                
                # Compare as strings (exact match)
                if acc_num == account_number_str:
                    logger.info(f"✓ Match found! Account '{account_number_str}' -> hash '{hash_val[:20]}...'")
                    return hash_val
                else:
                    logger.debug(f"  No match: '{acc_num}' != '{account_number_str}'")
        
        # If not found, raise error with available account numbers for debugging
        available_accounts = [str(acc.get("accountNumber", "")) for acc in account_numbers if acc.get("accountNumber")]
        logger.error(f"Account number '{account_number_str}' not found. Available: {available_accounts}")
        raise ValueError(
            f"Account number '{account_number_str}' not found in account numbers list. "
            f"Available accounts: {available_accounts}"
        )
        
    except ValueError:
        # Re-raise ValueError (our custom error)
        raise
    except Exception as e:
        logger.error(f"Failed to get account hash value: {e}", exc_info=True)
        raise ValueError(f"Failed to retrieve account hash value: {str(e)}")

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
        # Convert to encrypted hash value
        account_id = data["accountId"]
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            account_hash = account_id
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}/orders"
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
        
        # Log trade to CSV and database
        log_trade(data, order_response if order_response else {"status": "PLACED", "location": location}, None, account_id)
        
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
    # Convert to encrypted hash value
    try:
        account_hash = get_account_hash_value(account_id, access_token)
    except Exception as e:
        logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
        account_hash = account_id
    url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}/orders"
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
    
    # Log trade to CSV and database
    log_trade(order_data, order_response if order_response else {"status": "PLACED", "location": location}, signal, account_id)
    
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
    
    Note: accountNumber should be the encrypted hash value, not plain text.
    The system will automatically convert plain text account numbers to hash values.
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Convert plain text account number to encrypted hash value if needed
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
            logger.info(f"Using encrypted hash value for account {account_id}")
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            # Fallback to plain text (might work for some endpoints)
            account_hash = account_id
        
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}"
        response = schwab_api_request("GET", url, tokens['access_token'])
        data = response.json()
        
        logger.info(f"Retrieved account {account_id} (hash: {account_hash[:20]}...)")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get account {account_id}: {e}")
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/account-numbers', methods=['GET'])
def get_account_numbers():
    """
    Get list of account numbers and their encrypted hash values.
    Schwab API: GET /accounts/accountNumbers
    
    According to Schwab API documentation:
    - Account numbers in plain text cannot be used outside of headers or request/response bodies
    - Must use encrypted hash values for all subsequent accountNumber requests
    - This endpoint returns the mapping of plain text account numbers to encrypted hash values
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        response = schwab_api_request("GET", SCHWAB_ACCOUNT_NUMBERS_URL, tokens['access_token'])
        account_numbers = response.json()
        
        # Handle both single object and array responses
        if isinstance(account_numbers, dict):
            account_numbers = [account_numbers]
        
        # Update cache
        global _account_hash_cache
        for acc in account_numbers:
            acc_num = acc.get("accountNumber", "")
            hash_val = acc.get("hashValue", "")
            if acc_num and hash_val:
                _account_hash_cache[acc_num] = hash_val
        
        logger.info(f"Retrieved {len(account_numbers)} account number(s)")
        return jsonify({
            "account_numbers": account_numbers,
            "count": len(account_numbers),
            "note": "Use hashValue for all account-specific API calls"
        }), 200
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
            # Convert to encrypted hash value
            try:
                account_hash = get_account_hash_value(account_id, tokens['access_token'])
            except Exception as e:
                logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
                account_hash = account_id
            url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}/orders"
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
        # Convert to encrypted hash value
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            account_hash = account_id
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}/orders/{order_id}"
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
        # Convert to encrypted hash value
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            account_hash = account_id
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}/orders/{order_id}"
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
        
        # Convert to encrypted hash value
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            account_hash = account_id
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}/orders/{order_id}"
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
        
        # Convert to encrypted hash value
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            account_hash = account_id
        
        # Optional: Pre-check buying power before sending to API
        # This helps provide better error messages
        try:
            account_response = schwab_api_request("GET", f"{SCHWAB_ACCOUNTS_URL}/{account_hash}", tokens['access_token'])
            account_data = account_response.json()
            if isinstance(account_data, list) and len(account_data) > 0:
                account = account_data[0].get('securitiesAccount', {})
                balances = account.get('currentBalances', {})
                available_funds = balances.get('availableFunds', 0)
                buying_power = balances.get('buyingPower', 0)
                
                # Calculate order cost
                quantity = data.get('quantity', 0)
                price = data.get('price', 0) if data.get('orderType', '').upper() == 'LIMIT' else 0
                order_cost = quantity * price if price > 0 else 0
                
                # Warn if insufficient funds (but still try the API call)
                if order_cost > 0 and order_cost > available_funds:
                    logger.warning(f"Order cost (${order_cost:.2f}) exceeds available funds (${available_funds:.2f})")
        except Exception as e:
            logger.debug(f"Could not pre-check buying power: {e}")
            # Continue anyway - let Schwab API validate
        
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}/previewOrder"
        
        # Log the payload for debugging
        logger.info(f"Preview order payload: {order_payload}")
        
        try:
            response = schwab_api_request("POST", url, tokens['access_token'], data=order_payload)
            preview_response = response.json()
        except Exception as api_error:
            # Try to get more details from the error
            error_str = str(api_error)
            logger.error(f"Preview order API error: {error_str}")
            logger.error(f"Order payload sent: {order_payload}")
            
            # If it's a 400 error, try to get response body if available
            if "400" in error_str or "Bad Request" in error_str:
                # Extract validation error details if available
                suggestion = "Check order payload structure. Ensure all required fields are present and valid."
                if "validation error" in error_str.lower():
                    suggestion += " Common issues: insufficient buying power, price too far from market, or market closed."
                
                # Try to get account balance to check buying power
                buying_power_info = None
                try:
                    account_response = schwab_api_request("GET", f"{SCHWAB_ACCOUNTS_URL}/{account_hash}", tokens['access_token'])
                    account_data = account_response.json()
                    if isinstance(account_data, list) and len(account_data) > 0:
                        account = account_data[0].get('securitiesAccount', {})
                        balances = account.get('currentBalances', {})
                        buying_power_info = {
                            "available_funds": balances.get('availableFunds'),
                            "buying_power": balances.get('buyingPower'),
                            "cash_balance": balances.get('cashBalance')
                        }
                except:
                    pass  # Don't fail if we can't get account info
                
                return jsonify({
                    "error": "Bad request to Schwab API - validation error",
                    "details": error_str,
                    "payload_sent": order_payload,
                    "suggestion": suggestion,
                    "account_info": buying_power_info,
                    "common_fixes": [
                        "Check account has sufficient buying power (order cost: quantity × price)",
                        "Verify price is reasonable (not too far from current market price)",
                        "Ensure market is open (9:30 AM - 4:00 PM ET)",
                        "Verify symbol is valid and tradeable",
                        "Check quantity is a positive integer",
                        "For LIMIT orders, price should be within reasonable range of current market price"
                    ]
                }), 400
            raise
        
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
        # Schwab API: GET /accounts/{accountNumber}
        # According to the API response you provided, positions are included in the response
        # but the 'positions' field may be missing if there are no open positions
        # The fields=positions parameter may not be needed or may not work at the account-specific endpoint
        
        # Convert plain text account number to encrypted hash value if needed
        # Schwab API requires encrypted hash values for account-specific endpoints
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
            logger.info(f"Using encrypted hash value for account {account_id}")
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            # Fallback to plain text (might work for some endpoints)
            account_hash = account_id
        
        account_url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}"
        logger.info(f"Requesting account {account_id} (hash: {account_hash[:20]}...) details to get positions")
        
        # Get account details - positions should be included if they exist
        # Don't use fields parameter at account-specific endpoint (causes 400 error)
        account_response = schwab_api_request("GET", account_url, tokens['access_token'])
        account_data = account_response.json()
        
        # Extract positions from account data
        # Schwab API returns account data in different formats
        positions = []
        
        # Handle array response format (when getting all accounts)
        if isinstance(account_data, list) and len(account_data) > 0:
            account_item = account_data[0]
            # Check if it's wrapped in securitiesAccount
            if 'securitiesAccount' in account_item:
                securities_account = account_item.get('securitiesAccount', {})
                # Positions field may not exist if account has no positions
                positions = securities_account.get('positions', [])
            else:
                # Direct account object
                positions = account_item.get('positions', [])
            logger.info(f"Found {len(positions)} positions for account {account_id} (array format)")
        
        # Handle dict response format (when getting specific account)
        elif isinstance(account_data, dict):
            # Check if it's wrapped in securitiesAccount
            if 'securitiesAccount' in account_data:
                securities_account = account_data.get('securitiesAccount', {})
                # Positions field may not exist if account has no positions - this is normal
                positions = securities_account.get('positions', [])
                logger.info(f"Account {account_id} has {len(positions)} positions (dict format with securitiesAccount)")
            else:
                # Direct account object
                positions = account_data.get('positions', [])
                logger.info(f"Account {account_id} has {len(positions)} positions (dict format direct)")
        
        # Return positions (empty array if no positions - this is normal)
        return jsonify({
            "positions": positions,
            "account_id": account_id,
            "count": len(positions),
            "message": "No open positions" if len(positions) == 0 else f"{len(positions)} position(s) found"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        # Provide more detailed error information
        error_msg = str(e)
        if "400" in error_msg:
            return jsonify({
                "error": "Bad request to Schwab API. The account may not exist or the API format may have changed.",
                "details": error_msg,
                "suggestion": "Try calling GET /orders/accounts first to verify the account ID"
            }), 400
        return jsonify({"error": error_msg}), 500

def build_order_payload(data: dict) -> dict:
    """
    Build order payload for Schwab API.
    
    According to Schwab API documentation, the order object structure includes:
    - session: "NORMAL"
    - duration: "DAY"
    - orderType: "MARKET", "LIMIT", "STOP", etc.
    - orderStrategyType: "SINGLE"
    - complexOrderStrategyType: "NONE"
    - orderLegCollection: array of order legs
    - taxLotMethod: "FIFO"
    
    Args:
        data: Order data dictionary with:
            - symbol: Stock symbol
            - action: "BUY" or "SELL"
            - quantity: Number of shares
            - orderType: "MARKET", "LIMIT", "STOP", etc.
            - price: (optional) For LIMIT orders
            - stopPrice: (optional) For STOP orders
            - stopPriceOffset: (optional) For STOP orders
            - cancelTime: (optional) ISO-8601 timestamp
            - releaseTime: (optional) ISO-8601 timestamp
            - activationPrice: (optional) For conditional orders
            - specialInstruction: (optional) "ALL_OR_NONE", "DO_NOT_REDUCE", etc.
            - cusip: (optional) CUSIP identifier
            - description: (optional) Instrument description
            - divCapGains: (optional) "REINVEST" for dividend handling
            - toSymbol: (optional) For symbol conversion orders
            - destinationLinkName: (optional) Destination link name
            - priceLinkBasis: (optional) "MANUAL", "BASIS", etc.
            - priceLinkType: (optional) "VALUE", "PERCENT", etc.
            - stopPriceLinkBasis: (optional) "MANUAL", "BASIS", etc.
            - stopPriceLinkType: (optional) "VALUE", "PERCENT", etc.
            - stopType: (optional) "STANDARD", "BID", "ASK", "LAST", "MARK"
        
    Returns:
        Formatted order payload matching Schwab API Order Object structure
    """
    order_type = data.get("orderType", "MARKET").upper()
    action = data.get("action", "BUY").upper()
    symbol = data.get("symbol", "")
    quantity = int(data.get("quantity", 0))
    
    if quantity <= 0:
        raise ValueError("Quantity must be greater than 0")
    
    # Build order leg according to working example from Medium article
    # Key differences: use assetType instead of type, include legId, no quantityType
    leg_id = data.get("legId", 1)  # Default to 1 (can be int or string, but int is cleaner)
    order_leg = {
        "orderLegType": "EQUITY",
        "legId": int(leg_id) if isinstance(leg_id, (int, str)) and str(leg_id).isdigit() else 1,
        "instrument": {
            "symbol": symbol,
            "assetType": "EQUITY"  # Use assetType instead of type (per Medium article)
        },
        "instruction": action,
        "positionEffect": data.get("positionEffect", "OPENING"),  # OPENING or CLOSING
        "quantity": quantity  # Use numeric value
    }
    
    # Add optional order leg fields if provided
    if "cusip" in data:
        order_leg["instrument"]["cusip"] = data["cusip"]
    
    if "description" in data:
        order_leg["instrument"]["description"] = data["description"]
    
    if "instrumentId" in data:
        order_leg["instrument"]["instrumentId"] = int(data["instrumentId"])
    
    if "netChange" in data:
        order_leg["instrument"]["netChange"] = float(data["netChange"])
    
    if "divCapGains" in data:
        order_leg["divCapGains"] = data["divCapGains"]  # REINVEST, etc.
    
    if "toSymbol" in data:
        order_leg["toSymbol"] = data["toSymbol"]
    
    # Build base payload according to working example from Medium article
    # Key: include quantity and price at top level
    payload = {
        "session": data.get("session", "NORMAL"),  # NORMAL, AM, PM, SEAMLESS
        "duration": data.get("duration", "DAY"),  # DAY, GOOD_TILL_CANCEL, FILL_OR_KILL, etc.
        "orderType": order_type,
        "complexOrderStrategyType": data.get("complexOrderStrategyType", "NONE"),  # NONE, COVERED, etc.
        "quantity": quantity,  # Include at top level per Medium article
        "taxLotMethod": data.get("taxLotMethod", "FIFO"),  # FIFO, LIFO, HIGH_COST, LOW_COST, AVERAGE_COST, SPECIFIC_LOT
        "orderLegCollection": [order_leg],
        "orderStrategyType": "SINGLE"
    }
    
    # Add price at top level (for LIMIT orders, required; for others, optional)
    if order_type == "LIMIT":
        if "price" in data:
            payload["price"] = float(data["price"])  # Use numeric value
        else:
            raise ValueError("LIMIT orders require a price")
    elif "price" in data:
        # Allow price for other order types if provided
        payload["price"] = float(data["price"])
    
    # Add optional order-level fields if provided
    if "specialInstruction" in data:
        payload["specialInstruction"] = data["specialInstruction"]  # ALL_OR_NONE, DO_NOT_REDUCE, etc.
    
    if "activationPrice" in data:
        payload["activationPrice"] = float(data["activationPrice"])
    
    if "cancelTime" in data:
        payload["cancelTime"] = data["cancelTime"]  # ISO-8601 format
    
    if "releaseTime" in data:
        payload["releaseTime"] = data["releaseTime"]  # ISO-8601 format
    
    if "destinationLinkName" in data:
        payload["destinationLinkName"] = data["destinationLinkName"]
    
    # Add stop price for STOP orders
    if order_type == "STOP" or order_type == "STOP_LIMIT":
        if "stopPrice" in data:
            payload["stopPrice"] = float(data["stopPrice"])
            # Optional stop-related fields
            if "stopPriceLinkBasis" in data:
                payload["stopPriceLinkBasis"] = data["stopPriceLinkBasis"]
            if "stopPriceLinkType" in data:
                payload["stopPriceLinkType"] = data["stopPriceLinkType"]
            if "stopType" in data:
                payload["stopType"] = data["stopType"]
            if "stopPriceOffset" in data:
                payload["stopPriceOffset"] = float(data["stopPriceOffset"])
        else:
            raise ValueError(f"{order_type} orders require a stopPrice")
    
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

def log_trade(order_data: dict, order_response: dict, signal: dict = None, account_id: str = None):
    """
    Log trade to both CSV file and SQLite database.
    
    Args:
        order_data: Order data
        order_response: Order response from API
        signal: Optional signal data
        account_id: Optional account ID
    """
    from pathlib import Path
    import csv
    from utils.database import log_trade_to_db
    
    # Log to CSV (for backward compatibility)
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
    
    # Log to SQLite database
    try:
        log_trade_to_db(order_data, order_response, signal, account_id)
    except Exception as e:
        logger.warning(f"Failed to log trade to database (CSV logged successfully): {e}")
    
    logger.info(f"Trade logged to {csv_path} and database")

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
        # Convert to encrypted hash value
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            account_hash = account_id
        url = f"{SCHWAB_TRANSACTIONS_URL}/{account_hash}/transactions"
        
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
        # Convert to encrypted hash value
        try:
            account_hash = get_account_hash_value(account_id, tokens['access_token'])
        except Exception as e:
            logger.warning(f"Could not get hash value for {account_id}, trying plain text: {e}")
            account_hash = account_id
        url = f"{SCHWAB_TRANSACTIONS_URL}/{account_hash}/transactions/{transaction_id}"
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

