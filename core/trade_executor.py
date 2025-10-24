"""
Trade Execution Engine
Handles trade execution with risk management and position tracking
"""

import asyncio
import sqlite3
import csv
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass
from enum import Enum

from core.config import config
from core.logger import logger
from core.schwab_api import SchwabAPI

class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass
class Trade:
    """Trade data structure"""
    id: str
    symbol: str
    instruction: str
    quantity: int
    price: float
    order_type: str
    status: OrderStatus
    timestamp: datetime
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    pnl: Optional[float] = None
    fees: Optional[float] = None

class TradeExecutor:
    """Trade execution engine with risk management"""
    
    def __init__(self):
        self.max_loss_per_trade = config.MAX_LOSS_PER_TRADE
        self.max_position_size = config.MAX_POSITION_SIZE
        self.risk_percentage = config.RISK_PERCENTAGE
        self.db_path = config.DATABASE_PATH
        self.active_trades = {}
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_losses = 0
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for trade tracking"""
        try:
            import os
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create trades table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id TEXT PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        instruction TEXT NOT NULL,
                        quantity INTEGER NOT NULL,
                        price REAL NOT NULL,
                        order_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        stop_loss REAL,
                        target_price REAL,
                        pnl REAL,
                        fees REAL
                    )
                """)
                
                # Create daily_reports table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_reports (
                        date TEXT PRIMARY KEY,
                        total_trades INTEGER,
                        successful_trades INTEGER,
                        failed_trades INTEGER,
                        total_pnl REAL,
                        total_volume REAL,
                        max_drawdown REAL,
                        win_rate REAL
                    )
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
    
    async def execute_trade(self, symbol: str, instruction: str, quantity: int, 
                          order_type: str = "MARKET", price: Optional[float] = None) -> Optional[Dict]:
        """
        Execute a trade with risk management
        """
        try:
            # Risk management checks
            if not await self._validate_trade_risk(symbol, instruction, quantity, price):
                logger.warning(f"Trade rejected due to risk management: {symbol}")
                return None
            
            # Create trade record
            trade_id = f"{symbol}_{instruction}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            async with SchwabAPI() as schwab_api:
                # Create order
                if order_type == "MARKET":
                    order_data = schwab_api.create_market_order(symbol, instruction, quantity)
                elif order_type == "LIMIT":
                    if price is None:
                        raise ValueError("Price required for limit orders")
                    order_data = schwab_api.create_limit_order(symbol, instruction, quantity, price)
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")
                
                # Execute order
                result = await schwab_api.place_order(order_data)
                
                if result:
                    # Record trade
                    trade = Trade(
                        id=trade_id,
                        symbol=symbol,
                        instruction=instruction,
                        quantity=quantity,
                        price=price or 0.0,  # Will be updated when filled
                        order_type=order_type,
                        status=OrderStatus.PENDING,
                        timestamp=datetime.now()
                    )
                    
                    # Store in database
                    await self._store_trade(trade)
                    
                    # Track active trade
                    self.active_trades[trade_id] = trade
                    
                    logger.info(f"Trade executed successfully: {trade_id}")
                    return {
                        "trade_id": trade_id,
                        "status": "PENDING",
                        "order_data": order_data
                    }
                else:
                    logger.error(f"Trade execution failed: {symbol}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            return None
    
    async def _validate_trade_risk(self, symbol: str, instruction: str, 
                                 quantity: int, price: Optional[float]) -> bool:
        """
        Validate trade against risk management rules
        """
        try:
            # Check position size
            position_value = quantity * (price or 0.0)
            if position_value > self.max_position_size:
                logger.warning(f"Position size {position_value} exceeds maximum {self.max_position_size}")
                return False
            
            # Check daily loss limit
            if self.daily_pnl < -self.max_loss_per_trade:
                logger.warning(f"Daily loss limit exceeded: {self.daily_pnl}")
                return False
            
            # Check number of daily trades
            if self.daily_trades >= 50:  # Arbitrary limit
                logger.warning("Daily trade limit exceeded")
                return False
            
            # Check for existing positions in same symbol
            async with SchwabAPI() as schwab_api:
                positions = await schwab_api.get_positions()
                if positions:
                    for position in positions:
                        if position.get('instrument', {}).get('symbol') == symbol:
                            current_quantity = position.get('longQuantity', 0) - position.get('shortQuantity', 0)
                            new_quantity = current_quantity + (quantity if instruction == "BUY" else -quantity)
                            
                            if abs(new_quantity) > self.max_position_size:
                                logger.warning(f"Position size would exceed limit for {symbol}")
                                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating trade risk: {str(e)}")
            return False
    
    async def _store_trade(self, trade: Trade):
        """Store trade in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO trades 
                    (id, symbol, instruction, quantity, price, order_type, status, timestamp, stop_loss, target_price, pnl, fees)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.id, trade.symbol, trade.instruction, trade.quantity,
                    trade.price, trade.order_type, trade.status.value,
                    trade.timestamp.isoformat(), trade.stop_loss, trade.target_price,
                    trade.pnl, trade.fees
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing trade: {str(e)}")
    
    async def update_trade_status(self, trade_id: str, status: OrderStatus, 
                                fill_price: Optional[float] = None):
        """Update trade status"""
        try:
            if trade_id in self.active_trades:
                trade = self.active_trades[trade_id]
                trade.status = status
                
                if fill_price:
                    trade.price = fill_price
                
                # Update database
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE trades 
                        SET status = ?, price = ?
                        WHERE id = ?
                    """, (status.value, trade.price, trade_id))
                    conn.commit()
                
                # Remove from active trades if filled or cancelled
                if status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    del self.active_trades[trade_id]
                
                logger.info(f"Trade status updated: {trade_id} -> {status.value}")
                
        except Exception as e:
            logger.error(f"Error updating trade status: {str(e)}")
    
    async def get_trade_history(self, days: int = 30) -> List[Dict]:
        """Get trade history for specified number of days"""
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM trades 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp DESC
                """, (start_date,))
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                trades = []
                for row in rows:
                    trade_dict = dict(zip(columns, row))
                    trades.append(trade_dict)
                
                return trades
                
        except Exception as e:
            logger.error(f"Error getting trade history: {str(e)}")
            return []
    
    async def generate_daily_report(self) -> Dict[str, Any]:
        """Generate daily P&L and compliance report"""
        try:
            today = datetime.now().date().isoformat()
            
            # Get today's trades
            trades = await self.get_trade_history(1)
            today_trades = [t for t in trades if t['timestamp'].startswith(today)]
            
            # Calculate metrics
            total_trades = len(today_trades)
            successful_trades = len([t for t in today_trades if t['status'] == 'FILLED'])
            failed_trades = len([t for t in today_trades if t['status'] in ['CANCELLED', 'REJECTED']])
            
            # Calculate P&L
            total_pnl = sum(t.get('pnl', 0) for t in today_trades if t['pnl'] is not None)
            total_volume = sum(t['quantity'] * t['price'] for t in today_trades if t['status'] == 'FILLED')
            
            # Calculate win rate
            win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate max drawdown
            max_drawdown = min(t.get('pnl', 0) for t in today_trades if t['pnl'] is not None) if today_trades else 0
            
            report = {
                "date": today,
                "total_trades": total_trades,
                "successful_trades": successful_trades,
                "failed_trades": failed_trades,
                "total_pnl": round(total_pnl, 2),
                "total_volume": round(total_volume, 2),
                "max_drawdown": round(max_drawdown, 2),
                "win_rate": round(win_rate, 2),
                "active_trades": len(self.active_trades),
                "daily_losses": self.daily_losses,
                "risk_metrics": {
                    "max_loss_per_trade": self.max_loss_per_trade,
                    "max_position_size": self.max_position_size,
                    "risk_percentage": self.risk_percentage
                }
            }
            
            # Store daily report
            await self._store_daily_report(report)
            
            logger.info(f"Daily report generated: {report}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            return {}
    
    async def _store_daily_report(self, report: Dict[str, Any]):
        """Store daily report in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_reports 
                    (date, total_trades, successful_trades, failed_trades, total_pnl, total_volume, max_drawdown, win_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report['date'], report['total_trades'], report['successful_trades'],
                    report['failed_trades'], report['total_pnl'], report['total_volume'],
                    report['max_drawdown'], report['win_rate']
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing daily report: {str(e)}")
    
    async def log_trade_execution(self, symbol: str, instruction: str, 
                                quantity: int, result: Dict):
        """Log trade execution for audit trail"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "instruction": instruction,
                "quantity": quantity,
                "result": result
            }
            
            # Log to file
            logger.log_trade(log_entry)
            
            # Update daily counters
            self.daily_trades += 1
            
            # Update daily P&L if trade was successful
            if result.get("status") == "PENDING":
                # This would be updated when the trade is filled
                pass
            
        except Exception as e:
            logger.error(f"Error logging trade execution: {str(e)}")
    
    async def export_trades_csv(self, days: int = 30) -> str:
        """Export trade history to CSV"""
        try:
            trades = await self.get_trade_history(days)
            
            if not trades:
                return ""
            
            filename = f"trades_export_{datetime.now().strftime('%Y%m%d')}.csv"
            filepath = f"./data/{filename}"
            
            with open(filepath, 'w', newline='') as csvfile:
                if trades:
                    fieldnames = trades[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(trades)
            
            logger.info(f"Trade history exported to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting trades to CSV: {str(e)}")
            return ""
    
    async def get_performance_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get performance metrics for specified period"""
        try:
            trades = await self.get_trade_history(days)
            
            if not trades:
                return {}
            
            # Calculate metrics
            total_trades = len(trades)
            filled_trades = [t for t in trades if t['status'] == 'FILLED']
            successful_trades = len(filled_trades)
            
            total_pnl = sum(t.get('pnl', 0) for t in filled_trades if t['pnl'] is not None)
            total_volume = sum(t['quantity'] * t['price'] for t in filled_trades)
            
            # Calculate win rate
            win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate average trade size
            avg_trade_size = total_volume / len(filled_trades) if filled_trades else 0
            
            # Calculate Sharpe ratio (simplified)
            pnl_values = [t.get('pnl', 0) for t in filled_trades if t['pnl'] is not None]
            if len(pnl_values) > 1:
                import statistics
                sharpe_ratio = statistics.mean(pnl_values) / statistics.stdev(pnl_values) if statistics.stdev(pnl_values) > 0 else 0
            else:
                sharpe_ratio = 0
            
            return {
                "period_days": days,
                "total_trades": total_trades,
                "successful_trades": successful_trades,
                "total_pnl": round(total_pnl, 2),
                "total_volume": round(total_volume, 2),
                "win_rate": round(win_rate, 2),
                "average_trade_size": round(avg_trade_size, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "max_drawdown": round(min(pnl_values) if pnl_values else 0, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")
            return {}
