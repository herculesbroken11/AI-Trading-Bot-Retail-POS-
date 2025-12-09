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
from core.performance_analyzer import PerformanceAnalyzer
from ai.analyze import TradingAIAnalyzer
from api.orders import execute_signal_helper
from utils.helpers import get_valid_access_token, schwab_api_request
from api.quotes import SCHWAB_HISTORICAL_URL, SCHWAB_QUOTES_URL
from api.activity import add_activity_log

logger = setup_logger("scheduler")

class TradingScheduler:
    """
    Automated scheduler for continuous market analysis and trade execution.
    """
    
    def __init__(self):
        # Initialize performance analyzer for optimization
        self.performance_analyzer = PerformanceAnalyzer()
        
        # Initialize engines with performance analyzer
        self.ov_engine = OVStrategyEngine(performance_analyzer=self.performance_analyzer)
        self.position_manager = PositionManager(performance_analyzer=self.performance_analyzer)
        
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
        add_activity_log('info', f'Starting market analysis for {len(self.watchlist)} symbols', None, None)
        
        # Get valid access token (automatically refreshed if needed)
        access_token = get_valid_access_token()
        if not access_token:
            logger.error("Not authenticated - cannot analyze")
            add_activity_log('error', 'Not authenticated - cannot analyze market', None, None)
            return
        
        for symbol in self.watchlist:
            try:
                add_activity_log('info', f'Analyzing {symbol}...', None, symbol)
                
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
                    add_activity_log('warning', f'{symbol}: No market data available', None, symbol)
                    continue
                
                candles = historical_data['candles']
                if not candles or len(candles) == 0:
                    logger.warning(f"Empty candles array for {symbol}")
                    continue
                
                # Convert to DataFrame - handle both dict and array formats
                import pandas as pd
                if isinstance(candles[0], dict):
                    # Dictionary format - use directly
                    df = pd.DataFrame(candles)
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                    elif 'time' in df.columns:
                        df['datetime'] = pd.to_datetime(df['time'], unit='ms')
                        df = df.rename(columns={'time': 'datetime'})
                else:
                    # Array format - need to detect column order (same logic as quotes.py)
                    df = pd.DataFrame(candles)
                    if len(df.columns) == 6:
                        # Auto-detect column order
                        raw_values = [float(df.iloc[0, i]) for i in range(6)]
                        datetime_idx = raw_values.index(max(raw_values))
                        non_datetime = [(i, v) for i, v in enumerate(raw_values) if i != datetime_idx]
                        volume_candidates = [(i, v) for i, v in non_datetime if 1e6 <= v < 1e10]
                        volume_idx = volume_candidates[0][0] if volume_candidates else non_datetime[-1][0]
                        price_indices = [i for i in range(6) if i not in [datetime_idx, volume_idx]]
                        price_vals = [(i, raw_values[i]) for i in price_indices]
                        price_vals.sort(key=lambda x: x[1])
                        low_idx = price_vals[0][0]
                        high_idx = price_vals[-1][0]
                        open_idx = price_vals[1][0] if len(price_vals) > 1 else price_indices[0]
                        close_idx = price_vals[2][0] if len(price_vals) > 2 else price_indices[1]
                        col_map = [''] * 6
                        col_map[datetime_idx] = 'datetime'
                        col_map[open_idx] = 'open'
                        col_map[high_idx] = 'high'
                        col_map[low_idx] = 'low'
                        col_map[close_idx] = 'close'
                        col_map[volume_idx] = 'volume'
                        df.columns = col_map
                        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                    else:
                        logger.warning(f"Unexpected candle format for {symbol}: {len(df.columns)} columns")
                        continue
                
                # Ensure numeric types
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Check if we have enough data before calculating indicators
                if len(df) < 200:
                    logger.warning(f"Insufficient data for {symbol}: only {len(df)} candles (need 200+)")
                    add_activity_log('warning', f'{symbol}: Insufficient data ({len(df)} candles, need 200+)', None, symbol)
                    continue
                
                # Calculate indicators
                df = self.ov_engine.calculate_indicators(df)
                add_activity_log('info', f'{symbol}: Indicators calculated (SMA8/20/200, ATR14, RSI)', None, symbol)
                
                # Check if indicators were calculated (they might not be if data is still insufficient)
                if 'sma_8' not in df.columns or 'sma_20' not in df.columns or 'sma_200' not in df.columns:
                    logger.warning(f"Indicators not calculated for {symbol} - insufficient data")
                    continue
                
                # Identify setup
                setup = self.ov_engine.identify_setup(df)
                
                if not setup:
                    logger.debug(f"No setup found for {symbol}")
                    add_activity_log('info', f'{symbol}: No OV setup detected (checking next symbol)', None, symbol)
                    continue
                
                # Log setup detection
                setup_type = setup.get('type', 'UNKNOWN')
                add_activity_log('rule', f'Setup detected: {setup_type} for {symbol}', setup_type, symbol)
                
                # Check if 4 Fantastics are met (required for execution)
                fantastics = setup.get('fantastics', {})
                if not fantastics.get('all_fantastics', False):
                    logger.debug(f"{symbol}: 4 Fantastics not met")
                    # Log which fantastics are missing
                    missing = []
                    if not fantastics.get('price_above_sma200', False):
                        missing.append('Price above SMA200')
                    if not fantastics.get('sma_aligned', False):
                        missing.append('SMA alignment')
                    if not fantastics.get('volume_above_average', False):
                        missing.append('Volume above average')
                    if not fantastics.get('rsi_in_range', False):
                        missing.append('RSI in range')
                    missing_str = ', '.join(missing) if missing else 'Unknown'
                    add_activity_log('warning', f'{symbol}: 4 Fantastics not met - Missing: {missing_str}', '4 Fantastics', symbol)
                    continue
                
                add_activity_log('success', f'{symbol}: ✓ 4 Fantastics confirmed!', '4 Fantastics', symbol)
                
                # Generate chart image for AI vision analysis
                chart_image = None
                try:
                    from utils.chart_generator import generate_trading_chart
                    market_summary = self.ov_engine.get_market_summary(df)
                    chart_image = generate_trading_chart(df, symbol, setup, market_summary)
                    if chart_image:
                        add_activity_log('info', f'{symbol}: 📊 Chart generated for AI vision analysis', None, symbol)
                    else:
                        add_activity_log('warning', f'{symbol}: Failed to generate chart, using text-only analysis', None, symbol)
                except Exception as e:
                    logger.warning(f"Failed to generate chart for {symbol}: {e}")
                    add_activity_log('warning', f'{symbol}: Chart generation failed, using text-only analysis', None, symbol)
                
                # AI analysis with chart image (if available)
                if not market_summary:
                    market_summary = self.ov_engine.get_market_summary(df)
                ai_analyzer = self._get_ai_analyzer()
                ai_signal = ai_analyzer.analyze_market_data(symbol, market_summary, setup, chart_image)
                
                # Store chart in cache for dashboard display
                if chart_image:
                    try:
                        from api.activity import add_chart_to_cache
                        add_chart_to_cache(symbol, chart_image, setup, ai_signal)
                    except Exception as e:
                        logger.warning(f"Failed to cache chart for {symbol}: {e}")
                
                # Log AI analysis
                confidence = ai_signal.get('confidence', 0)
                action = ai_signal.get('action', 'HOLD')
                analysis_type = "with chart vision" if chart_image else "text-only"
                add_activity_log('info', f'AI analysis for {symbol} ({analysis_type}): {action} (confidence: {confidence:.1%})', None, symbol)
                
                # Only execute if AI confirms and confidence > 0.7
                if ai_signal.get('action') in ['BUY', 'SELL'] and ai_signal.get('confidence', 0) > 0.7:
                    add_activity_log('success', f'{symbol}: AI confirmed {action} signal with {confidence:.1%} confidence - Proceeding to execute', None, symbol)
                else:
                    reason = 'HOLD signal' if action == 'HOLD' else f'Low confidence ({confidence:.1%} < 70%)'
                    add_activity_log('warning', f'{symbol}: Trade not executed - {reason}', None, symbol)
                
                if ai_signal.get('action') in ['BUY', 'SELL'] and ai_signal.get('confidence', 0) > 0.7:
                    logger.info(f"Signal found for {symbol}: {ai_signal.get('action')}")
                    
                    # Execute signal
                    try:
                        # Check account balance before attempting trade
                        try:
                            from api.orders import SCHWAB_ACCOUNTS_URL, get_validated_account_hash
                            accounts_response = schwab_api_request("GET", SCHWAB_ACCOUNTS_URL, access_token)
                            accounts = accounts_response.json()
                            if accounts and len(accounts) > 0:
                                account_id = accounts[0].get("accountNumber", "")
                                account_hash, _ = get_validated_account_hash(account_id, access_token)
                                account_url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}"
                                account_response = schwab_api_request("GET", account_url, access_token)
                                account_data = account_response.json()
                                
                                if account_data:
                                    balances = account_data.get('currentBalances', {})
                                    available_funds = float(balances.get('availableFunds', 0) or 0)
                                    buying_power = float(balances.get('buyingPower', 0) or 0)
                                    account_value = float(balances.get('liquidationValue', balances.get('totalEquity', 0)) or 0)
                                    
                                    add_activity_log('info', f'Account balance: ${account_value:.2f}, Buying power: ${buying_power:.2f}', None, None)
                                    
                                    # Estimate order cost
                                    entry_price = float(ai_signal.get('entry', 0))
                                    position_size = ai_signal.get('position_size', 1)
                                    estimated_cost = entry_price * position_size
                                    
                                    if available_funds > 0 and estimated_cost > available_funds:
                                        add_activity_log('warning', 
                                            f'Insufficient funds for {symbol}: Need ${estimated_cost:.2f}, have ${available_funds:.2f}',
                                            None, symbol)
                                        continue
                        except Exception as e:
                            logger.warning(f"Could not check account balance: {e}")
                        
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
                            
                            # Log trade execution
                            add_activity_log('success', 
                                f'Trade executed: {ai_signal.get("action")} {symbol} @ ${ai_signal.get("entry", 0):.2f} (Setup: {setup.get("type")})',
                                setup.get('type'),
                                symbol)
                        else:
                            add_activity_log('warning', f'Trade execution failed for {symbol}: {result.get("error", "Unknown error")}', None, symbol)
                    except Exception as e:
                        logger.error(f"Failed to execute signal for {symbol}: {e}")
                        add_activity_log('error', f'Error executing trade for {symbol}: {str(e)}', None, symbol)
                
                # Small delay between symbols
                time.sleep(1)
            
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                continue
        
        logger.info("Market analysis complete")
        add_activity_log('info', f'Market analysis complete - Analyzed {len(self.watchlist)} symbols', None, None)
    
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
        # Pass performance analyzer to record outcomes
        self.position_manager.performance_analyzer = self.performance_analyzer
        closed = self.position_manager.close_all_positions()
        logger.info(f"Closed {len(closed)} positions")
        
        # Record outcomes for all closed positions
        for position in closed:
            try:
                # Get current price for P&L calculation
                symbol = position.get('symbol')
                access_token = get_valid_access_token()
                if access_token:
                    url = f"{SCHWAB_QUOTES_URL}?symbols={symbol}"
                    response = schwab_api_request("GET", url, access_token)
                    quote = response.json()
                    
                    if isinstance(quote, dict) and symbol in quote:
                        quote_data = quote[symbol]
                        exit_price = quote_data.get('lastPrice') or quote_data.get('mark', 0)
                        
                        entry_price = position.get('entry_price') or position.get('average_entry', 0)
                        quantity = position.get('quantity', 0)
                        direction = position.get('direction', 'LONG')
                        
                        if direction == 'LONG':
                            pnl = (exit_price - entry_price) * quantity
                        else:
                            pnl = (entry_price - exit_price) * quantity
                        
                        self.record_trade_outcome(position, exit_price, pnl, "CLOSED")
            except Exception as e:
                logger.error(f"Failed to record outcome for {position.get('symbol')}: {e}")
    
    def start(self):
        """Start the scheduler."""
        logger.info("Starting trading scheduler...")
        self.is_running = True
        add_activity_log('success', 'Automated trading scheduler started', None, None)
        
        # Schedule tasks
        # Analyze market every 5 minutes during market hours
        schedule.every(5).minutes.do(self.analyze_and_trade).tag('market-hours')
        
        # Update positions every minute
        schedule.every(1).minutes.do(self.update_positions).tag('market-hours')
        
        # Auto-close at 4:00 PM ET
        schedule.every().day.at("16:00").do(self.auto_close_positions)
        
        # Phase 7: Optimization tasks
        # Run performance analysis daily at end of trading day
        schedule.every().day.at("16:30").do(self.run_daily_optimization)
        
        # Auto-tune parameters weekly (Sunday evening)
        schedule.every().sunday.at("20:00").do(self.run_parameter_optimization)
        
        logger.info("Scheduler started. Monitoring market...")
        
        # Run scheduler loop
        while self.is_running:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    
    def run_daily_optimization(self):
        """
        Phase 7: Run daily performance analysis and adjust setup weights.
        Runs at 4:30 PM ET (after market close).
        """
        logger.info("Running daily optimization...")
        try:
            # Analyze performance over last 30 days
            analysis = self.performance_analyzer.analyze_performance(days=30)
            
            # Adjust setup weights based on performance
            new_weights = self.performance_analyzer.adjust_setup_weights(min_trades=5)
            
            logger.info(f"Daily optimization complete. Setup weights: {new_weights}")
            logger.info(f"Performance: {analysis.get('win_rate', 0):.1f}% win rate, ${analysis.get('total_pnl', 0):.2f} P&L")
            
        except Exception as e:
            logger.error(f"Failed to run daily optimization: {e}", exc_info=True)
    
    def run_parameter_optimization(self):
        """
        Phase 7: Auto-tune parameters based on volatility.
        Runs weekly on Sunday evening.
        """
        logger.info("Running parameter optimization...")
        try:
            # Get recent price data for volatility calculation
            access_token = get_valid_access_token()
            if not access_token:
                logger.warning("Not authenticated - skipping parameter optimization")
                return
            
            # Get prices for watchlist symbols
            recent_prices = []
            for symbol in self.watchlist[:5]:  # Use first 5 symbols
                try:
                    url = f"{SCHWAB_HISTORICAL_URL}?symbol={symbol}&periodType=day&period=1&frequencyType=minute&frequency=5"
                    response = schwab_api_request("GET", url, access_token)
                    data = response.json()
                    
                    # Extract close prices
                    if isinstance(data, dict) and 'candles' in data:
                        prices = [c.get('close', 0) for c in data['candles'] if c.get('close')]
                        recent_prices.extend(prices)
                except Exception as e:
                    logger.debug(f"Failed to get prices for {symbol}: {e}")
                    continue
            
            if recent_prices:
                # Get recent trades for performance-based adjustment
                recent_trades = self.performance_analyzer.performance_data.get("trades", [])[-50:]
                
                # Auto-tune parameters
                optimized = self.performance_analyzer.auto_tune_parameters(
                    recent_prices=recent_prices,
                    recent_trades=recent_trades
                )
                
                logger.info(f"Parameter optimization complete: {optimized}")
            else:
                logger.warning("No price data available for parameter optimization")
                
        except Exception as e:
            logger.error(f"Failed to run parameter optimization: {e}", exc_info=True)
    
    def record_trade_outcome(self, position: Dict[str, Any], exit_price: float, pnl: float, status: str = "CLOSED"):
        """
        Phase 7: Record trade outcome for performance analysis.
        
        Args:
            position: Position dictionary
            exit_price: Exit price
            pnl: Profit/loss in dollars
            status: Trade status (CLOSED, OPEN, etc.)
        """
        try:
            trade_data = {
                "symbol": position.get("symbol"),
                "setup_type": position.get("setup_type", "unknown"),
                "entry_price": position.get("entry_price") or position.get("average_entry"),
                "exit_price": exit_price,
                "quantity": position.get("quantity", 0),
                "direction": position.get("direction", "LONG"),
                "pnl": pnl,
                "status": status,
                "entry_time": position.get("entry_time"),
                "exit_time": datetime.now(timezone.utc).isoformat()
            }
            
            self.performance_analyzer.record_trade_outcome(trade_data)
            
        except Exception as e:
            logger.error(f"Failed to record trade outcome: {e}", exc_info=True)
    
    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping trading scheduler...")
        self.is_running = False
        schedule.clear()
        add_activity_log('info', 'Automated trading scheduler stopped', None, None)

