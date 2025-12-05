"""
Performance Analyzer - Phase 7: Optimization and Intelligent Mode
Tracks trade outcomes and adjusts strategy parameters based on performance.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from utils.logger import setup_logger
import pandas as pd

logger = setup_logger("performance_analyzer")

class PerformanceAnalyzer:
    """
    Analyzes trade performance and adjusts strategy parameters.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.performance_file = self.data_dir / "performance_data.json"
        self.weights_file = self.data_dir / "setup_weights.json"
        self.parameters_file = self.data_dir / "optimized_parameters.json"
        
        # Load existing data
        self.performance_data = self._load_performance_data()
        self.setup_weights = self._load_setup_weights()
        self.optimized_parameters = self._load_optimized_parameters()
    
    def _load_performance_data(self) -> Dict:
        """Load historical performance data."""
        if self.performance_file.exists():
            try:
                with open(self.performance_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load performance data: {e}")
        return {
            "trades": [],
            "setup_stats": {},
            "last_analysis": None
        }
    
    def _load_setup_weights(self) -> Dict[str, float]:
        """Load setup weights (how much to favor each setup type)."""
        default_weights = {
            "whale": 1.0,
            "kamikaze": 1.0,
            "rbi": 1.0,
            "gbi": 1.0,
            "pullback": 1.0,
            "breakout": 1.0
        }
        
        if self.weights_file.exists():
            try:
                with open(self.weights_file, 'r') as f:
                    weights = json.load(f)
                    # Merge with defaults to ensure all setups have weights
                    default_weights.update(weights)
                    return default_weights
            except Exception as e:
                logger.error(f"Failed to load setup weights: {e}")
        
        return default_weights
    
    def _load_optimized_parameters(self) -> Dict:
        """Load optimized trading parameters."""
        default_params = {
            "atr_multiplier": 1.0,
            "stop_distance_atr": 1.5,
            "target_distance_atr": 3.0,
            "trailing_stop_atr": 0.5,
            "breakeven_atr": 1.0,
            "position_scaling_threshold": 1.0,
            "volatility_adjustment": 1.0,
            "last_optimization": None
        }
        
        if self.parameters_file.exists():
            try:
                with open(self.parameters_file, 'r') as f:
                    params = json.load(f)
                    default_params.update(params)
                    return default_params
            except Exception as e:
                logger.error(f"Failed to load optimized parameters: {e}")
        
        return default_params
    
    def _save_performance_data(self):
        """Save performance data to file."""
        try:
            with open(self.performance_file, 'w') as f:
                json.dump(self.performance_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save performance data: {e}")
    
    def _save_setup_weights(self):
        """Save setup weights to file."""
        try:
            with open(self.weights_file, 'w') as f:
                json.dump(self.setup_weights, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save setup weights: {e}")
    
    def _save_optimized_parameters(self):
        """Save optimized parameters to file."""
        try:
            with open(self.parameters_file, 'w') as f:
                json.dump(self.optimized_parameters, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save optimized parameters: {e}")
    
    def record_trade_outcome(self, trade_data: Dict):
        """
        Record a completed trade outcome for analysis.
        
        Args:
            trade_data: Dict with keys:
                - symbol: Stock symbol
                - setup_type: Type of setup (whale, kamikaze, etc.)
                - entry_price: Entry price
                - exit_price: Exit price (or current price if still open)
                - quantity: Number of shares
                - direction: LONG or SHORT
                - pnl: Profit/loss in dollars
                - status: FILLED, CLOSED, OPEN
                - entry_time: Entry timestamp
                - exit_time: Exit timestamp (if closed)
        """
        try:
            trade_record = {
                "symbol": trade_data.get("symbol"),
                "setup_type": trade_data.get("setup_type", "unknown"),
                "entry_price": trade_data.get("entry_price"),
                "exit_price": trade_data.get("exit_price"),
                "quantity": trade_data.get("quantity"),
                "direction": trade_data.get("direction", "LONG"),
                "pnl": trade_data.get("pnl", 0.0),
                "status": trade_data.get("status", "OPEN"),
                "entry_time": trade_data.get("entry_time", datetime.now().isoformat()),
                "exit_time": trade_data.get("exit_time"),
                "recorded_at": datetime.now().isoformat()
            }
            
            self.performance_data["trades"].append(trade_record)
            
            # Keep only last 1000 trades to avoid file bloat
            if len(self.performance_data["trades"]) > 1000:
                self.performance_data["trades"] = self.performance_data["trades"][-1000:]
            
            self._save_performance_data()
            logger.info(f"Recorded trade outcome: {trade_data.get('symbol')} - {trade_data.get('setup_type')} - P&L: ${trade_data.get('pnl', 0):.2f}")
            
        except Exception as e:
            logger.error(f"Failed to record trade outcome: {e}", exc_info=True)
    
    def analyze_performance(self, days: int = 30) -> Dict:
        """
        Analyze trade performance over the last N days.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict with performance metrics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_iso = cutoff_date.isoformat()
            
            # Filter trades within date range
            recent_trades = [
                t for t in self.performance_data["trades"]
                if t.get("entry_time", "") >= cutoff_iso and t.get("status") == "CLOSED"
            ]
            
            if not recent_trades:
                logger.info(f"No closed trades found in last {days} days")
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.0,
                    "total_pnl": 0.0,
                    "avg_win": 0.0,
                    "avg_loss": 0.0,
                    "setup_stats": {},
                    "analysis_date": datetime.now().isoformat()
                }
            
            # Calculate overall stats
            total_trades = len(recent_trades)
            winning_trades = [t for t in recent_trades if t.get("pnl", 0) > 0]
            losing_trades = [t for t in recent_trades if t.get("pnl", 0) <= 0]
            
            total_pnl = sum(t.get("pnl", 0) for t in recent_trades)
            win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0.0
            
            avg_win = sum(t.get("pnl", 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0.0
            avg_loss = sum(t.get("pnl", 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0.0
            
            # Calculate setup-specific stats
            setup_stats = defaultdict(lambda: {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0
            })
            
            for trade in recent_trades:
                setup_type = trade.get("setup_type", "unknown")
                stats = setup_stats[setup_type]
                stats["total"] += 1
                stats["total_pnl"] += trade.get("pnl", 0)
                
                if trade.get("pnl", 0) > 0:
                    stats["wins"] += 1
                else:
                    stats["losses"] += 1
            
            # Calculate win rates and averages for each setup
            for setup_type, stats in setup_stats.items():
                if stats["total"] > 0:
                    stats["win_rate"] = (stats["wins"] / stats["total"]) * 100
                    stats["avg_pnl"] = stats["total_pnl"] / stats["total"]
            
            analysis_result = {
                "total_trades": total_trades,
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "setup_stats": dict(setup_stats),
                "analysis_date": datetime.now().isoformat(),
                "period_days": days
            }
            
            # Store in performance data
            self.performance_data["last_analysis"] = analysis_result
            self.performance_data["setup_stats"] = dict(setup_stats)
            self._save_performance_data()
            
            logger.info(f"Performance analysis complete: {total_trades} trades, {win_rate:.1f}% win rate, ${total_pnl:.2f} P&L")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Failed to analyze performance: {e}", exc_info=True)
            return {}
    
    def adjust_setup_weights(self, min_trades: int = 10) -> Dict[str, float]:
        """
        Adjust setup weights based on performance.
        Higher win rate = higher weight (more likely to trade).
        
        Args:
            min_trades: Minimum number of trades needed to adjust weight
            
        Returns:
            Updated setup weights
        """
        try:
            analysis = self.analyze_performance(days=30)
            setup_stats = analysis.get("setup_stats", {})
            
            if not setup_stats:
                logger.info("No setup stats available for weight adjustment")
                return self.setup_weights
            
            # Calculate new weights based on win rates
            new_weights = {}
            overall_win_rate = analysis.get("win_rate", 50.0)
            
            for setup_type, stats in setup_stats.items():
                if stats["total"] >= min_trades:
                    win_rate = stats["win_rate"]
                    # Weight = (win_rate / overall_win_rate) * base_weight
                    # If win rate is better than average, weight increases
                    # If win rate is worse, weight decreases
                    base_weight = 1.0
                    if overall_win_rate > 0:
                        weight_multiplier = win_rate / overall_win_rate
                        new_weight = base_weight * weight_multiplier
                        # Clamp between 0.3 and 2.0 to avoid extreme values
                        new_weight = max(0.3, min(2.0, new_weight))
                    else:
                        new_weight = base_weight
                    
                    new_weights[setup_type] = round(new_weight, 3)
                    logger.info(f"Setup {setup_type}: win_rate={win_rate:.1f}%, weight={new_weight:.3f}")
                else:
                    # Keep existing weight if not enough data
                    new_weights[setup_type] = self.setup_weights.get(setup_type, 1.0)
            
            # Update weights (merge with existing to keep all setups)
            self.setup_weights.update(new_weights)
            self._save_setup_weights()
            
            logger.info(f"Setup weights adjusted: {new_weights}")
            return self.setup_weights
            
        except Exception as e:
            logger.error(f"Failed to adjust setup weights: {e}", exc_info=True)
            return self.setup_weights
    
    def get_setup_weight(self, setup_type: str) -> float:
        """
        Get the current weight for a setup type.
        
        Args:
            setup_type: Type of setup (whale, kamikaze, etc.)
            
        Returns:
            Weight value (higher = more likely to trade)
        """
        return self.setup_weights.get(setup_type.lower(), 1.0)
    
    def calculate_volatility(self, prices: List[float], period: int = 20) -> float:
        """
        Calculate market volatility using standard deviation of returns.
        
        Args:
            prices: List of recent prices
            period: Number of periods to use
            
        Returns:
            Volatility measure (0.0 to 1.0+)
        """
        try:
            if len(prices) < period:
                return 1.0  # Default volatility
            
            # Calculate returns
            returns = []
            for i in range(1, len(prices)):
                if prices[i-1] > 0:
                    ret = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(ret)
            
            if not returns:
                return 1.0
            
            # Calculate standard deviation
            import statistics
            if len(returns) >= 2:
                volatility = statistics.stdev(returns)
                # Normalize to 0-2 range (1.0 = normal, >1.0 = high volatility)
                normalized_vol = min(2.0, max(0.1, volatility * 100))
                return normalized_vol
            
            return 1.0
            
        except Exception as e:
            logger.error(f"Failed to calculate volatility: {e}")
            return 1.0
    
    def auto_tune_parameters(self, recent_prices: List[float], recent_trades: List[Dict] = None) -> Dict:
        """
        Auto-tune trading parameters based on market volatility and performance.
        
        Args:
            recent_prices: Recent price data for volatility calculation
            recent_trades: Recent trade outcomes (optional)
            
        Returns:
            Optimized parameters dict
        """
        try:
            # Calculate current volatility
            volatility = self.calculate_volatility(recent_prices)
            
            # Base parameters
            base_params = {
                "atr_multiplier": 1.0,
                "stop_distance_atr": 1.5,
                "target_distance_atr": 3.0,
                "trailing_stop_atr": 0.5,
                "breakeven_atr": 1.0,
                "position_scaling_threshold": 1.0
            }
            
            # Adjust based on volatility
            # High volatility = wider stops, lower position size
            # Low volatility = tighter stops, normal position size
            volatility_adjustment = 1.0 / volatility  # Inverse relationship
            
            optimized = {
                "atr_multiplier": base_params["atr_multiplier"] * volatility_adjustment,
                "stop_distance_atr": base_params["stop_distance_atr"] * volatility,  # Wider stops in high vol
                "target_distance_atr": base_params["target_distance_atr"] * volatility,  # Wider targets in high vol
                "trailing_stop_atr": base_params["trailing_stop_atr"] * volatility,
                "breakeven_atr": base_params["breakeven_atr"] * volatility,
                "position_scaling_threshold": base_params["position_scaling_threshold"] * volatility_adjustment,
                "volatility_adjustment": volatility,
                "last_optimization": datetime.now().isoformat()
            }
            
            # If we have recent trade data, adjust based on performance
            if recent_trades and len(recent_trades) >= 5:
                analysis = self.analyze_performance(days=7)  # Last week
                win_rate = analysis.get("win_rate", 50.0)
                
                # If win rate is low, tighten stops (cut losses faster)
                # If win rate is high, can use wider stops (let winners run)
                if win_rate < 40.0:
                    # Low win rate - tighten stops
                    optimized["stop_distance_atr"] *= 0.9
                    optimized["trailing_stop_atr"] *= 0.9
                elif win_rate > 60.0:
                    # High win rate - can use wider stops
                    optimized["stop_distance_atr"] *= 1.1
                    optimized["target_distance_atr"] *= 1.1
            
            # Clamp values to reasonable ranges
            optimized["stop_distance_atr"] = max(1.0, min(3.0, optimized["stop_distance_atr"]))
            optimized["target_distance_atr"] = max(2.0, min(5.0, optimized["target_distance_atr"]))
            optimized["trailing_stop_atr"] = max(0.3, min(1.0, optimized["trailing_stop_atr"]))
            optimized["breakeven_atr"] = max(0.5, min(2.0, optimized["breakeven_atr"]))
            
            # Round values
            for key in optimized:
                if isinstance(optimized[key], float):
                    optimized[key] = round(optimized[key], 2)
            
            self.optimized_parameters.update(optimized)
            self._save_optimized_parameters()
            
            logger.info(f"Parameters auto-tuned: volatility={volatility:.2f}, stop_atr={optimized['stop_distance_atr']:.2f}")
            
            return self.optimized_parameters
            
        except Exception as e:
            logger.error(f"Failed to auto-tune parameters: {e}", exc_info=True)
            return self.optimized_parameters
    
    def get_optimized_parameters(self) -> Dict:
        """Get current optimized parameters."""
        return self.optimized_parameters.copy()
    
    def get_performance_summary(self) -> Dict:
        """Get summary of performance and optimization status."""
        return {
            "setup_weights": self.setup_weights,
            "optimized_parameters": self.optimized_parameters,
            "last_analysis": self.performance_data.get("last_analysis"),
            "total_trades_recorded": len(self.performance_data.get("trades", [])),
            "last_optimization": self.optimized_parameters.get("last_optimization")
        }

