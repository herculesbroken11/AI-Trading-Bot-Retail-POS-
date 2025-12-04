"""
Daily reporting and compliance endpoints.
"""
import os
from flask import Blueprint, request, jsonify
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import csv
from utils.logger import setup_logger
from utils.helpers import schwab_api_request, get_valid_access_token
from utils.database import (
    get_trades_from_db, 
    get_todays_trades_from_db,
    get_trade_statistics,
    init_database
)
from ai.analyze import TradingAIAnalyzer

# Import Schwab API constants from orders module (single source of truth)
from api.orders import (
    SCHWAB_BASE_URL,
    SCHWAB_ACCOUNTS_URL
)

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')
logger = setup_logger("reports")

@reports_bp.route('/test-hash/<account_id>', methods=['GET'])
def test_account_hash(account_id: str):
    """
    Diagnostic endpoint to test account hash lookup.
    """
    try:
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({"error": "Not authenticated"}), 401
        
        from api.orders import get_account_hash_value, SCHWAB_ACCOUNT_NUMBERS_URL
        
        # Get account numbers
        response = schwab_api_request("GET", SCHWAB_ACCOUNT_NUMBERS_URL, access_token)
        account_numbers = response.json()
        if isinstance(account_numbers, dict):
            account_numbers = [account_numbers]
        
        # Try to get hash
        try:
            account_hash = get_account_hash_value(account_id, access_token)
            return jsonify({
                "account_id": account_id,
                "account_hash": account_hash,
                "hash_length": len(account_hash),
                "is_valid": account_hash != account_id and len(account_hash) > 20,
                "available_accounts": [str(acc.get("accountNumber", "")) for acc in account_numbers if acc.get("accountNumber")]
            }), 200
        except Exception as e:
            return jsonify({
                "account_id": account_id,
                "error": str(e),
                "available_accounts": [str(acc.get("accountNumber", "")) for acc in account_numbers if acc.get("accountNumber")]
            }), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@reports_bp.route('/daily', methods=['GET'])
