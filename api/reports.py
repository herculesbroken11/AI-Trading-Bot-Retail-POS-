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
from utils.helpers import load_tokens, schwab_api_request, get_valid_access_token
from utils.database import (
    get_trades_from_db, 
    get_todays_trades_from_db,
    get_trade_statistics,
    init_database
)
from ai.analyze import TradingAIAnalyzer

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')
logger = setup_logger("reports")

SCHWAB_BASE_URL = "https://api.schwabapi.com"
SCHWAB_ACCOUNTS_URL = f"{SCHWAB_BASE_URL}/trader/v1/accounts"

@reports_bp.route('/daily', methods=['GET'])
def daily_report():
    """
    Generate daily P&L and trading report.
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    account_id = request.args.get('accountId')
    if not account_id:
        return jsonify({"error": "accountId required"}), 400
    
    try:
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({"error": "Not authenticated"}), 401
        
        # Get account information
        from api.orders import get_account_hash_value
        try:
            account_hash = get_account_hash_value(account_id, access_token)
        except:
            account_hash = account_id
        
        url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}"
        response = schwab_api_request("GET", url, access_token)
        account_data = response.json()
        
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
                account_value = float(account_data.get("currentBalances", {}).get("liquidationValue", 0))
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
        logger.error(f"Failed to generate daily report: {e}")
        return jsonify({"error": str(e)}), 500

@reports_bp.route('/compliance', methods=['GET'])
def compliance_report():
    """
    Generate compliance report with trade statistics.
    """
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    start_date = request.args.get('start_date', date.today().isoformat())
    end_date = request.args.get('end_date', date.today().isoformat())
    
    try:
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
    except:
        # Fallback: calculate from trades list
        winning_trades = sum(1 for t in trades if t.get("pnl", 0) > 0)
        losing_trades = sum(1 for t in trades if t.get("pnl", 0) < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Calculate total P&L from trades
    total_pnl = sum(float(t.get("pnl", 0)) for t in trades if t.get("pnl"))
    
    # Get account P&L from account data if available
    # Handle both dict and list responses from Schwab API
    if isinstance(account_data, list) and len(account_data) > 0:
        account_data = account_data[0]
    
    securities_account = account_data.get("securitiesAccount", account_data)
    current_balances = securities_account.get("currentBalances", {})
    day_trading_buying_power = current_balances.get("dayTradingBuyingPower", 0)
    liquidation_value = current_balances.get("liquidationValue", 0)
    
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

