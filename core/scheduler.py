"""
Automated Trading Scheduler
Continuously monitors market and executes trades based on OV strategy.
"""
import os
import time
import schedule
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from utils.logger import setup_logger
from core.ov_engine import OVStrategyEngine
from core.position_manager import PositionManager
from ai.analyze import TradingAIAnalyzer
from api.orders import execute_signal_helper
from utils.helpers import get_valid_access_token, schwab_api_request
from api.quotes import SCHWAB_HISTORICAL_URL, SCHWAB_QUOTES_URL

logger = setup_logger("scheduler")

class TradingScheduler:
    """
    Automated scheduler for continuous market analysis and trade execution.
    """
    
    def __init__(self):
        self.ov_engine = OVStrategyEngine()
        self.position_manager = PositionManager()
        # Lazy initialization of AI analyzer to avoid import errors at startup
        self.ai_analyzer = None
        self.watchlist = self._load_watchlist()
        self.is_running = False
    
    def _get_ai_analyzer(self):
        """Get or initialize AI analyzer (lazy initialization)."""
        if self.ai_analyzer is None:
            try:
                self.ai_analyzer = TradingAIAnalyzer()
            except Exception as e:
                logger.error(f"Failed to initialize AI analyzer: {e}")
                logger.warning("Trading will continue without AI validation")
                # Return a dummy analyzer that always returns HOLD
                class DummyAnalyzer:
                    def analyze_market_data(self, symbol, market_summary, setup):
                        return {
                            "action": "HOLD",
                            "confidence": 0.0,
                            "reasoning": "AI analyzer unavailable"
                        }
                self.ai_analyzer = DummyAnalyzer()
        return self.ai_analyzer
        
    def _load_watchlist(self) -> List[str]:
        """Load trading watchlist from environment or file."""
        watchlist_str = os.getenv("TRADING_WATCHLIST", "AAPL,MSFT,GOOGL,TSLA,NVDA")
        return [s.strip().upper() for s in watchlist_str.split(",")]
    
    def is_market_hours(self) -> bool:
        """
        Check if current time is within market hours (9:30 AM - 4:00 PM ET).
        
        Returns:
            True if market is open
        """
        # Get current time in ET
        now_utc = datetime.now(timezone.utc)
        # ET is UTC-5 (EST) or UTC-4 (EDT) - using UTC-5 for simplicity
        et_offset = -5
        now_et = now_utc.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=et_offset)))
        
        # Check if weekday (Monday=0, Friday=4)
        if now_et.weekday() >= 5:  # Saturday or Sunday
            return False
        
        current_time = now_et.time()
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("16:00", "%H:%M").time()
        
        return market_open <= current_time <= market_close
    
    def analyze_and_trade(self):
        """
        Analyze watchlist symbols and execute trades if signals found.
        Runs every 5 minutes during market hours.
        """
        if not self.is_market_hours():
            logger.debug("Outside market hours - skipping analysis")
            return
        
        if not self.is_running:
            return
        
        logger.info("Starting automated market analysis...")
        
        # Get valid access token (automatically refreshed if needed)
        access_token = get_valid_access_token()
        if not access_token:
            logger.error("Not authenticated - cannot analyze")
            return
        
        for symbol in self.watchlist:
            try:
                # Get historical data using Schwab API directly
                params = {
                    "symbol": symbol,
                    "periodType": "day",
                    "period": "1",
                    "frequencyType": "minute",
                    "frequency": "5",
                    "needExtendedHoursData": "false"
                }
                
                url = SCHWAB_HISTORICAL_URL
                # Token is automatically refreshed if needed by schwab_api_request
                response = schwab_api_request("GET", url, access_token, params=params)
                historical_data = response.json()
                
                if not historical_data or 'candles' not in historical_data:
                    logger.warning(f"No data for {symbol}")
                    continue
                
                # Convert to DataFrame
                import pandas as pd
                candles = historical_data['candles']
                df = pd.DataFrame(candles)
                df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                
                # Calculate indicators
                df = self.ov_engine.calculate_indicators(df)
                
                # Identify setup
                setup = self.ov_engine.identify_setup(df)
                
                if not setup:
                    logger.debug(f"No setup found for {symbol}")
                    continue
                
                # Check if 4 Fantastics are met (required for execution)
                if not setup.get('fantastics', {}).get('all_fantastics', False):
                    logger.debug(f"{symbol}: 4 Fantastics not met")
                    continue
                
                    # AI analysis
                    market_summary = self.ov_engine.get_market_summary(df)
                    ai_analyzer = self._get_ai_analyzer()
                    ai_signal = ai_analyzer.analyze_market_data(symbol, market_summary, setup)
                
                # Only execute if AI confirms and confidence > 0.7
                if ai_signal.get('action') in ['BUY', 'SELL'] and ai_signal.get('confidence', 0) > 0.7:
                    logger.info(f"Signal found for {symbol}: {ai_signal.get('action')}")
                    
                    # Execute signal
                    try:
                        result = execute_signal_helper(ai_signal, access_token)
                        if result and result.get('status') == 'success':
                            # Add to position manager
                            position = {
                                'symbol': symbol,
                                'account_id': result.get('account_id'),
                                'entry_price': ai_signal.get('entry'),
                                'stop_loss': ai_signal.get('stop'),
                                'take_profit': ai_signal.get('target'),
                                'quantity': ai_signal.get('position_size', 0),
                                'direction': 'LONG' if ai_signal.get('action') == 'BUY' else 'SHORT',
                                'atr': market_summary.get('atr_14', 0),
                                'setup_type': setup.get('type')
                            }
                            self.position_manager.add_position(position)
                            logger.info(f"Position opened: {symbol}")
                    except Exception as e:
                        logger.error(f"Failed to execute signal for {symbol}: {e}")
                
                # Small delay between symbols
                time.sleep(1)
            
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                continue
        
        logger.info("Market analysis complete")
    
    def update_positions(self):
        """
        Update all positions with current prices and manage stops.
        Runs every minute during market hours.
        """
        if not self.is_market_hours():
            return
        
        if not self.is_running:
            return
        
        logger.debug("Updating positions...")
        
        positions = self.position_manager.load_active_positions()
        if not positions:
            return
        
        # Get current prices for all symbols
        price_data = {}
        # Get valid access token (automatically refreshed if needed)
        access_token = get_valid_access_token()
        
        if not access_token:
            logger.warning("Not authenticated - cannot update positions")
            return
        
        for position in positions:
            symbol = position.get('symbol')
            try:
                # Get quote directly from Schwab API
                url = f"{SCHWAB_QUOTES_URL}?symbols={symbol}"
                response = schwab_api_request("GET", url, access_token)
                quote = response.json()
                
                # Extract price from Schwab quote format
                if isinstance(quote, dict) and symbol in quote:
                    quote_data = quote[symbol]
                    # Schwab quote format may vary - try common fields
                    if 'lastPrice' in quote_data:
                        price_data[symbol] = quote_data['lastPrice']
                    elif 'mark' in quote_data:
                        price_data[symbol] = quote_data['mark']
                    elif 'closePrice' in quote_data:
                        price_data[symbol] = quote_data['closePrice']
            except Exception as e:
                logger.error(f"Failed to get price for {symbol}: {e}")
        
        # Update positions
        if price_data:
            self.position_manager.update_all_positions(price_data)
    
    def auto_close_positions(self):
        """
        Auto-close all positions at 4:00 PM ET.
        """
        if not self.position_manager.should_auto_close():
            return
        
        logger.info("Auto-closing all positions at 4:00 PM ET...")
        closed = self.position_manager.close_all_positions()
        logger.info(f"Closed {len(closed)} positions")
    
    def start(self):
        """Start the scheduler."""
        logger.info("Starting trading scheduler...")
        self.is_running = True
        
        # Schedule tasks
        # Analyze market every 5 minutes during market hours
        schedule.every(5).minutes.do(self.analyze_and_trade).tag('market-hours')
        
        # Update positions every minute
        schedule.every(1).minutes.do(self.update_positions).tag('market-hours')
        
        # Auto-close at 4:00 PM ET
        schedule.every().day.at("16:00").do(self.auto_close_positions)
        
        logger.info("Scheduler started. Monitoring market...")
        
        # Run scheduler loop
        while self.is_running:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    
    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping trading scheduler...")
        self.is_running = False
        schedule.clear()

