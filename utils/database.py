"""
SQLite database utilities for trade logging and reporting.
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from utils.logger import setup_logger

logger = setup_logger("database")

DB_PATH = Path("data/trades.db")

def get_db_connection():
    """Get SQLite database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def init_database():
    """Initialize database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            stop_price REAL,
            target_price REAL,
            order_id TEXT,
            status TEXT,
            setup_type TEXT,
            entry REAL,
            stop REAL,
            target REAL,
            account_id TEXT,
            pnl REAL,
            filled_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol ON trades(symbol)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_date ON trades(date(timestamp))
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def log_trade_to_db(order_data: Dict, order_response: Dict, signal: Optional[Dict] = None, account_id: Optional[str] = None):
    """
    Log trade to SQLite database.
    
    Args:
        order_data: Order data dictionary
        order_response: Order response from API
        signal: Optional signal data
        account_id: Optional account ID
    """
    try:
        init_database()  # Ensure database exists
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO trades (
                timestamp, symbol, action, quantity, price,
                stop_price, target_price, order_id, status,
                setup_type, entry, stop, target, account_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
            signal.get("target") if signal else None,
            account_id
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Trade logged to database: {order_data.get('symbol')} {order_data.get('action')}")
    except Exception as e:
        logger.error(f"Failed to log trade to database: {e}")

def get_trades_from_db(start_date: Optional[str] = None, end_date: Optional[str] = None, 
                      symbol: Optional[str] = None, account_id: Optional[str] = None) -> List[Dict]:
    """
    Get trades from database with optional filters.
    
    Args:
        start_date: Start date (ISO format or YYYY-MM-DD)
        end_date: End date (ISO format or YYYY-MM-DD)
        symbol: Filter by symbol
        account_id: Filter by account ID
        
    Returns:
        List of trade dictionaries
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date(timestamp) >= date(?)"
            params.append(start_date)
        
        if end_date:
            query += " AND date(timestamp) <= date(?)"
            params.append(end_date)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        
        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert rows to dictionaries
        trades = []
        for row in rows:
            trade = dict(row)
            trades.append(trade)
        
        conn.close()
        return trades
    except Exception as e:
        logger.error(f"Failed to get trades from database: {e}")
        return []

def get_todays_trades_from_db(account_id: Optional[str] = None) -> List[Dict]:
    """Get all trades executed today."""
    today = datetime.now().date().isoformat()
    return get_trades_from_db(start_date=today, end_date=today, account_id=account_id)

def update_trade_pnl(trade_id: int, pnl: float):
    """Update P&L for a trade."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trades SET pnl = ? WHERE id = ?
        """, (pnl, trade_id))
        
        conn.commit()
        conn.close()
        logger.info(f"Updated P&L for trade {trade_id}: ${pnl:.2f}")
    except Exception as e:
        logger.error(f"Failed to update trade P&L: {e}")

def get_trade_statistics(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get trade statistics for reporting.
    
    Returns:
        Dictionary with statistics
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT COUNT(*) as total, SUM(quantity) as total_volume FROM trades WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date(timestamp) >= date(?)"
            params.append(start_date)
        
        if end_date:
            query += " AND date(timestamp) <= date(?)"
            params.append(end_date)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        # Get winning/losing trades
        query_pnl = query.replace("COUNT(*) as total, SUM(quantity) as total_volume", 
                                  "COUNT(*) as total, SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins, SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses")
        cursor.execute(query_pnl, params)
        pnl_result = cursor.fetchone()
        
        # Get max trade size
        query_max = query.replace("COUNT(*) as total, SUM(quantity) as total_volume", "MAX(quantity) as max_size")
        cursor.execute(query_max, params)
        max_result = cursor.fetchone()
        
        conn.close()
        
        total = result['total'] if result else 0
        total_volume = result['total_volume'] if result and result['total_volume'] else 0
        wins = pnl_result['wins'] if pnl_result else 0
        losses = pnl_result['losses'] if pnl_result else 0
        max_size = max_result['max_size'] if max_result else 0
        
        return {
            "total_trades": total,
            "total_volume": total_volume,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "average_trade_size": (total_volume / total) if total > 0 else 0,
            "max_trade_size": max_size
        }
    except Exception as e:
        logger.error(f"Failed to get trade statistics: {e}")
        return {
            "total_trades": 0,
            "total_volume": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "average_trade_size": 0,
            "max_trade_size": 0
        }

