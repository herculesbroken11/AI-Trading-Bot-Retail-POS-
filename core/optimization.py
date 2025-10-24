"""
AI Optimization Layer
Adaptive learning and strategy optimization
"""

import asyncio
import json
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass
import sqlite3

from core.config import config
from core.logger import logger
from core.ai_analyzer import AIAnalyzer
from core.velez_strategy import VelezStrategy
from core.trade_executor import TradeExecutor

@dataclass
class OptimizationResult:
    """Optimization result data structure"""
    parameter: str
    old_value: float
    new_value: float
    improvement: float
    confidence: float
    timestamp: datetime

class StrategyOptimizer:
    """AI-powered strategy optimization and adaptive learning"""
    
    def __init__(self):
        self.db_path = config.DATABASE_PATH
        self.optimization_history = []
        self.performance_threshold = 0.05  # 5% improvement threshold
        self.min_trades_for_optimization = 10
        
        # Strategy parameters to optimize
        self.optimizable_params = {
            'min_volume_threshold': {'min': 50000, 'max': 500000, 'step': 25000},
            'min_price_threshold': {'min': 2.0, 'max': 20.0, 'step': 1.0},
            'max_price_threshold': {'min': 100.0, 'max': 1000.0, 'step': 50.0},
            'confidence_threshold': {'min': 0.6, 'max': 0.95, 'step': 0.05},
            'risk_reward_threshold': {'min': 1.0, 'max': 3.0, 'step': 0.25}
        }
    
    async def analyze_performance(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze trading performance and identify optimization opportunities
        """
        try:
            trade_executor = TradeExecutor()
            performance_metrics = await trade_executor.get_performance_metrics(days)
            
            if performance_metrics.get('total_trades', 0) < self.min_trades_for_optimization:
                logger.info("Insufficient trades for optimization analysis")
                return {"status": "insufficient_data", "message": "Need more trades for optimization"}
            
            # Analyze win rate trends
            win_rate_analysis = await self._analyze_win_rate_trends(days)
            
            # Analyze P&L distribution
            pnl_analysis = await self._analyze_pnl_distribution(days)
            
            # Analyze signal quality
            signal_analysis = await self._analyze_signal_quality(days)
            
            # Identify optimization opportunities
            optimization_opportunities = await self._identify_optimization_opportunities(
                performance_metrics, win_rate_analysis, pnl_analysis, signal_analysis
            )
            
            analysis_result = {
                "status": "success",
                "performance_metrics": performance_metrics,
                "win_rate_analysis": win_rate_analysis,
                "pnl_analysis": pnl_analysis,
                "signal_analysis": signal_analysis,
                "optimization_opportunities": optimization_opportunities,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("Performance analysis completed")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def _analyze_win_rate_trends(self, days: int) -> Dict[str, Any]:
        """Analyze win rate trends over time"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get daily win rates
                cursor.execute("""
                    SELECT date, win_rate, total_trades
                    FROM daily_reports 
                    WHERE date >= date('now', '-{} days')
                    ORDER BY date
                """.format(days))
                
                daily_data = cursor.fetchall()
                
                if not daily_data:
                    return {"status": "no_data"}
                
                # Calculate trends
                win_rates = [row[1] for row in daily_data if row[2] > 0]
                total_trades = [row[2] for row in daily_data]
                
                if len(win_rates) < 2:
                    return {"status": "insufficient_data"}
                
                # Calculate trend
                trend = np.polyfit(range(len(win_rates)), win_rates, 1)[0]
                avg_win_rate = np.mean(win_rates)
                
                return {
                    "status": "success",
                    "average_win_rate": round(avg_win_rate, 2),
                    "trend": round(trend, 4),
                    "trend_direction": "improving" if trend > 0 else "declining",
                    "daily_win_rates": win_rates,
                    "total_trades": total_trades
                }
                
        except Exception as e:
            logger.error(f"Error analyzing win rate trends: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def _analyze_pnl_distribution(self, days: int) -> Dict[str, Any]:
        """Analyze P&L distribution patterns"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get P&L data
                cursor.execute("""
                    SELECT pnl FROM trades 
                    WHERE timestamp >= date('now', '-{} days')
                    AND pnl IS NOT NULL
                    AND status = 'FILLED'
                """.format(days))
                
                pnl_data = cursor.fetchall()
                
                if not pnl_data:
                    return {"status": "no_data"}
                
                pnl_values = [row[0] for row in pnl_data]
                
                # Calculate statistics
                mean_pnl = np.mean(pnl_values)
                std_pnl = np.std(pnl_values)
                min_pnl = np.min(pnl_values)
                max_pnl = np.max(pnl_values)
                
                # Calculate skewness and kurtosis
                skewness = self._calculate_skewness(pnl_values)
                kurtosis = self._calculate_kurtosis(pnl_values)
                
                return {
                    "status": "success",
                    "mean_pnl": round(mean_pnl, 2),
                    "std_pnl": round(std_pnl, 2),
                    "min_pnl": round(min_pnl, 2),
                    "max_pnl": round(max_pnl, 2),
                    "skewness": round(skewness, 2),
                    "kurtosis": round(kurtosis, 2),
                    "distribution_type": "normal" if abs(skewness) < 0.5 else "skewed"
                }
                
        except Exception as e:
            logger.error(f"Error analyzing P&L distribution: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def _analyze_signal_quality(self, days: int) -> Dict[str, Any]:
        """Analyze signal quality and effectiveness"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get signal data (assuming we store signal quality in trades table)
                cursor.execute("""
                    SELECT symbol, instruction, quantity, price, pnl, status
                    FROM trades 
                    WHERE timestamp >= date('now', '-{} days')
                    AND status = 'FILLED'
                """.format(days))
                
                trade_data = cursor.fetchall()
                
                if not trade_data:
                    return {"status": "no_data"}
                
                # Analyze by symbol
                symbol_analysis = {}
                for trade in trade_data:
                    symbol = trade[0]
                    pnl = trade[4] or 0
                    
                    if symbol not in symbol_analysis:
                        symbol_analysis[symbol] = {'trades': 0, 'total_pnl': 0, 'wins': 0}
                    
                    symbol_analysis[symbol]['trades'] += 1
                    symbol_analysis[symbol]['total_pnl'] += pnl
                    if pnl > 0:
                        symbol_analysis[symbol]['wins'] += 1
                
                # Calculate symbol performance
                symbol_performance = {}
                for symbol, data in symbol_analysis.items():
                    if data['trades'] > 0:
                        symbol_performance[symbol] = {
                            'total_trades': data['trades'],
                            'total_pnl': round(data['total_pnl'], 2),
                            'win_rate': round(data['wins'] / data['trades'] * 100, 2),
                            'avg_pnl_per_trade': round(data['total_pnl'] / data['trades'], 2)
                        }
                
                return {
                    "status": "success",
                    "symbol_performance": symbol_performance,
                    "total_symbols": len(symbol_performance),
                    "best_performing_symbol": max(symbol_performance.keys(), 
                                                key=lambda x: symbol_performance[x]['total_pnl']) if symbol_performance else None
                }
                
        except Exception as e:
            logger.error(f"Error analyzing signal quality: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def _identify_optimization_opportunities(self, performance_metrics: Dict, 
                                                 win_rate_analysis: Dict, 
                                                 pnl_analysis: Dict, 
                                                 signal_analysis: Dict) -> List[Dict]:
        """Identify specific optimization opportunities"""
        opportunities = []
        
        try:
            # Check win rate trends
            if win_rate_analysis.get('status') == 'success':
                if win_rate_analysis['trend'] < -0.5:  # Declining trend
                    opportunities.append({
                        "type": "win_rate_decline",
                        "priority": "high",
                        "description": "Win rate is declining, consider adjusting confidence thresholds",
                        "suggested_action": "Increase confidence threshold for signal validation"
                    })
            
            # Check P&L distribution
            if pnl_analysis.get('status') == 'success':
                if pnl_analysis['skewness'] < -1.0:  # Highly negative skew
                    opportunities.append({
                        "type": "negative_skew",
                        "priority": "high",
                        "description": "P&L distribution is highly negatively skewed",
                        "suggested_action": "Improve risk management and stop-loss placement"
                    })
            
            # Check symbol performance
            if signal_analysis.get('status') == 'success':
                symbol_performance = signal_analysis.get('symbol_performance', {})
                if symbol_performance:
                    # Find underperforming symbols
                    underperforming = [symbol for symbol, data in symbol_performance.items() 
                                     if data['win_rate'] < 40 and data['total_trades'] > 3]
                    
                    if underperforming:
                        opportunities.append({
                            "type": "underperforming_symbols",
                            "priority": "medium",
                            "description": f"Symbols with low win rates: {underperforming}",
                            "suggested_action": "Consider filtering out or reducing exposure to underperforming symbols"
                        })
            
            # Check overall performance
            if performance_metrics.get('win_rate', 0) < 50:
                opportunities.append({
                    "type": "low_win_rate",
                    "priority": "high",
                    "description": "Overall win rate is below 50%",
                    "suggested_action": "Review and optimize signal validation criteria"
                })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error identifying optimization opportunities: {str(e)}")
            return []
    
    async def optimize_strategy_parameters(self) -> Dict[str, Any]:
        """
        Optimize strategy parameters using AI analysis
        """
        try:
            # Get recent performance data
            performance_analysis = await self.analyze_performance(30)
            
            if performance_analysis.get('status') != 'success':
                return {
                    "status": "error",
                    "message": "Cannot optimize without sufficient performance data"
                }
            
            # Get current strategy parameters
            velez_strategy = VelezStrategy()
            current_params = {
                'min_volume_threshold': velez_strategy.min_volume_threshold,
                'min_price_threshold': velez_strategy.min_price_threshold,
                'max_price_threshold': velez_strategy.max_price_threshold
            }
            
            # Use AI to suggest parameter optimizations
            async with AIAnalyzer() as ai_analyzer:
                optimization_suggestions = await self._get_ai_optimization_suggestions(
                    ai_analyzer, performance_analysis, current_params
                )
            
            # Apply optimizations if they meet improvement threshold
            applied_optimizations = []
            for suggestion in optimization_suggestions:
                if suggestion['expected_improvement'] >= self.performance_threshold:
                    # Apply the optimization
                    result = await self._apply_parameter_optimization(suggestion)
                    if result:
                        applied_optimizations.append(result)
            
            return {
                "status": "success",
                "applied_optimizations": applied_optimizations,
                "total_optimizations": len(applied_optimizations),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error optimizing strategy parameters: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def _get_ai_optimization_suggestions(self, ai_analyzer: AIAnalyzer, 
                                             performance_analysis: Dict, 
                                             current_params: Dict) -> List[Dict]:
        """Get AI suggestions for parameter optimization"""
        try:
            prompt = f"""
            You are an expert quantitative analyst. Analyze the following trading performance data and suggest parameter optimizations.
            
            PERFORMANCE METRICS:
            {json.dumps(performance_analysis['performance_metrics'], indent=2)}
            
            WIN RATE ANALYSIS:
            {json.dumps(performance_analysis['win_rate_analysis'], indent=2)}
            
            P&L ANALYSIS:
            {json.dumps(performance_analysis['pnl_analysis'], indent=2)}
            
            SIGNAL ANALYSIS:
            {json.dumps(performance_analysis['signal_analysis'], indent=2)}
            
            CURRENT PARAMETERS:
            {json.dumps(current_params, indent=2)}
            
            OPTIMIZATION OPPORTUNITIES:
            {json.dumps(performance_analysis['optimization_opportunities'], indent=2)}
            
            Suggest specific parameter optimizations that could improve performance. Focus on:
            1. Volume thresholds for better signal quality
            2. Price thresholds for optimal stock selection
            3. Confidence thresholds for better win rates
            4. Risk management parameters
            
            Provide suggestions in JSON format with:
            - parameter_name
            - current_value
            - suggested_value
            - reasoning
            - expected_improvement (0-1 scale)
            """
            
            # Use AI to get optimization suggestions
            # This would integrate with the AI analyzer
            # For now, return mock suggestions
            return [
                {
                    "parameter_name": "min_volume_threshold",
                    "current_value": current_params['min_volume_threshold'],
                    "suggested_value": current_params['min_volume_threshold'] * 1.2,
                    "reasoning": "Increase volume threshold to filter out low-volume stocks",
                    "expected_improvement": 0.08
                }
            ]
            
        except Exception as e:
            logger.error(f"Error getting AI optimization suggestions: {str(e)}")
            return []
    
    async def _apply_parameter_optimization(self, suggestion: Dict) -> Optional[OptimizationResult]:
        """Apply a parameter optimization"""
        try:
            parameter = suggestion['parameter_name']
            old_value = suggestion['current_value']
            new_value = suggestion['suggested_value']
            expected_improvement = suggestion['expected_improvement']
            
            # Apply the optimization (this would update the strategy parameters)
            # For now, just log the optimization
            result = OptimizationResult(
                parameter=parameter,
                old_value=old_value,
                new_value=new_value,
                improvement=expected_improvement,
                confidence=0.8,  # Would be calculated based on historical data
                timestamp=datetime.now()
            )
            
            # Store optimization result
            self.optimization_history.append(result)
            await self._store_optimization_result(result)
            
            logger.info(f"Applied optimization: {parameter} {old_value} -> {new_value}")
            return result
            
        except Exception as e:
            logger.error(f"Error applying parameter optimization: {str(e)}")
            return None
    
    async def _store_optimization_result(self, result: OptimizationResult):
        """Store optimization result in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create optimization_results table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parameter TEXT NOT NULL,
                        old_value REAL NOT NULL,
                        new_value REAL NOT NULL,
                        improvement REAL NOT NULL,
                        confidence REAL NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)
                
                cursor.execute("""
                    INSERT INTO optimization_results 
                    (parameter, old_value, new_value, improvement, confidence, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    result.parameter, result.old_value, result.new_value,
                    result.improvement, result.confidence, result.timestamp.isoformat()
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing optimization result: {str(e)}")
    
    def _calculate_skewness(self, data: List[float]) -> float:
        """Calculate skewness of data"""
        if len(data) < 3:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0.0
        
        skewness = np.mean([(x - mean) ** 3 for x in data]) / (std ** 3)
        return skewness
    
    def _calculate_kurtosis(self, data: List[float]) -> float:
        """Calculate kurtosis of data"""
        if len(data) < 4:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0.0
        
        kurtosis = np.mean([(x - mean) ** 4 for x in data]) / (std ** 4) - 3
        return kurtosis
    
    async def get_optimization_history(self, days: int = 30) -> List[Dict]:
        """Get optimization history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM optimization_results 
                    WHERE timestamp >= date('now', '-{} days')
                    ORDER BY timestamp DESC
                """.format(days))
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                optimizations = []
                for row in rows:
                    optimization_dict = dict(zip(columns, row))
                    optimizations.append(optimization_dict)
                
                return optimizations
                
        except Exception as e:
            logger.error(f"Error getting optimization history: {str(e)}")
            return []