def daily_report():
    """
    Generate daily P&L and trading report.
    """
    account_id = request.args.get('accountId')
    if not account_id:
        return jsonify({"error": "accountId required"}), 400
    
    # Ensure account_id is always a string
    account_id = str(account_id).strip()
    
    try:
        # get_valid_access_token() handles authentication and auto-refresh
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({"error": "Not authenticated. Please authenticate with Schwab first."}), 401
        
        # Get account information - must use encrypted hash value
        from api.orders import SCHWAB_ACCOUNT_NUMBERS_URL
        
        # STEP 1: Get all available account numbers first
        logger.info(f"Step 1: Getting all account numbers from Schwab API...")
        try:
            account_numbers_response = schwab_api_request("GET", SCHWAB_ACCOUNT_NUMBERS_URL, access_token)
            all_account_numbers = account_numbers_response.json()
            if isinstance(all_account_numbers, dict):
                all_account_numbers = [all_account_numbers]
            
            # Extract account numbers and hash values
            available_accounts = []
            account_hash_map = {}
            for acc in all_account_numbers:
                acc_num = str(acc.get("accountNumber", "")).strip()
                hash_val = str(acc.get("hashValue", "")).strip()
                if acc_num and hash_val:
                    available_accounts.append(acc_num)
                    account_hash_map[acc_num] = hash_val
                    logger.info(f"  Found account: {acc_num} -> hash: {hash_val[:30]}...")
            
            logger.info(f"Total available accounts: {len(available_accounts)}")
            logger.info(f"Looking for account: '{account_id}' in available accounts: {available_accounts}")
            
        except Exception as e:
            logger.error(f"Failed to get account numbers: {e}", exc_info=True)
            return jsonify({
                "error": "Failed to retrieve account numbers from Schwab API",
                "details": str(e),
                "account_id_provided": account_id,
                "suggestion": "Please verify your authentication and try again."
            }), 500
        
        # STEP 2: Check if account exists in the list
        account_id_str = str(account_id).strip()
        if account_id_str not in available_accounts:
            logger.error(f"❌ Account '{account_id_str}' NOT FOUND in available accounts!")
            return jsonify({
                "error": "Account number not found",
                "account_id_provided": account_id_str,
                "available_accounts": available_accounts,
                "suggestion": f"The account number '{account_id_str}' is not in your account list. Available accounts: {available_accounts}. Please use one of these account numbers."
            }), 400
        
        # STEP 3: Get hash value for the account
        account_hash = account_hash_map.get(account_id_str)
        
        if not account_hash:
            logger.error(f"❌ No hash value found for account '{account_id_str}'")
            return jsonify({
                "error": "Hash value not found for account",
                "account_id_provided": account_id_str,
                "available_accounts": available_accounts,
                "suggestion": "The account exists but hash value is missing. Please try again or contact support."
            }), 500
        
        # STEP 4: Validate hash value
        if account_hash == account_id_str:
            logger.error(f"❌ CRITICAL: Hash equals account ID! hash={account_hash}, account_id={account_id_str}")
            return jsonify({
                "error": "Invalid hash value",
                "details": "Hash value equals account ID - this should never happen",
                "account_id_provided": account_id_str,
                "suggestion": "This indicates a critical error. Please check server logs."
            }), 500
        
        if len(account_hash) < 20:
            logger.error(f"❌ Hash value too short: {account_hash}")
            return jsonify({
                "error": "Invalid hash value format",
                "details": f"Hash value '{account_hash}' is too short",
                "account_id_provided": account_id_str,
                "suggestion": "Hash values should be long encrypted strings. Please verify account numbers endpoint."
            }), 500
        
        logger.info(f"✓ Account '{account_id_str}' found! Hash: {account_hash[:30]}...")
        
        # Build URL with validated hash (already validated in STEP 4 above)
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}"
        logger.info(f"✓ Making request to Schwab API: {url}")
        logger.info(f"  Account ID: {account_id_str}")
        logger.info(f"  Account Hash: {account_hash[:50]}... (length: {len(account_hash)})")
        
        try:
            response = schwab_api_request("GET", url, access_token)
            account_data = response.json()
        except Exception as api_error:
            error_str = str(api_error)
            logger.error(f"❌ Schwab API error: {error_str}")
            logger.error(f"  URL used: {url}")
            logger.error(f"  Account ID: {account_id}")
            logger.error(f"  Account Hash: {account_hash}")
            
            # If it's a 400 error about invalid account, provide helpful message
            if "Invalid account number" in error_str or "400" in error_str:
                # This should never happen if our validation worked, but just in case
                if account_hash == account_id:
                    logger.error(f"❌ CRITICAL BUG: Plain account number was used in URL despite validation!")
                    return jsonify({
                        "error": "CRITICAL: Plain account number was used in API call",
                        "details": "This indicates a bug in the validation logic",
                        "account_id_provided": account_id,
                        "url_used": url,
                        "suggestion": "Please check server logs and report this issue. The system should never use plain account numbers."
                    }), 500
                
                return jsonify({
                    "error": "Invalid account number or hash value",
                    "details": error_str,
                    "account_id_provided": account_id,
                    "account_hash_used": account_hash[:50] + "..." if len(account_hash) > 50 else account_hash,
                    "url_used": url,
                    "suggestion": "The hash value may be invalid. Try calling /orders/account-numbers to verify the account mapping."
                }), 400
            raise
        
        # Get today's trades from database (preferred) or CSV (fallback)
        try:
            trades = get_todays_trades_from_db(account_id=account_id)
            if not trades:
                # Fallback to CSV if database is empty
                trades = get_todays_trades()
        except Exception as e:
            logger.warning(f"Database query failed, using CSV: {e}")
            trades = get_todays_trades()
        
        # Calculate P&L
        pnl_data = calculate_daily_pnl(trades, account_data)
        
        # Generate AI report if trades exist
        ai_report = None
        if trades:
            try:
                analyzer = TradingAIAnalyzer()
                # Get account value safely
                account_value = 0
                try:
                    if isinstance(account_data, list) and len(account_data) > 0:
                        account_data = account_data[0]
                    securities_account = account_data.get("securitiesAccount", account_data) if isinstance(account_data, dict) else {}
                    current_balances = securities_account.get("currentBalances", {}) if isinstance(securities_account, dict) else {}
                    account_value = float(current_balances.get("liquidationValue", 0) or 0) if isinstance(current_balances, dict) else 0
                except:
                    pass
                ai_report = analyzer.generate_daily_report(trades, account_value)
            except Exception as e:
                logger.warning(f"AI report generation failed: {e}")
        
        # Save report
        report_path = save_daily_report(pnl_data, trades, ai_report)
        
        return jsonify({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "account_id": account_id,
            "pnl": pnl_data,
            "trades": trades,
            "ai_report": ai_report,
            "report_path": str(report_path)
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to generate daily report: {e}", exc_info=True)
        return jsonify({
            "error": "Failed to generate daily report",
            "details": str(e),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "account_id": account_id,
            "pnl": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "estimated_pnl": 0,
                "account_value": 0,
                "buying_power": 0
            },
            "trades": []
        }), 500

@reports_bp.route('/compliance', methods=['GET'])
def compliance_report():
    """
    Generate compliance report with trade statistics.
    """
    start_date = request.args.get('start_date', date.today().isoformat())
    end_date = request.args.get('end_date', date.today().isoformat())
    
    try:
        # get_valid_access_token() handles authentication and auto-refresh
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({"error": "Not authenticated. Please authenticate with Schwab first."}), 401
        # Load trades from database (preferred) or CSV (fallback)
        try:
            trades = get_trades_from_db(start_date=start_date, end_date=end_date)
            if not trades:
                # Fallback to CSV if database is empty
                trades = load_trades_from_csv(start_date, end_date)
        except Exception as e:
            logger.warning(f"Database query failed, using CSV: {e}")
            trades = load_trades_from_csv(start_date, end_date)
        
        # Calculate compliance metrics
        metrics = calculate_compliance_metrics(trades)
        
        return jsonify({
            "period": {
                "start": start_date,
                "end": end_date
            },
            "metrics": metrics,
            "trades": trades
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to generate compliance report: {e}")
        return jsonify({"error": str(e)}), 500

@reports_bp.route('/trades', methods=['GET'])
def get_trades():
    """
    Get trades from database or CSV file.
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    symbol = request.args.get('symbol')
    account_id = request.args.get('accountId')
    
    try:
        # Try database first, fallback to CSV
        try:
            trades = get_trades_from_db(start_date=start_date, end_date=end_date, 
                                       symbol=symbol, account_id=account_id)
            if not trades:
                trades = load_trades_from_csv(start_date, end_date)
        except Exception as e:
            logger.warning(f"Database query failed, using CSV: {e}")
            trades = load_trades_from_csv(start_date, end_date)
        
        return jsonify({
            "count": len(trades),
            "trades": trades
        }), 200
    except Exception as e:
        logger.error(f"Failed to load trades: {e}")
        return jsonify({"error": str(e)}), 500

def get_todays_trades() -> list:
    """Get all trades executed today."""
    csv_path = Path("data/trades.csv")
    if not csv_path.exists():
        return []
    
    today = datetime.now().date()
    trades = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade_date = datetime.fromisoformat(row['timestamp']).date()
            if trade_date == today:
                trades.append(row)
    
    return trades

def load_trades_from_csv(start_date: str = None, end_date: str = None) -> list:
    """Load trades from CSV file within date range."""
    csv_path = Path("data/trades.csv")
    if not csv_path.exists():
        return []
    
    trades = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade_date = datetime.fromisoformat(row['timestamp']).date()
            
            if start_date:
                start = datetime.fromisoformat(start_date).date()
                if trade_date < start:
                    continue
            
            if end_date:
                end = datetime.fromisoformat(end_date).date()
                if trade_date > end:
                    continue
            
            trades.append(row)
    
    return trades

def calculate_daily_pnl(trades: list, account_data: dict) -> dict:
    """Calculate daily P&L from trades."""
    total_trades = len(trades)
    
    # Try to get statistics from database if available
    try:
        stats = get_trade_statistics()
        winning_trades = stats.get("winning_trades", 0)
        losing_trades = stats.get("losing_trades", 0)
        win_rate = stats.get("win_rate", 0)
    except Exception as e:
        logger.debug(f"Could not get statistics from database: {e}")
        # Fallback: calculate from trades list
        winning_trades = sum(1 for t in trades if t.get("pnl") and float(t.get("pnl", 0)) > 0)
        losing_trades = sum(1 for t in trades if t.get("pnl") and float(t.get("pnl", 0)) < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Calculate total P&L from trades
    total_pnl = 0.0
    for t in trades:
        try:
            pnl = t.get("pnl")
            if pnl:
                total_pnl += float(pnl)
        except (ValueError, TypeError):
            pass
    
    # Get account P&L from account data if available
    # Handle both dict and list responses from Schwab API
    liquidation_value = 0
    day_trading_buying_power = 0
    
    try:
        if isinstance(account_data, list) and len(account_data) > 0:
            account_data = account_data[0]
        
        if isinstance(account_data, dict):
            # Try different possible structures
            securities_account = account_data.get("securitiesAccount", account_data)
            
            if isinstance(securities_account, dict):
                current_balances = securities_account.get("currentBalances", {})
                if isinstance(current_balances, dict):
                    liquidation_value = float(current_balances.get("liquidationValue", 0) or 0)
                    day_trading_buying_power = float(current_balances.get("dayTradingBuyingPower", 0) or 0)
    except Exception as e:
        logger.warning(f"Could not parse account data: {e}")
        # Use defaults (0) if parsing fails
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "estimated_pnl": total_pnl,
        "account_value": liquidation_value,
        "buying_power": day_trading_buying_power
    }

def calculate_compliance_metrics(trades: list) -> dict:
    """Calculate compliance and risk metrics."""
    if not trades:
        return {
            "total_trades": 0,
            "total_volume": 0,
            "average_trade_size": 0,
            "max_trade_size": 0,
            "risk_per_trade": "N/A"
        }
    
    total_volume = sum(int(t.get("quantity", 0)) for t in trades)
    trade_sizes = [int(t.get("quantity", 0)) for t in trades]
    
    return {
        "total_trades": len(trades),
        "total_volume": total_volume,
        "average_trade_size": total_volume / len(trades) if trades else 0,
        "max_trade_size": max(trade_sizes) if trade_sizes else 0,
        "risk_per_trade": f"${os.getenv('MAX_TRADE_AMOUNT', '300')}"
    }

def save_daily_report(pnl_data: dict, trades: list, ai_report: str = None) -> Path:
    """Save daily report to file."""
    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = report_dir / f"daily_report_{datetime.now().strftime('%Y%m%d')}.txt"
    
    with open(report_path, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write(f"Daily Trading Report - {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("P&L Summary:\n")
        f.write(f"  Total Trades: {pnl_data['total_trades']}\n")
        f.write(f"  Winning Trades: {pnl_data['winning_trades']}\n")
        f.write(f"  Losing Trades: {pnl_data['losing_trades']}\n")
        f.write(f"  Win Rate: {pnl_data['win_rate']:.2f}%\n")
        f.write(f"  Account Value: ${pnl_data['account_value']:,.2f}\n\n")
        
        f.write("Trades:\n")
        for trade in trades:
            f.write(f"  {trade.get('symbol')} {trade.get('action')} "
                   f"{trade.get('quantity')} @ ${trade.get('price')}\n")
        
        if ai_report:
            f.write("\n" + "=" * 60 + "\n")
            f.write("AI Analysis:\n")
            f.write("=" * 60 + "\n")
            f.write(ai_report)
    
    logger.info(f"Daily report saved to {report_path}")
    return report_path

