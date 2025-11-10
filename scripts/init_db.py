#!/usr/bin/env python3
"""
Database Initialization Script
Creates SQLite database and required tables
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config

def init_database():
    """Initialize SQLite database with required tables"""
    
    db_path = Config.DATABASE_PATH
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    print(f"Initializing database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                status TEXT NOT NULL,
                order_id TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL,
                target_price REAL,
                reasoning TEXT,
                processed BOOLEAN DEFAULT 0,
                executed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create optimization_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                parameters TEXT NOT NULL,
                performance_score REAL,
                win_rate REAL,
                total_trades INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create logs table (for structured logging)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                module TEXT,
                function TEXT,
                line_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)")
        
        conn.commit()
        conn.close()
        
        print("[OK] Database initialized successfully")
        print(f"Database file: {db_path}")
        print("\nTables created:")
        print("  - trades")
        print("  - signals")
        print("  - optimization_results")
        print("  - logs")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        return False

def main():
    """Main function"""
    print("=" * 60)
    print("Database Initialization")
    print("=" * 60)
    
    if init_database():
        print("\n[OK] Database setup complete!")
        return 0
    else:
        print("\n[ERROR] Database setup failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

