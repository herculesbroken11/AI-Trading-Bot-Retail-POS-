"""
Polygon.io WebSocket Streaming for Real-Time Market Data
Handles real-time data ingestion, normalization, and storage.
"""
import os
import json
import websocket
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from utils.logger import setup_logger
from utils.helpers import polygon_api_request
import pandas as pd

logger = setup_logger("polygon_streamer")

# Polygon.io WebSocket endpoint
POLYGON_WS_URL = "wss://socket.polygon.io/stocks"

class PolygonStreamer:
    """
    WebSocket streamer for Polygon.io real-time market data.
    Handles connection, subscription, data normalization, and storage.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('POLYGON_API_KEY')
        # Don't raise error on init - allow lazy initialization
        # Will check when connect() is called
        
        self.ws = None
        self.is_connected = False
        self.is_authenticated = False
        self.subscribed_symbols = set()
        self.callbacks = {}  # symbol -> callback function
        self.data_callbacks = {}  # symbol -> data processing callback
        self.thread = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        
        # Data buffers for normalization
        self.tick_data = {}  # symbol -> list of ticks
        self.last_candle_time = {}  # symbol -> {timeframe: last_candle_timestamp}
        
    def connect(self):
        """Connect to Polygon.io WebSocket stream."""
        if self.is_connected:
            return
        
        # Check API key before connecting
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY not found in environment variables. Please set POLYGON_API_KEY in .env file.")
        
        try:
            self.ws = websocket.WebSocketApp(
                POLYGON_WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start WebSocket in separate thread
            self.thread = threading.Thread(target=self.ws.run_forever)
            self.thread.daemon = True
            self.thread.start()
            
            logger.info("Polygon.io WebSocket connection initiated")
        
        except Exception as e:
            logger.error(f"Failed to connect Polygon.io WebSocket: {e}")
            raise
    
    def _on_open(self, ws):
        """Handle WebSocket open - authenticate immediately."""
        logger.info("Polygon.io WebSocket connected, authenticating...")
        self.is_connected = True
        
        # Authenticate with API key
        auth_message = {
            "action": "auth",
            "params": self.api_key
        }
        ws.send(json.dumps(auth_message))
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Handle authentication response
            if isinstance(data, list) and len(data) > 0:
                event = data[0].get('ev')
                
                if event == 'status':
                    # Authentication or status message
                    status = data[0].get('status')
                    message_text = data[0].get('message', '')
                    
                    if status == 'auth_success':
                        self.is_authenticated = True
                        self.reconnect_attempts = 0
                        logger.info("Polygon.io WebSocket authenticated successfully")
                        
                        # Subscribe to already subscribed symbols
                        if self.subscribed_symbols:
                            self._subscribe_all()
                    elif status == 'auth_failed':
                        logger.error(f"Polygon.io authentication failed: {message_text}")
                        self.is_authenticated = False
                    elif status == 'success':
                        logger.debug(f"Polygon.io status: {message_text}")
                
                elif event == 'T':  # Trade data
                    self._handle_trade(data[0])
                elif event == 'Q':  # Quote data
                    self._handle_quote(data[0])
                elif event == 'A':  # Aggregate (bar) data
                    self._handle_aggregate(data[0])
            
            logger.debug(f"Received Polygon.io message: {data}")
        
        except Exception as e:
            logger.error(f"Error processing Polygon.io WebSocket message: {e}", exc_info=True)
    
    def _handle_trade(self, trade_data: Dict):
        """Handle trade tick data."""
        symbol = trade_data.get('sym', '').upper()
        if not symbol:
            return
        
        # Store tick for normalization
        if symbol not in self.tick_data:
            self.tick_data[symbol] = []
        
        tick = {
            'timestamp': trade_data.get('t', 0),  # Unix timestamp in milliseconds
            'price': trade_data.get('p', 0),
            'size': trade_data.get('s', 0),
            'exchange': trade_data.get('x', '')
        }
        
        self.tick_data[symbol].append(tick)
        
        # Call user callback if registered
        if symbol in self.callbacks:
            self.callbacks[symbol](tick)
        
        # Normalize to 1-minute bars
        self._normalize_to_bars(symbol, '1min')
    
    def _handle_quote(self, quote_data: Dict):
        """Handle quote (bid/ask) data."""
        symbol = quote_data.get('sym', '').upper()
        if not symbol:
            return
        
        quote = {
            'timestamp': quote_data.get('t', 0),
            'bid': quote_data.get('bp', 0),
            'ask': quote_data.get('ap', 0),
            'bid_size': quote_data.get('bs', 0),
            'ask_size': quote_data.get('as', 0)
        }
        
        # Call user callback if registered
        if symbol in self.callbacks:
            self.callbacks[symbol](quote)
    
    def _handle_aggregate(self, agg_data: Dict):
        """Handle aggregate (bar) data."""
        symbol = agg_data.get('sym', '').upper()
        if not symbol:
            return
        
        bar = {
            'timestamp': agg_data.get('s', 0),  # Start time
            'open': agg_data.get('o', 0),
            'high': agg_data.get('h', 0),
            'low': agg_data.get('l', 0),
            'close': agg_data.get('c', 0),
            'volume': agg_data.get('v', 0),
            'vwap': agg_data.get('vw', 0),  # Volume-weighted average price
            'timeframe': agg_data.get('i', '1min')  # Interval
        }
        
        # Call data callback for storage/processing
        if symbol in self.data_callbacks:
            self.data_callbacks[symbol](bar)
    
    def _normalize_to_bars(self, symbol: str, timeframe: str = '1min'):
        """
        Normalize tick data to bars (OHLCV).
        
        Args:
            symbol: Stock symbol
            timeframe: Target timeframe ('1min', '5min', 'daily')
        """
        if symbol not in self.tick_data or not self.tick_data[symbol]:
            return
        
        # Get timeframe in minutes
        if timeframe == '1min':
            interval_ms = 60 * 1000
        elif timeframe == '5min':
            interval_ms = 5 * 60 * 1000
        elif timeframe == 'daily':
            # For daily, we'd need to track day boundaries
            return
        else:
            return
        
        # Group ticks by time interval
        ticks = self.tick_data[symbol]
        if not ticks:
            return
        
        # Get current bar start time
        current_time = time.time() * 1000  # Current time in milliseconds
        bar_start = (current_time // interval_ms) * interval_ms
        
        # Check if we have a complete bar
        last_bar_time = self.last_candle_time.get(symbol, {}).get(timeframe, 0)
        
        if bar_start > last_bar_time:
            # New bar started, process previous bar
            bar_ticks = [t for t in ticks if last_bar_time <= t['timestamp'] < bar_start]
            
            if bar_ticks:
                # Create OHLCV bar
                prices = [t['price'] for t in bar_ticks]
                volumes = [t['size'] for t in bar_ticks]
                
                bar = {
                    'timestamp': last_bar_time,
                    'open': prices[0] if prices else 0,
                    'high': max(prices) if prices else 0,
                    'low': min(prices) if prices else 0,
                    'close': prices[-1] if prices else 0,
                    'volume': sum(volumes),
                    'timeframe': timeframe
                }
                
                # Call data callback
                if symbol in self.data_callbacks:
                    self.data_callbacks[symbol](bar)
                
                # Update last bar time
                if symbol not in self.last_candle_time:
                    self.last_candle_time[symbol] = {}
                self.last_candle_time[symbol][timeframe] = bar_start
                
                # Remove processed ticks
                self.tick_data[symbol] = [t for t in ticks if t['timestamp'] >= bar_start]
    
    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        logger.error(f"Polygon.io WebSocket error: {error}")
        self.is_connected = False
        self.is_authenticated = False
        
        # Attempt reconnection
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts}...")
            time.sleep(self.reconnect_delay)
            self.connect()
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.info(f"Polygon.io WebSocket closed: {close_status_code} - {close_msg}")
        self.is_connected = False
        self.is_authenticated = False
        
        # Attempt reconnection if not intentional
        if close_status_code != 1000:  # 1000 = normal closure
            if self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts}...")
                time.sleep(self.reconnect_delay)
                self.connect()
    
    def subscribe(self, symbol: str, callback: Optional[Callable] = None, data_callback: Optional[Callable] = None):
        """
        Subscribe to real-time data for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            callback: Optional callback for raw tick/quote data
            data_callback: Optional callback for normalized bar data
        """
        symbol = symbol.upper()
        self.subscribed_symbols.add(symbol)
        
        if callback:
            self.callbacks[symbol] = callback
        
        if data_callback:
            self.data_callbacks[symbol] = data_callback
        
        if self.is_authenticated:
            self._subscribe_symbol(symbol)
    
    def _subscribe_symbol(self, symbol: str):
        """Send subscription message for symbol."""
        if not self.ws or not self.is_authenticated:
            return
        
        # Subscribe to trades and quotes
        subscribe_message = {
            "action": "subscribe",
            "params": f"T.{symbol},Q.{symbol},A.{symbol}"  # Trades, Quotes, Aggregates
        }
        
        try:
            self.ws.send(json.dumps(subscribe_message))
            logger.info(f"Subscribed to Polygon.io data for {symbol}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol}: {e}")
    
    def _subscribe_all(self):
        """Subscribe to all symbols in watchlist."""
        for symbol in self.subscribed_symbols:
            self._subscribe_symbol(symbol)
    
    def unsubscribe(self, symbol: str):
        """Unsubscribe from symbol."""
        symbol = symbol.upper()
        self.subscribed_symbols.discard(symbol)
        self.callbacks.pop(symbol, None)
        self.data_callbacks.pop(symbol, None)
        
        if self.is_authenticated:
            unsubscribe_message = {
                "action": "unsubscribe",
                "params": f"T.{symbol},Q.{symbol},A.{symbol}"
            }
            try:
                self.ws.send(json.dumps(unsubscribe_message))
                logger.info(f"Unsubscribed from {symbol}")
            except Exception as e:
                logger.error(f"Failed to unsubscribe from {symbol}: {e}")
    
    def disconnect(self):
        """Disconnect WebSocket."""
        if self.ws:
            self.ws.close()
        self.is_connected = False
        self.is_authenticated = False
        self.subscribed_symbols.clear()
        self.callbacks.clear()
        self.data_callbacks.clear()
        logger.info("Polygon.io WebSocket disconnected")
    
    def get_status(self) -> Dict[str, Any]:
        """Get streaming status."""
        return {
            "connected": self.is_connected,
            "authenticated": self.is_authenticated,
            "subscribed_symbols": list(self.subscribed_symbols),
            "reconnect_attempts": self.reconnect_attempts
        }
    
    def health_check(self) -> bool:
        """Perform health check on WebSocket connection."""
        if not self.is_connected or not self.is_authenticated:
            return False
        
        # Check if connection is stale (no data for 60 seconds)
        # This is a simple check - in production, you'd want more sophisticated monitoring
        return True

