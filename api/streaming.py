"""
WebSocket Streaming for Real-Time Market Data
"""
import os
import json
import websocket
import threading
from flask import Blueprint, request, jsonify
from typing import Dict, Any, Optional, Callable
from utils.logger import setup_logger
from utils.helpers import load_tokens

streaming_bp = Blueprint('streaming', __name__, url_prefix='/streaming')
logger = setup_logger("streaming")

# Schwab WebSocket endpoint (if available)
# Note: Schwab may use different streaming API - check documentation
SCHWAB_WS_URL = os.getenv("SCHWAB_WS_URL", "wss://api.schwabapi.com/streaming/v1")

class QuoteStreamer:
    """
    WebSocket streamer for real-time quotes.
    """
    
    def __init__(self):
        self.ws = None
        self.is_connected = False
        self.subscribed_symbols = set()
        self.callbacks = {}  # symbol -> callback function
        self.thread = None
        
    def connect(self, access_token: str):
        """Connect to WebSocket stream."""
        if self.is_connected:
            return
        
        try:
            # Create WebSocket connection with authentication
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            self.ws = websocket.WebSocketApp(
                SCHWAB_WS_URL,
                header=headers,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start WebSocket in separate thread
            self.thread = threading.Thread(target=self.ws.run_forever)
            self.thread.daemon = True
            self.thread.start()
            
            logger.info("WebSocket connection initiated")
        
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
    
    def _on_open(self, ws):
        """Handle WebSocket open."""
        self.is_connected = True
        logger.info("WebSocket connected")
        
        # Subscribe to already subscribed symbols
        if self.subscribed_symbols:
            self._subscribe_all()
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Process quote data
            if 'symbol' in data and 'price' in data:
                symbol = data['symbol']
                if symbol in self.callbacks:
                    self.callbacks[symbol](data)
            
            logger.debug(f"Received quote: {data}")
        
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")
        self.is_connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.info("WebSocket closed")
        self.is_connected = False
    
    def subscribe(self, symbol: str, callback: Optional[Callable] = None):
        """
        Subscribe to real-time quotes for a symbol.
        
        Args:
            symbol: Stock symbol
            callback: Optional callback function for quote updates
        """
        self.subscribed_symbols.add(symbol)
        
        if callback:
            self.callbacks[symbol] = callback
        
        if self.is_connected:
            self._subscribe_symbol(symbol)
    
    def unsubscribe(self, symbol: str):
        """Unsubscribe from symbol."""
        self.subscribed_symbols.discard(symbol)
        self.callbacks.pop(symbol, None)
        
        if self.is_connected:
            self._unsubscribe_symbol(symbol)
    
    def _subscribe_symbol(self, symbol: str):
        """Send subscription message for symbol."""
        if not self.ws:
            return
        
        message = {
            "action": "subscribe",
            "symbols": [symbol]
        }
        
        try:
            self.ws.send(json.dumps(message))
            logger.info(f"Subscribed to {symbol}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol}: {e}")
    
    def _subscribe_all(self):
        """Subscribe to all symbols in watchlist."""
        for symbol in self.subscribed_symbols:
            self._subscribe_symbol(symbol)
    
    def _unsubscribe_symbol(self, symbol: str):
        """Send unsubscribe message for symbol."""
        if not self.ws:
            return
        
        message = {
            "action": "unsubscribe",
            "symbols": [symbol]
        }
        
        try:
            self.ws.send(json.dumps(message))
            logger.info(f"Unsubscribed from {symbol}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {symbol}: {e}")
    
    def disconnect(self):
        """Disconnect WebSocket."""
        if self.ws:
            self.ws.close()
        self.is_connected = False
        self.subscribed_symbols.clear()
        self.callbacks.clear()

# Global streamer instance
streamer = QuoteStreamer()

@streaming_bp.route('/connect', methods=['POST'])
def connect_stream():
    """Connect to WebSocket stream."""
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        streamer.connect(tokens['access_token'])
        return jsonify({"status": "connected"}), 200
    except Exception as e:
        logger.error(f"Failed to connect stream: {e}")
        return jsonify({"error": str(e)}), 500

@streaming_bp.route('/subscribe/<symbol>', methods=['POST'])
def subscribe_symbol(symbol: str):
    """Subscribe to real-time quotes for a symbol."""
    try:
        streamer.subscribe(symbol.upper())
        return jsonify({"status": "subscribed", "symbol": symbol}), 200
    except Exception as e:
        logger.error(f"Failed to subscribe: {e}")
        return jsonify({"error": str(e)}), 500

@streaming_bp.route('/unsubscribe/<symbol>', methods=['POST'])
def unsubscribe_symbol(symbol: str):
    """Unsubscribe from symbol."""
    try:
        streamer.unsubscribe(symbol.upper())
        return jsonify({"status": "unsubscribed", "symbol": symbol}), 200
    except Exception as e:
        logger.error(f"Failed to unsubscribe: {e}")
        return jsonify({"error": str(e)}), 500

@streaming_bp.route('/disconnect', methods=['POST'])
def disconnect_stream():
    """Disconnect WebSocket stream."""
    try:
        streamer.disconnect()
        return jsonify({"status": "disconnected"}), 200
    except Exception as e:
        logger.error(f"Failed to disconnect: {e}")
        return jsonify({"error": str(e)}), 500

@streaming_bp.route('/status', methods=['GET'])
def stream_status():
    """Get streaming status."""
    return jsonify({
        "connected": streamer.is_connected,
        "subscribed_symbols": list(streamer.subscribed_symbols)
    }), 200

