"""
Main Trading Engine
Orchestrates the entire trading system
"""

import asyncio
import signal
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd

from core.config import config
from core.logger import logger
from core.schwab_api import SchwabAPI
from core.velez_strategy import VelezStrategy
from core.ai_analyzer import AIAnalyzer
from core.trade_executor import TradeExecutor
from core.optimization import StrategyOptimizer

class TradingEngine:
    """Main trading engine that orchestrates all components"""
    
    def __init__(self):
        self.is_running = False
        self.velez_strategy = VelezStrategy()
        self.trade_executor = TradeExecutor()
        self.optimizer = StrategyOptimizer()
        
        # Trading parameters
        self.watchlist = []  # Symbols to monitor
        self.signal_cooldown = {}  # Cooldown between signals for same symbol
        self.cooldown_minutes = 15  # Minimum minutes between signals
        
        # Performance tracking
        self.session_start_time = datetime.now()
        self.signals_generated = 0
        self.trades_executed = 0
        self.ai_validations = 0
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.is_running = False
    
    async def start(self, watchlist: List[str] = None):
        """Start the trading engine"""
        try:
            logger.info("Starting AI Trading Engine...")
            
            # Validate configuration
            if not config.validate_config():
                missing_config = config.get_missing_config()
                logger.error(f"Missing configuration: {missing_config}")
                return False
            
            # Set watchlist
            if watchlist:
                self.watchlist = watchlist
            else:
                # Default watchlist - you can customize this
                self.watchlist = [
                    "SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA",
                    "META", "NFLX", "AMD", "INTC", "CRM", "ADBE", "PYPL"
                ]
            
            logger.info(f"Monitoring {len(self.watchlist)} symbols: {self.watchlist}")
            
            # Start main trading loop
            self.is_running = True
            await self._main_trading_loop()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting trading engine: {str(e)}")
            return False
    
    async def _main_trading_loop(self):
        """Main trading loop"""
        logger.info("Starting main trading loop...")
        
        while self.is_running:
            try:
                # Process each symbol in watchlist
                for symbol in self.watchlist:
                    if not self.is_running:
                        break
                    
                    # Check cooldown
                    if self._is_in_cooldown(symbol):
                        continue
                    
                    # Process symbol
                    await self._process_symbol(symbol)
                    
                    # Small delay between symbols
                    await asyncio.sleep(1)
                
                # Wait before next iteration
                await asyncio.sleep(config.MARKET_DATA_REFRESH_INTERVAL * 60)
                
            except Exception as e:
                logger.error(f"Error in main trading loop: {str(e)}")
                await asyncio.sleep(30)  # Wait before retrying
        
        logger.info("Trading loop stopped")
    
    async def _process_symbol(self, symbol: str):
        """Process a single symbol for trading opportunities"""
        try:
            # Get market data
            async with SchwabAPI() as schwab_api:
                market_data = await schwab_api.get_market_data(
                    symbol=symbol,
                    period_type="day",
                    period=1,
                    frequency_type="minute",
                    frequency=1
                )
                
                if market_data is None or len(market_data) < 20:
                    logger.debug(f"Insufficient market data for {symbol}")
                    return
                
                # Analyze for trading patterns
                signals = self.velez_strategy.analyze_all_patterns(market_data, symbol)
                
                if not signals:
                    return
                
                # Filter and validate signals
                valid_signals = [s for s in signals if self.velez_strategy.validate_signal(s, market_data)]
                
                if not valid_signals:
                    return
                
                # Get the best signal
                best_signal = valid_signals[0]  # Already sorted by confidence
                
                # AI validation
                async with AIAnalyzer() as ai_analyzer:
                    ai_analysis = await ai_analyzer.analyze_signal(best_signal, market_data)
                    self.ai_validations += 1
                    
                    # Check if AI recommends the trade
                    if ai_analysis.get('recommendation') == 'BUY' and ai_analysis.get('confidence_score', 0) >= 75:
                        # Execute trade
                        await self._execute_signal_trade(best_signal, ai_analysis)
                        
                        # Set cooldown
                        self._set_cooldown(symbol)
                        
                        self.signals_generated += 1
                        
                        logger.info(f"Signal processed for {symbol}: {best_signal.signal_type.value}")
                
        except Exception as e:
            logger.error(f"Error processing symbol {symbol}: {str(e)}")
    
    async def _execute_signal_trade(self, signal, ai_analysis: Dict):
        """Execute a trade based on a validated signal"""
        try:
            # Calculate position size based on risk management
            risk_amount = config.MAX_LOSS_PER_TRADE
            stop_loss_distance = abs(signal.entry_price - signal.stop_loss)
            
            if stop_loss_distance == 0:
                logger.warning("Stop loss distance is zero, skipping trade")
                return
            
            # Calculate quantity based on risk
            quantity = int(risk_amount / stop_loss_distance)
            
            if quantity <= 0:
                logger.warning("Calculated quantity is zero or negative, skipping trade")
                return
            
            # Execute the trade
            result = await self.trade_executor.execute_trade(
                symbol=signal.symbol,
                instruction="BUY",
                quantity=quantity,
                order_type="MARKET"
            )
            
            if result:
                self.trades_executed += 1
                
                # Log the trade with AI analysis
                trade_log = {
                    "signal": {
                        "type": signal.signal_type.value,
                        "entry_price": signal.entry_price,
                        "stop_loss": signal.stop_loss,
                        "target_price": signal.target_price,
                        "confidence": signal.confidence
                    },
                    "ai_analysis": ai_analysis,
                    "trade_result": result,
                    "quantity": quantity,
                    "risk_amount": risk_amount
                }
                
                logger.log_trade(trade_log)
                
        except Exception as e:
            logger.error(f"Error executing signal trade: {str(e)}")
    
    def _is_in_cooldown(self, symbol: str) -> bool:
        """Check if symbol is in cooldown period"""
        if symbol not in self.signal_cooldown:
            return False
        
        last_signal_time = self.signal_cooldown[symbol]
        time_since_last = datetime.now() - last_signal_time
        
        return time_since_last.total_seconds() < (self.cooldown_minutes * 60)
    
    def _set_cooldown(self, symbol: str):
        """Set cooldown for symbol"""
        self.signal_cooldown[symbol] = datetime.now()
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics"""
        try:
            runtime = datetime.now() - self.session_start_time
            
            # Get performance metrics
            performance_metrics = await self.trade_executor.get_performance_metrics(1)
            
            return {
                "session_start": self.session_start_time.isoformat(),
                "runtime_hours": round(runtime.total_seconds() / 3600, 2),
                "signals_generated": self.signals_generated,
                "trades_executed": self.trades_executed,
                "ai_validations": self.ai_validations,
                "active_symbols": len(self.watchlist),
                "symbols_in_cooldown": len(self.signal_cooldown),
                "performance_metrics": performance_metrics,
                "is_running": self.is_running
            }
            
        except Exception as e:
            logger.error(f"Error getting session stats: {str(e)}")
            return {}
    
    async def optimize_strategy(self) -> Dict[str, Any]:
        """Trigger strategy optimization"""
        try:
            logger.info("Starting strategy optimization...")
            
            # Analyze performance
            performance_analysis = await self.optimizer.analyze_performance(30)
            
            # Optimize parameters
            optimization_result = await self.optimizer.optimize_strategy_parameters()
            
            return {
                "performance_analysis": performance_analysis,
                "optimization_result": optimization_result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error optimizing strategy: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def generate_daily_report(self) -> Dict[str, Any]:
        """Generate comprehensive daily report"""
        try:
            # Get daily report from trade executor
            daily_report = await self.trade_executor.generate_daily_report()
            
            # Get session stats
            session_stats = await self.get_session_stats()
            
            # Get optimization history
            optimization_history = await self.optimizer.get_optimization_history(1)
            
            # Combine all reports
            comprehensive_report = {
                "daily_report": daily_report,
                "session_stats": session_stats,
                "optimization_history": optimization_history,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("Daily report generated successfully")
            return comprehensive_report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def stop(self):
        """Stop the trading engine"""
        logger.info("Stopping trading engine...")
        self.is_running = False
        
        # Generate final report
        try:
            final_report = await self.generate_daily_report()
            logger.info(f"Final session report: {final_report}")
        except Exception as e:
            logger.error(f"Error generating final report: {str(e)}")
        
        logger.info("Trading engine stopped")

# Global trading engine instance
trading_engine = TradingEngine()
