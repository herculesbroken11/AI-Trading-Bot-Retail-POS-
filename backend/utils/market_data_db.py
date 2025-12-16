"""
Time-Series Database for Market Data Storage
Stores OHLCV data, VWAP, and technical indicators (EMA 20, EMA 200).
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from utils.logger import setup_logger

logger = setup_logger("market_data_db")

DB_PATH = Path("data/market_data.db")

def get_db_connection():
    """Get SQLite database connection for market data."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_market_data_db():
    """Initialize market data database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create market_data table for time-series OHLCV data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            timeframe TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            vwap REAL,
            ema_20 REAL,
            ema_200 REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timestamp, timeframe)
        )
    """)
    
    # Create indexes for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_timeframe ON market_data(symbol, timeframe)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON market_data(timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON market_data(symbol, timestamp)
    """)
    
    # Create chart_metadata table for storing chart image metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chart_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            chart_type TEXT DEFAULT 'candlestick',
            indicators TEXT,  -- JSON array of indicators included
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timeframe, timestamp)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chart_symbol_timeframe ON chart_metadata(symbol, timeframe)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chart_timestamp ON chart_metadata(timestamp)
    """)
    
    conn.commit()
    conn.close()
    logger.info("Market data database initialized")

def store_market_data(
    symbol: str,
    timestamp: int,
    timeframe: str,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: int,
    vwap: Optional[float] = None,
    ema_20: Optional[float] = None,
    ema_200: Optional[float] = None
):
    """
    Store market data bar (OHLCV) in database.
    
    Args:
        symbol: Stock symbol
        timestamp: Unix timestamp in milliseconds
        timeframe: Timeframe ('1min', '5min', 'daily')
        open_price: Open price
        high: High price
        low: Low price
        close: Close price
        volume: Volume
        vwap: Volume-weighted average price (optional)
        ema_20: EMA 20 value (optional)
        ema_200: EMA 200 value (optional)
    """
    try:
        init_market_data_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO market_data 
            (symbol, timestamp, timeframe, open, high, low, close, volume, vwap, ema_20, ema_200)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol.upper(),
            timestamp,
            timeframe,
            open_price,
            high,
            low,
            close,
            volume,
            vwap,
            ema_20,
            ema_200
        ))
        
        conn.commit()
        conn.close()
        logger.debug(f"Stored market data: {symbol} {timeframe} @ {timestamp}")
    
    except Exception as e:
        logger.error(f"Failed to store market data: {e}", exc_info=True)

def get_market_data(
    symbol: str,
    timeframe: str,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
    limit: Optional[int] = None
) -> pd.DataFrame:
    """
    Retrieve market data from database.
    
    Args:
        symbol: Stock symbol
        timeframe: Timeframe ('1min', '5min', 'daily')
        start_timestamp: Start timestamp in milliseconds (optional)
        end_timestamp: End timestamp in milliseconds (optional)
        limit: Maximum number of records (optional)
        
    Returns:
        DataFrame with market data
    """
    try:
        init_market_data_db()
        conn = get_db_connection()
        
        query = """
            SELECT timestamp, open, high, low, close, volume, vwap, ema_20, ema_200
            FROM market_data
            WHERE symbol = ? AND timeframe = ?
        """
        params = [symbol.upper(), timeframe]
        
        if start_timestamp:
            query += " AND timestamp >= ?"
            params.append(start_timestamp)
        
        if end_timestamp:
            query += " AND timestamp <= ?"
            params.append(end_timestamp)
        
        query += " ORDER BY timestamp ASC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if not df.empty:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('datetime', inplace=True)
        
        return df
    
    except Exception as e:
        logger.error(f"Failed to get market data: {e}", exc_info=True)
        return pd.DataFrame()

def store_chart_metadata(
    symbol: str,
    timeframe: str,
    timestamp: int,
    filename: str,
    filepath: str,
    indicators: Optional[List[str]] = None
):
    """
    Store chart image metadata.
    
    Args:
        symbol: Stock symbol
        timeframe: Timeframe ('1min', '5min', 'daily')
        timestamp: Unix timestamp in milliseconds
        filename: Chart filename
        filepath: Full path to chart file
        indicators: List of indicators included in chart
    """
    try:
        init_market_data_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        indicators_json = json.dumps(indicators) if indicators else None
        
        cursor.execute("""
            INSERT OR REPLACE INTO chart_metadata
            (symbol, timeframe, timestamp, filename, filepath, indicators)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            symbol.upper(),
            timeframe,
            timestamp,
            filename,
            filepath,
            indicators_json
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Stored chart metadata: {filename}")
    
    except Exception as e:
        logger.error(f"Failed to store chart metadata: {e}", exc_info=True)

def get_chart_metadata(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve chart metadata.
    
    Args:
        symbol: Stock symbol (optional)
        timeframe: Timeframe (optional)
        start_timestamp: Start timestamp (optional)
        end_timestamp: End timestamp (optional)
        limit: Maximum number of records (optional)
        
    Returns:
        List of chart metadata dictionaries
    """
    try:
        init_market_data_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM chart_metadata WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)
        
        if start_timestamp:
            query += " AND timestamp >= ?"
            params.append(start_timestamp)
        
        if end_timestamp:
            query += " AND timestamp <= ?"
            params.append(end_timestamp)
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        charts = []
        for row in rows:
            chart = dict(row)
            if chart.get('indicators'):
                import json
                chart['indicators'] = json.loads(chart['indicators'])
            charts.append(chart)
        
        conn.close()
        return charts
    
    except Exception as e:
        logger.error(f"Failed to get chart metadata: {e}", exc_info=True)
        return []

def detect_data_gaps(
    symbol: str,
    timeframe: str,
    start_timestamp: int,
    end_timestamp: int
) -> List[Dict[str, int]]:
    """
    Detect gaps in market data.
    
    Args:
        symbol: Stock symbol
        timeframe: Timeframe
        start_timestamp: Start timestamp
        end_timestamp: End timestamp
        
    Returns:
        List of gap dictionaries with start and end timestamps
    """
    try:
        df = get_market_data(symbol, timeframe, start_timestamp, end_timestamp)
        
        if df.empty:
            return [{"start": start_timestamp, "end": end_timestamp}]
        
        gaps = []
        
        # Calculate expected interval in milliseconds
        if timeframe == '1min':
            interval_ms = 60 * 1000
        elif timeframe == '5min':
            interval_ms = 5 * 60 * 1000
        elif timeframe == 'daily':
            interval_ms = 24 * 60 * 60 * 1000
        else:
            return []
        
        # Check for gaps
        timestamps = sorted(df['timestamp'].tolist())
        
        for i in range(len(timestamps) - 1):
            gap = timestamps[i + 1] - timestamps[i]
            if gap > interval_ms * 2:  # More than 2 intervals = gap
                gaps.append({
                    "start": timestamps[i] + interval_ms,
                    "end": timestamps[i + 1] - interval_ms
                })
        
        return gaps
    
    except Exception as e:
        logger.error(f"Failed to detect data gaps: {e}", exc_info=True)
        return []

# Import json for indicators serialization
import json

