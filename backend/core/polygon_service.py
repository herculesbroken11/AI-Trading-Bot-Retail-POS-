"""
Polygon.io Market Data Service
Orchestrates WebSocket connection, data processing, chart generation, and monitoring.
"""
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from utils.logger import setup_logger
from core.polygon_streamer import PolygonStreamer
from core.data_normalizer import process_and_store_bar
from core.chart_renderer import generate_chart_on_candle_complete
from utils.market_data_db import init_market_data_db, detect_data_gaps
from utils.helpers import polygon_api_request

logger = setup_logger("polygon_service")

class PolygonMarketDataService:
    """
    Main service for Polygon.io market data integration.
    Handles real-time streaming, data storage, chart generation, and monitoring.
    """
    
    def __init__(self, watchlist: Optional[List[str]] = None):
        """
        Initialize Polygon.io market data service.
        
        Args:
            watchlist: List of symbols to monitor (default: from env)
        """
        self.watchlist = watchlist or self._load_watchlist()
        self.streamer = PolygonStreamer()
        self.is_running = False
        self.monitoring_thread = None
        self.last_data_timestamp = {}  # symbol -> timestamp
        self.chart_generation_enabled = True
        
        # Initialize database
        init_market_data_db()
        
        logger.info(f"Polygon.io service initialized with watchlist: {self.watchlist}")
    
    def _load_watchlist(self) -> List[str]:
        """Load watchlist from environment variable."""
        watchlist_str = os.getenv('POLYGON_WATCHLIST', 'AMD,INTC,CSCO,BAC,PFE,KO,T,JNJ,NKE,ABT')
        return [s.strip().upper() for s in watchlist_str.split(',') if s.strip()]
    
    def start(self):
        """Start the market data service."""
        if self.is_running:
            logger.warning("Service is already running")
            return
        
        try:
            # Connect WebSocket
            self.streamer.connect()
            
            # Wait for authentication
            max_wait = 10  # seconds
            wait_time = 0
            while not self.streamer.is_authenticated and wait_time < max_wait:
                time.sleep(0.5)
                wait_time += 0.5
            
            if not self.streamer.is_authenticated:
                raise Exception("Failed to authenticate with Polygon.io WebSocket")
            
            # Subscribe to all symbols in watchlist
            for symbol in self.watchlist:
                self.streamer.subscribe(
                    symbol=symbol,
                    data_callback=self._on_bar_data
                )
                time.sleep(0.1)  # Small delay between subscriptions
            
            self.is_running = True
            
            # Start monitoring thread
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            logger.info("Polygon.io market data service started")
        
        except Exception as e:
            logger.error(f"Failed to start Polygon.io service: {e}", exc_info=True)
            raise
    
    def stop(self):
        """Stop the market data service."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.streamer.disconnect()
        
        logger.info("Polygon.io market data service stopped")
    
    def _on_bar_data(self, bar_data: Dict):
        """
        Callback for when new bar data is received.
        
        Args:
            bar_data: Dictionary with OHLCV data
        """
        try:
            symbol = bar_data.get('sym', '').upper()
            if not symbol:
                return
            
            timeframe = bar_data.get('timeframe', '1min')
            timestamp = bar_data.get('timestamp', 0)
            
            # Update last data timestamp
            self.last_data_timestamp[symbol] = timestamp
            
            # Process and store bar
            process_and_store_bar(
                symbol=symbol,
                bar_data=bar_data,
                source_timeframe=timeframe
            )
            
            # Generate chart if enabled
            if self.chart_generation_enabled:
                try:
                    generate_chart_on_candle_complete(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=timestamp
                    )
                except Exception as e:
                    logger.error(f"Failed to generate chart for {symbol}: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error processing bar data: {e}", exc_info=True)
    
    def _monitoring_loop(self):
        """Background monitoring loop for health checks and gap detection."""
        while self.is_running:
            try:
                # Health check
                if not self.streamer.health_check():
                    logger.warning("WebSocket health check failed")
                
                # Check for stale data (no data for 5 minutes)
                current_time = int(time.time() * 1000)
                for symbol in self.watchlist:
                    last_timestamp = self.last_data_timestamp.get(symbol, 0)
                    if last_timestamp > 0:
                        time_since_last = current_time - last_timestamp
                        if time_since_last > 5 * 60 * 1000:  # 5 minutes
                            logger.warning(f"No data received for {symbol} in {time_since_last/1000:.0f} seconds")
                
                # Detect data gaps (check every 10 minutes)
                if int(time.time()) % 600 == 0:  # Every 10 minutes
                    self._check_data_gaps()
                
                time.sleep(30)  # Check every 30 seconds
            
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(60)  # Wait longer on error
    
    def _check_data_gaps(self):
        """Check for data gaps and log them."""
        try:
            end_time = int(time.time() * 1000)
            start_time = end_time - (60 * 60 * 1000)  # Last hour
            
            for symbol in self.watchlist:
                gaps = detect_data_gaps(
                    symbol=symbol,
                    timeframe='1min',
                    start_timestamp=start_time,
                    end_timestamp=end_time
                )
                
                if gaps:
                    logger.warning(f"Detected {len(gaps)} data gaps for {symbol}")
                    # In production, you might want to trigger REST API backfill here
        
        except Exception as e:
            logger.error(f"Error checking data gaps: {e}", exc_info=True)
    
    def backfill_historical_data(self, symbol: str, days: int = 10):
        """
        Backfill historical data using REST API.
        
        Args:
            symbol: Stock symbol
            days: Number of days to backfill
        """
        try:
            logger.info(f"Backfilling historical data for {symbol} ({days} days)")
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Fetch 1-minute data
            data = polygon_api_request(
                symbol=symbol,
                multiplier=1,
                timespan='minute',
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=end_date.strftime('%Y-%m-%d')
            )
            
            if data and 'candles' in data:
                from core.data_normalizer import normalize_to_timeframe
                import pandas as pd
                
                # Convert to DataFrame
                df = pd.DataFrame(data['candles'])
                if 'datetime' in df.columns:
                    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                    df.set_index('datetime', inplace=True)
                
                # Process each bar
                for idx, row in df.iterrows():
                    bar_data = {
                        'timestamp': int(idx.timestamp() * 1000),
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'volume': row['volume']
                    }
                    process_and_store_bar(symbol, bar_data, '1min')
                
                logger.info(f"Backfilled {len(data['candles'])} bars for {symbol}")
        
        except Exception as e:
            logger.error(f"Failed to backfill data for {symbol}: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "running": self.is_running,
            "watchlist": self.watchlist,
            "streamer_status": self.streamer.get_status(),
            "last_data_timestamps": {
                symbol: timestamp
                for symbol, timestamp in self.last_data_timestamp.items()
            },
            "chart_generation_enabled": self.chart_generation_enabled
        }

# Global service instance
_service_instance: Optional[PolygonMarketDataService] = None

def get_polygon_service() -> PolygonMarketDataService:
    """Get or create global Polygon.io service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PolygonMarketDataService()
    return _service_instance

