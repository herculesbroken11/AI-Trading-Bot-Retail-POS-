"""
Schwab Streamer API - Complete Real-Time Market Data Implementation
Implements all Schwab Streamer API services as documented in Schwab Developer Portal.
"""
import os
import json
import uuid
import websocket
import threading
import time
from flask import Blueprint, request, jsonify
from typing import Dict, Any, Optional, Callable, List
from utils.logger import setup_logger
from utils.helpers import load_tokens, schwab_api_request, get_valid_access_token
from api.orders import SCHWAB_USER_PREF_URL

streaming_bp = Blueprint('streaming', __name__, url_prefix='/streaming')
logger = setup_logger("streaming")

# Service constants
SERVICE_LEVELONE_EQUITIES = "LEVELONE_EQUITIES"
SERVICE_LEVELONE_OPTIONS = "LEVELONE_OPTIONS"
SERVICE_LEVELONE_FUTURES = "LEVELONE_FUTURES"
SERVICE_LEVELONE_FUTURES_OPTIONS = "LEVELONE_FUTURES_OPTIONS"
SERVICE_LEVELONE_FOREX = "LEVELONE_FOREX"
SERVICE_NYSE_BOOK = "NYSE_BOOK"
SERVICE_NASDAQ_BOOK = "NASDAQ_BOOK"
SERVICE_OPTIONS_BOOK = "OPTIONS_BOOK"
SERVICE_CHART_EQUITY = "CHART_EQUITY"
SERVICE_CHART_FUTURES = "CHART_FUTURES"
SERVICE_SCREENER_EQUITY = "SCREENER_EQUITY"
SERVICE_SCREENER_OPTION = "SCREENER_OPTION"
SERVICE_ACCT_ACTIVITY = "ACCT_ACTIVITY"

class SchwabStreamer:
    """Comprehensive Schwab Streamer API client for all real-time market data services."""
    
    def __init__(self):
        self.ws = None
        self.is_connected = False
        self.is_authenticated = False
        self.thread = None
        self.ws_url = None
        self.schwab_client_customer_id = None
        self.schwab_client_correl_id = None
        self.schwab_client_channel = None
        self.schwab_client_function_id = None
        self.request_id_counter = 0
        self.last_heartbeat_time = None
        self.subscriptions = {}  # {service: {symbol: callback}}
        self.service_callbacks = {}  # {service: callback}
    
    def _get_user_preferences(self, access_token: str) -> Dict[str, Any]:
        """Get user preferences to extract Streamer configuration."""
        try:
            response = schwab_api_request("GET", SCHWAB_USER_PREF_URL, access_token)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user preferences: {e}")
            raise
    
    def _extract_streamer_config(self, prefs: Dict[str, Any], access_token: str):
        """Extract Streamer configuration from user preferences."""
        # Log the full preferences structure for debugging
        logger.debug(f"User preferences structure: {json.dumps(prefs, indent=2, default=str)}")
        
        # Extract WebSocket URL
        if 'streamerInfoUrl' in prefs:
            self.ws_url = prefs['streamerInfoUrl']
        elif 'streamerInfo' in prefs and isinstance(prefs['streamerInfo'], dict):
            self.ws_url = prefs['streamerInfo'].get('url') or prefs['streamerInfo'].get('streamerInfoUrl')
        else:
            # Search nested structures
            for key, value in prefs.items():
                if isinstance(value, dict) and 'streamerInfoUrl' in value:
                    self.ws_url = value['streamerInfoUrl']
                    break
        
        if not self.ws_url:
            self.ws_url = os.getenv("SCHWAB_WS_URL", "wss://streamer.schwab.com")
            logger.warning(f"streamerInfoUrl not found in preferences, using default: {self.ws_url}")
        
        # Extract Customer ID - try multiple possible field names
        self.schwab_client_customer_id = (
            prefs.get('schwabClientCustomerId') or 
            prefs.get('customerId') or
            prefs.get('clientId') or
            prefs.get('accountNumber')
        )
        
        # Also check in streamerInfo nested object
        if not self.schwab_client_customer_id and 'streamerInfo' in prefs:
            if isinstance(prefs['streamerInfo'], dict):
                self.schwab_client_customer_id = (
                    prefs['streamerInfo'].get('schwabClientCustomerId') or
                    prefs['streamerInfo'].get('customerId') or
                    prefs['streamerInfo'].get('clientId')
                )
        
        # If still not found, try to get from accounts endpoint as fallback
        if not self.schwab_client_customer_id:
            logger.warning("CustomerId not found in user preferences. Attempting to get from accounts endpoint...")
            try:
                from api.orders import SCHWAB_ACCOUNTS_URL
                accounts_response = schwab_api_request("GET", SCHWAB_ACCOUNTS_URL, access_token)
                accounts_data = accounts_response.json()
                
                # Handle both single object and array responses
                if isinstance(accounts_data, dict):
                    accounts_data = [accounts_data]
                
                if accounts_data and len(accounts_data) > 0:
                    # Try to extract customer ID from first account
                    # For Streamer API, we need the accountNumber (plain text account ID)
                    first_account = accounts_data[0]
                    sec_account = first_account.get("securitiesAccount", first_account)
                    
                    # Try multiple possible fields for account number
                    account_number = (
                        sec_account.get('accountNumber') or
                        first_account.get('accountNumber') or
                        str(sec_account.get('accountId', '')) or
                        str(first_account.get('accountId', ''))
                    )
                    
                    if account_number:
                        self.schwab_client_customer_id = str(account_number).strip()
                        logger.info(f"✓ Retrieved CustomerId from accounts endpoint: {self.schwab_client_customer_id}")
                    else:
                        logger.warning("Account number not found in accounts response structure")
                        logger.debug(f"Accounts response structure: {json.dumps(accounts_data[0], indent=2, default=str)}")
            except Exception as e:
                logger.error(f"Failed to get CustomerId from accounts endpoint: {e}", exc_info=True)
        
        self.schwab_client_correl_id = str(uuid.uuid4())
        self.schwab_client_channel = prefs.get('schwabClientChannel') or prefs.get('channel', 'IO')
        self.schwab_client_function_id = prefs.get('schwabClientFunctionId') or prefs.get('functionId', 'APIAPP')
        
        if not self.schwab_client_customer_id:
            logger.error("CRITICAL: CustomerId is None! Streamer connection will fail with 404 error.")
            logger.error("Please check user preferences API response structure.")
        else:
            logger.info(f"Streamer config: URL={self.ws_url}, CustomerId={self.schwab_client_customer_id}")
    
    def _get_next_request_id(self) -> str:
        """Get next unique request ID."""
        self.request_id_counter += 1
        return str(self.request_id_counter)
    
    def connect(self, access_token: Optional[str] = None):
        """Connect to Schwab Streamer API WebSocket."""
        if self.is_connected:
            return
        
        try:
            if not access_token:
                access_token = get_valid_access_token()
                if not access_token:
                    raise ValueError("No valid access token available")
            
            prefs = self._get_user_preferences(access_token)
            self._extract_streamer_config(prefs, access_token)
            
            if not self.ws_url:
                raise ValueError("WebSocket URL not found")
            
            if not self.schwab_client_customer_id:
                raise ValueError("CustomerId is required for Streamer connection but was not found in user preferences. Please check your Schwab API account configuration.")
            
            logger.info(f"Connecting to Schwab Streamer at {self.ws_url} with CustomerId={self.schwab_client_customer_id}")
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            self._access_token = access_token
            # Use run_forever with ping_interval to keep connection alive
            # Note: Some WebSocket libraries may need different connection methods
            self.thread = threading.Thread(
                target=self.ws.run_forever,
                kwargs={
                    'ping_interval': 20,  # Send ping every 20 seconds
                    'ping_timeout': 10,   # Wait 10 seconds for pong
                }
            )
            self.thread.daemon = True
            self.thread.start()
            logger.info("Schwab Streamer WebSocket connection initiated")
        
        except Exception as e:
            logger.error(f"Failed to connect: {e}", exc_info=True)
            raise
    
    def _on_open(self, ws):
        """Handle WebSocket open - send LOGIN command."""
        self.is_connected = True
        logger.info("WebSocket connected, sending LOGIN...")
        self._send_login()
    
    def _send_login(self):
        """Send LOGIN command."""
        if not self.ws or not self.is_connected:
            return
        
        request_id = self._get_next_request_id()
        login_request = {
            "requests": [{
                "requestid": request_id,
                "service": "ADMIN",
                "command": "LOGIN",
                "SchwabClientCustomerId": self.schwab_client_customer_id,
                "SchwabClientCorrelId": self.schwab_client_correl_id,
                "parameters": {
                    "Authorization": self._access_token,
                    "SchwabClientChannel": self.schwab_client_channel,
                    "SchwabClientFunctionId": self.schwab_client_function_id
                }
            }]
        }
        
        try:
            self.ws.send(json.dumps(login_request))
            logger.info(f"Sent LOGIN (requestid={request_id})")
        except Exception as e:
            logger.error(f"Failed to send LOGIN: {e}")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            if 'notify' in data:
                self._handle_notify(data['notify'])
            elif 'response' in data:
                self._handle_response(data['response'])
            elif 'data' in data:
                self._handle_data(data['data'])
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _handle_notify(self, notify_list: List[Dict]):
        """Handle notify messages (heartbeats)."""
        for notify in notify_list:
            if 'heartbeat' in notify:
                self.last_heartbeat_time = time.time()
                logger.debug(f"Heartbeat: {notify['heartbeat']}")
    
    def _handle_response(self, response_list: List[Dict]):
        """Handle response messages."""
        for response in response_list:
            service = response.get('service')
            command = response.get('command')
            code = response.get('content', {}).get('code')
            msg = response.get('content', {}).get('msg', '')
            
            logger.info(f"Response: {service}/{command}, code={code}, msg={msg}")
            
            if service == 'ADMIN' and command == 'LOGIN':
                if code == 0:
                    self.is_authenticated = True
                    logger.info("✓ LOGIN successful")
                    self._resubscribe_all()
                elif code == 3:
                    self.is_authenticated = False
                    logger.error("✗ LOGIN denied")
    
    def _handle_data(self, data_list: List[Dict]):
        """Handle data messages - route to appropriate parser."""
        for data_item in data_list:
            service = data_item.get('service')
            content = data_item.get('content', [])
            timestamp = data_item.get('timestamp')
            
            if service == SERVICE_LEVELONE_EQUITIES:
                self._handle_levelone_equities(content, timestamp)
            elif service == SERVICE_LEVELONE_OPTIONS:
                self._handle_levelone_options(content, timestamp)
            elif service == SERVICE_LEVELONE_FUTURES:
                self._handle_levelone_futures(content, timestamp)
            elif service == SERVICE_LEVELONE_FUTURES_OPTIONS:
                self._handle_levelone_futures_options(content, timestamp)
            elif service == SERVICE_LEVELONE_FOREX:
                self._handle_levelone_forex(content, timestamp)
            elif service in [SERVICE_NYSE_BOOK, SERVICE_NASDAQ_BOOK, SERVICE_OPTIONS_BOOK]:
                self._handle_book_data(service, content, timestamp)
            elif service in [SERVICE_CHART_EQUITY, SERVICE_CHART_FUTURES]:
                self._handle_chart_data(service, content, timestamp)
            elif service in [SERVICE_SCREENER_EQUITY, SERVICE_SCREENER_OPTION]:
                self._handle_screener_data(service, content, timestamp)
            elif service == SERVICE_ACCT_ACTIVITY:
                self._handle_account_activity(content, timestamp)
    
    # Data handlers for each service type
    def _handle_levelone_equities(self, content: List[Dict], timestamp: Optional[int]):
        """Handle LEVELONE_EQUITIES data."""
        if not isinstance(content, list):
            return
        for quote_data in content:
            symbol = quote_data.get('key')
            if symbol:
                parsed = self._parse_levelone_equities(quote_data)
                parsed['timestamp'] = timestamp
                self._call_callbacks(SERVICE_LEVELONE_EQUITIES, symbol, parsed)
    
    def _parse_levelone_equities(self, quote_data: Dict) -> Dict[str, Any]:
        """Parse LEVELONE_EQUITIES fields (0-51)."""
        parsed = {
            'symbol': quote_data.get('key'),
            'delayed': quote_data.get('delayed', False),
            'asset_main_type': quote_data.get('assetMainType'),
            'asset_sub_type': quote_data.get('assetSubType'),
            'cusip': quote_data.get('cusip'),
        }
        # Field mappings 0-51
        field_map = {
            '1': 'bid_price', '2': 'ask_price', '3': 'last_price', '4': 'bid_size',
            '5': 'ask_size', '6': 'ask_id', '7': 'bid_id', '8': 'total_volume',
            '9': 'last_size', '10': 'high_price', '11': 'low_price', '12': 'close_price',
            '13': 'exchange_id', '14': 'marginable', '15': 'description', '16': 'last_id',
            '17': 'open_price', '18': 'net_change', '19': '52_week_high', '20': '52_week_low',
            '21': 'pe_ratio', '22': 'annual_dividend_amount', '23': 'dividend_yield', '24': 'nav',
            '25': 'exchange_name', '26': 'dividend_date', '27': 'regular_market_quote',
            '28': 'regular_market_trade', '29': 'regular_market_last_price', '30': 'regular_market_last_size',
            '31': 'regular_market_net_change', '32': 'security_status', '33': 'mark_price',
            '34': 'quote_time', '35': 'trade_time', '36': 'regular_market_trade_time',
            '37': 'bid_time', '38': 'ask_time', '39': 'ask_mic_id', '40': 'bid_mic_id',
            '41': 'last_mic_id', '42': 'net_percent_change', '43': 'regular_market_percent_change',
            '44': 'mark_price_net_change', '45': 'mark_price_percent_change', '46': 'hard_to_borrow_quantity',
            '47': 'hard_to_borrow_rate', '48': 'hard_to_borrow', '49': 'shortable',
            '50': 'post_market_net_change', '51': 'post_market_percent_change',
        }
        for field_num, field_name in field_map.items():
            if field_num in quote_data:
                parsed[field_name] = quote_data[field_num]
        if 'bid_price' in parsed and 'ask_price' in parsed:
            if parsed['bid_price'] and parsed['ask_price']:
                parsed['spread'] = parsed['ask_price'] - parsed['bid_price']
                if parsed['bid_price'] > 0:
                    parsed['spread_percent'] = (parsed['spread'] / parsed['bid_price']) * 100
        return parsed
    
    def _handle_levelone_options(self, content: List[Dict], timestamp: Optional[int]):
        """Handle LEVELONE_OPTIONS data."""
        if not isinstance(content, list):
            return
        for quote_data in content:
            symbol = quote_data.get('key')
            if symbol:
                parsed = self._parse_levelone_options(quote_data)
                parsed['timestamp'] = timestamp
                self._call_callbacks(SERVICE_LEVELONE_OPTIONS, symbol, parsed)
    
    def _parse_levelone_options(self, quote_data: Dict) -> Dict[str, Any]:
        """Parse LEVELONE_OPTIONS fields (0-37)."""
        parsed = {
            'symbol': quote_data.get('key'),
            'delayed': quote_data.get('delayed', False),
            'asset_main_type': quote_data.get('assetMainType'),
            'asset_sub_type': quote_data.get('assetSubType'),
            'cusip': quote_data.get('cusip'),
        }
        field_map = {
            '1': 'description', '2': 'bid_price', '3': 'ask_price', '4': 'last_price',
            '5': 'high_price', '6': 'low_price', '7': 'close_price', '8': 'total_volume',
            '9': 'open_interest', '10': 'volatility', '11': 'money_intrinsic_value',
            '12': 'expiration_year', '13': 'multiplier', '14': 'digits', '15': 'open_price',
            '16': 'bid_size', '17': 'ask_size', '18': 'last_size', '19': 'net_change',
            '20': 'strike_price', '21': 'contract_type', '22': 'underlying', '23': 'expiration_month',
            '24': 'deliverables', '25': 'time_value', '26': 'expiration_day', '27': 'days_to_expiration',
            '28': 'delta', '29': 'gamma', '30': 'theta', '31': 'vega', '32': 'rho',
            '33': 'security_status', '34': 'theoretical_option_value', '35': 'underlying_price',
            '36': 'uv_expiration_type', '37': 'mark_price',
        }
        for field_num, field_name in field_map.items():
            if field_num in quote_data:
                parsed[field_name] = quote_data[field_num]
        return parsed
    
    def _handle_levelone_futures(self, content: List[Dict], timestamp: Optional[int]):
        """Handle LEVELONE_FUTURES data."""
        if not isinstance(content, list):
            return
        for quote_data in content:
            symbol = quote_data.get('key')
            if symbol:
                parsed = self._parse_levelone_futures(quote_data)
                parsed['timestamp'] = timestamp
                self._call_callbacks(SERVICE_LEVELONE_FUTURES, symbol, parsed)
    
    def _parse_levelone_futures(self, quote_data: Dict) -> Dict[str, Any]:
        """Parse LEVELONE_FUTURES fields (0-40)."""
        parsed = {'symbol': quote_data.get('key'), 'delayed': quote_data.get('delayed', False)}
        field_map = {
            '1': 'bid_price', '2': 'ask_price', '3': 'last_price', '4': 'bid_size', '5': 'ask_size',
            '6': 'bid_id', '7': 'ask_id', '8': 'total_volume', '9': 'last_size', '10': 'quote_time',
            '11': 'trade_time', '12': 'high_price', '13': 'low_price', '14': 'close_price', '15': 'last_id',
            '16': 'description', '17': 'open_price', '18': 'open_interest', '19': 'mark', '20': 'tick',
            '21': 'tick_amount', '22': 'future_multiplier', '23': 'future_settlement_price', '24': 'underlying_symbol',
            '25': 'strike_price', '26': 'future_expiration_date', '27': 'expiration_style', '28': 'contract_type',
            '29': 'security_status', '30': 'exchange', '31': 'exchange_name', '32': 'future_price_format',
            '33': 'future_trading_hours', '34': 'future_is_tradable', '35': 'future_multiplier_alt',
            '36': 'future_is_active', '37': 'ask_time', '38': 'bid_time', '39': 'quoted_in_session', '40': 'settlement_date',
        }
        for field_num, field_name in field_map.items():
            if field_num in quote_data:
                parsed[field_name] = quote_data[field_num]
        return parsed
    
    def _handle_levelone_futures_options(self, content: List[Dict], timestamp: Optional[int]):
        """Handle LEVELONE_FUTURES_OPTIONS data."""
        if not isinstance(content, list):
            return
        for quote_data in content:
            symbol = quote_data.get('key')
            if symbol:
                parsed = self._parse_levelone_futures_options(quote_data)
                parsed['timestamp'] = timestamp
                self._call_callbacks(SERVICE_LEVELONE_FUTURES_OPTIONS, symbol, parsed)
    
    def _parse_levelone_futures_options(self, quote_data: Dict) -> Dict[str, Any]:
        """Parse LEVELONE_FUTURES_OPTIONS fields (0-22)."""
        parsed = {'symbol': quote_data.get('key'), 'delayed': quote_data.get('delayed', False)}
        field_map = {
            '1': 'bid_price', '2': 'ask_price', '3': 'last_price', '4': 'bid_size', '5': 'ask_size',
            '6': 'bid_id', '7': 'ask_id', '8': 'total_volume', '9': 'last_size', '10': 'quote_time',
            '11': 'trade_time', '12': 'high_price', '13': 'low_price', '14': 'close_price', '15': 'last_id',
            '16': 'description', '17': 'open_price', '18': 'open_interest', '19': 'mark', '20': 'tick',
            '21': 'tick_amount', '22': 'future_multiplier',
        }
        for field_num, field_name in field_map.items():
            if field_num in quote_data:
                parsed[field_name] = quote_data[field_num]
        return parsed
    
    def _handle_levelone_forex(self, content: List[Dict], timestamp: Optional[int]):
        """Handle LEVELONE_FOREX data."""
        if not isinstance(content, list):
            return
        for quote_data in content:
            symbol = quote_data.get('key')
            if symbol:
                parsed = self._parse_levelone_forex(quote_data)
                parsed['timestamp'] = timestamp
                self._call_callbacks(SERVICE_LEVELONE_FOREX, symbol, parsed)
    
    def _parse_levelone_forex(self, quote_data: Dict) -> Dict[str, Any]:
        """Parse LEVELONE_FOREX fields (0-23)."""
        parsed = {'symbol': quote_data.get('key'), 'delayed': quote_data.get('delayed', False)}
        field_map = {
            '1': 'bid_price', '2': 'ask_price', '3': 'last_price', '4': 'bid_size', '5': 'ask_size',
            '6': 'total_volume', '7': 'last_size', '8': 'quote_time', '9': 'trade_time',
            '10': 'high_price', '11': 'low_price', '12': 'close_price', '13': 'exchange', '14': 'description',
            '15': 'open_price', '16': 'net_change', '17': 'percent_change', '18': 'exchange_name',
            '19': 'digits', '20': 'security_status', '21': 'tick', '22': 'tick_amount', '23': 'product',
        }
        for field_num, field_name in field_map.items():
            if field_num in quote_data:
                parsed[field_name] = quote_data[field_num]
        return parsed
    
    def _handle_book_data(self, service: str, content: List[Dict], timestamp: Optional[int]):
        """Handle BOOK services data."""
        if not isinstance(content, list):
            return
        for book_data in content:
            symbol = book_data.get('0')
            if symbol:
                parsed = self._parse_book_data(book_data)
                parsed['service'] = service
                parsed['timestamp'] = timestamp
                self._call_callbacks(service, symbol, parsed)
    
    def _parse_book_data(self, book_data: Dict) -> Dict[str, Any]:
        """Parse BOOK services data."""
        parsed = {
            'symbol': book_data.get('0'),
            'market_snapshot_time': book_data.get('1'),
        }
        if '2' in book_data and isinstance(book_data['2'], list):
            parsed['bid_levels'] = [self._parse_price_level(level) for level in book_data['2']]
        if '3' in book_data and isinstance(book_data['3'], list):
            parsed['ask_levels'] = [self._parse_price_level(level) for level in book_data['3']]
        return parsed
    
    def _parse_price_level(self, level: Dict) -> Dict[str, Any]:
        """Parse Book Price Level."""
        parsed = {
            'price': level.get('0'),
            'aggregate_size': level.get('1'),
            'market_maker_count': level.get('2'),
        }
        if '3' in level and isinstance(level['3'], list):
            parsed['market_makers'] = [self._parse_market_maker(mm) for mm in level['3']]
        return parsed
    
    def _parse_market_maker(self, mm: Dict) -> Dict[str, Any]:
        """Parse Book Market Maker."""
        return {
            'market_maker_id': mm.get('0'),
            'size': mm.get('1'),
            'quote_time': mm.get('2'),
        }
    
    def _handle_chart_data(self, service: str, content: List[Dict], timestamp: Optional[int]):
        """Handle CHART services data."""
        if not isinstance(content, list):
            return
        for chart_data in content:
            symbol = chart_data.get('key') or chart_data.get('0')
            if symbol:
                parsed = self._parse_chart_data(chart_data)
                parsed['service'] = service
                parsed['timestamp'] = timestamp
                
                # Store latest candle for real-time chart updates
                if symbol.upper() not in latest_chart_data:
                    latest_chart_data[symbol.upper()] = {}
                
                # Convert chart data to candle format
                candle = {
                    'time': parsed.get('chart_time'),  # milliseconds since epoch
                    'open': parsed.get('open_price'),
                    'high': parsed.get('high_price'),
                    'low': parsed.get('low_price'),
                    'close': parsed.get('close_price'),
                    'volume': parsed.get('volume'),
                    'timestamp': timestamp or parsed.get('chart_time')
                }
                latest_chart_data[symbol.upper()] = candle
                
                self._call_callbacks(service, symbol, parsed)
    
    def _parse_chart_data(self, chart_data: Dict) -> Dict[str, Any]:
        """Parse CHART services data."""
        parsed = {'symbol': chart_data.get('key') or chart_data.get('0')}
        field_map = {
            '1': 'open_price', '2': 'high_price', '3': 'low_price', '4': 'close_price',
            '5': 'volume', '6': 'sequence', '7': 'chart_time', '8': 'chart_day',
        }
        for field_num, field_name in field_map.items():
            if field_num in chart_data:
                parsed[field_name] = chart_data[field_num]
        return parsed
    
    def _handle_screener_data(self, service: str, content: List[Dict], timestamp: Optional[int]):
        """Handle SCREENER services data."""
        if not isinstance(content, list):
            return
        for screener_data in content:
            parsed = self._parse_screener_data(screener_data)
            parsed['service'] = service
            parsed['timestamp'] = timestamp
            if service in self.service_callbacks:
                try:
                    self.service_callbacks[service](parsed)
                except Exception as e:
                    logger.error(f"Error in screener callback: {e}")
    
    def _parse_screener_data(self, screener_data: Dict) -> Dict[str, Any]:
        """Parse SCREENER services data."""
        return {
            'symbol': screener_data.get('0'),
            'timestamp': screener_data.get('1'),
            'sort_field': screener_data.get('2'),
            'frequency': screener_data.get('3'),
            'items': screener_data.get('4', []),
        }
    
    def _handle_account_activity(self, content: List[Dict], timestamp: Optional[int]):
        """Handle ACCT_ACTIVITY data."""
        if not isinstance(content, list):
            return
        for activity_data in content:
            parsed = self._parse_account_activity(activity_data)
            parsed['timestamp'] = timestamp
            if SERVICE_ACCT_ACTIVITY in self.service_callbacks:
                try:
                    self.service_callbacks[SERVICE_ACCT_ACTIVITY](parsed)
                except Exception as e:
                    logger.error(f"Error in account activity callback: {e}")
    
    def _parse_account_activity(self, activity_data: Dict) -> Dict[str, Any]:
        """Parse ACCT_ACTIVITY data."""
        parsed = {
            'seq': activity_data.get('seq'),
            'key': activity_data.get('key'),
            'account': activity_data.get('1'),
            'message_type': activity_data.get('2'),
            'message_data': activity_data.get('3'),
        }
        if parsed['message_data'] and isinstance(parsed['message_data'], str):
            try:
                parsed['message_data_parsed'] = json.loads(parsed['message_data'])
            except json.JSONDecodeError:
                pass
        return parsed
    
    def _call_callbacks(self, service: str, symbol: str, parsed: Dict):
        """Call registered callbacks for a service and symbol."""
        if service in self.service_callbacks:
            try:
                self.service_callbacks[service](parsed)
            except Exception as e:
                logger.error(f"Error in service callback for {service}: {e}")
        if service in self.subscriptions:
            if symbol in self.subscriptions[service]:
                try:
                    self.subscriptions[service][symbol](parsed)
                except Exception as e:
                    logger.error(f"Error in callback for {symbol}: {e}")
    
    def subscribe(self, service: str, symbols: List[str], callback: Optional[Callable] = None,
                  fields: Optional[str] = None, service_callback: Optional[Callable] = None):
        """Subscribe to a service for given symbols."""
        if service not in self.subscriptions:
            self.subscriptions[service] = {}
        
        for symbol in symbols:
            symbol = symbol.upper()
        if callback:
                self.subscriptions[service][symbol] = callback
        
        if service_callback:
            self.service_callbacks[service] = service_callback
        
        if self.is_authenticated:
            self._send_subs(service, symbols, fields)
        else:
            logger.info(f"Symbols {symbols} queued for {service} (waiting for authentication)")
    
    def _resubscribe_all(self):
        """Resubscribe to all queued subscriptions."""
        for service, symbols_dict in self.subscriptions.items():
            if symbols_dict:
                self._send_subs(service, list(symbols_dict.keys()))
    
    def _send_subs(self, service: str, symbols: List[str], fields: Optional[str] = None):
        """Send SUBS command."""
        if not self.ws or not self.is_authenticated:
            return
        
        if not fields:
            fields = self._get_default_fields(service)
        
        request_id = self._get_next_request_id()
        subs_request = {
            "requests": [{
                "requestid": request_id,
                "service": service,
                "command": "SUBS",
                "SchwabClientCustomerId": self.schwab_client_customer_id,
                "SchwabClientCorrelId": self.schwab_client_correl_id,
                "parameters": {
                    "keys": ",".join(symbols),
                    "fields": fields
                }
            }]
        }
        
        if service == SERVICE_ACCT_ACTIVITY:
            subs_request["requests"][0]["parameters"]["keys"] = symbols[0] if symbols else "Account Activity"
            subs_request["requests"][0]["parameters"]["fields"] = "0,1,2,3"
        
        try:
            self.ws.send(json.dumps(subs_request))
            logger.info(f"Sent SUBS for {service}: {len(symbols)} symbol(s)")
        except Exception as e:
            logger.error(f"Failed to send SUBS for {service}: {e}")
    
    def _get_default_fields(self, service: str) -> str:
        """Get default fields for a service."""
        defaults = {
            SERVICE_LEVELONE_EQUITIES: "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51",
            SERVICE_LEVELONE_OPTIONS: "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37",
            SERVICE_LEVELONE_FUTURES: "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40",
            SERVICE_LEVELONE_FUTURES_OPTIONS: "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22",
            SERVICE_LEVELONE_FOREX: "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23",
            SERVICE_CHART_EQUITY: "0,1,2,3,4,5,6,7,8",
            SERVICE_CHART_FUTURES: "0,1,2,3,4,5,6,7",
        }
        return defaults.get(service, "0,1,2,3,4,5")
    
    def unsubscribe(self, service: str, symbols: List[str]):
        """Unsubscribe from symbols for a service."""
        if service in self.subscriptions:
            for symbol in symbols:
                self.subscriptions[service].pop(symbol.upper(), None)
        
        if self.is_authenticated:
            self._send_unsubs(service, symbols)
    
    def _send_unsubs(self, service: str, symbols: List[str]):
        """Send UNSUBS command."""
        if not self.ws or not self.is_authenticated:
            return
        
        request_id = self._get_next_request_id()
        unsubs_request = {
            "requests": [{
                "requestid": request_id,
                "service": service,
                "command": "UNSUBS",
                "SchwabClientCustomerId": self.schwab_client_customer_id,
                "SchwabClientCorrelId": self.schwab_client_correl_id,
                "parameters": {"keys": ",".join(symbols)}
            }]
        }
        
        try:
            self.ws.send(json.dumps(unsubs_request))
            logger.info(f"Sent UNSUBS for {service}: {len(symbols)} symbol(s)")
        except Exception as e:
            logger.error(f"Failed to send UNSUBS for {service}: {e}")
    
    def disconnect(self):
        """Disconnect from Streamer."""
        if self.ws and self.is_authenticated:
            request_id = self._get_next_request_id()
            logout_request = {
                "requests": [{
                    "requestid": request_id,
                    "service": "ADMIN",
                    "command": "LOGOUT",
                    "SchwabClientCustomerId": self.schwab_client_customer_id,
                    "SchwabClientCorrelId": self.schwab_client_correl_id,
                    "parameters": {}
                }]
            }
            try:
                self.ws.send(json.dumps(logout_request))
                logger.info("Sent LOGOUT")
            except Exception as e:
                logger.error(f"Failed to send LOGOUT: {e}")
        
        if self.ws:
            self.ws.close()
        
        self.is_connected = False
        self.is_authenticated = False
        self.subscriptions.clear()
        self.service_callbacks.clear()
        logger.info("Schwab Streamer disconnected")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current Streamer status."""
        return {
            "connected": self.is_connected,
            "authenticated": self.is_authenticated,
            "subscriptions": {service: list(symbols.keys()) for service, symbols in self.subscriptions.items()},
            "last_heartbeat": self.last_heartbeat_time,
            "ws_url": self.ws_url,
            "customer_id": self.schwab_client_customer_id
        }
    
    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        # Parse error to get more details
        error_str = str(error)
        if hasattr(error, 'status_code'):
            error_str = f"Handshake status {error.status_code} {getattr(error, 'status_message', '')}"
        elif isinstance(error, tuple) and len(error) >= 2:
            error_str = f"Handshake status {error[0]} {error[1] if len(error) > 1 else ''}"
        
        logger.error(f"WebSocket error: {error_str} -+-+- {error}")
        self.is_connected = False
        self.is_authenticated = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.is_connected = False
        self.is_authenticated = False

# Global streamer instance
streamer = SchwabStreamer()

# In-memory store for latest chart candle data (for real-time chart updates)
# Format: {symbol: {time, open, high, low, close, volume, timestamp}}
latest_chart_data = {}

# API Endpoints
@streaming_bp.route('/connect', methods=['POST'])
def connect_stream():
    """Connect to Schwab Streamer WebSocket."""
    tokens = load_tokens()
    if not tokens or 'access_token' not in tokens:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        streamer.connect(tokens['access_token'])
        return jsonify({"status": "connecting", "message": "WebSocket connection initiated"}), 200
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return jsonify({"error": str(e)}), 500

@streaming_bp.route('/subscribe/<service>/<symbol>', methods=['POST'])
def subscribe_symbol(service: str, symbol: str):
    """Subscribe to a symbol for a specific service."""
    try:
        data = request.get_json() or {}
        fields = data.get('fields')
        symbols = [s.strip().upper() for s in symbol.split(',')]
        streamer.subscribe(service.upper(), symbols, fields=fields)
        return jsonify({"status": "subscribed", "service": service, "symbols": symbols}), 200
    except Exception as e:
        logger.error(f"Failed to subscribe: {e}")
        return jsonify({"error": str(e)}), 500

@streaming_bp.route('/unsubscribe/<service>/<symbol>', methods=['POST'])
def unsubscribe_symbol(service: str, symbol: str):
    """Unsubscribe from a symbol for a specific service."""
    try:
        symbols = [s.strip().upper() for s in symbol.split(',')]
        streamer.unsubscribe(service.upper(), symbols)
        return jsonify({"status": "unsubscribed", "service": service, "symbols": symbols}), 200
    except Exception as e:
        logger.error(f"Failed to unsubscribe: {e}")
        return jsonify({"error": str(e)}), 500

@streaming_bp.route('/disconnect', methods=['POST'])
def disconnect_stream():
    """Disconnect from Schwab Streamer."""
    try:
        streamer.disconnect()
        return jsonify({"status": "disconnected"}), 200
    except Exception as e:
        logger.error(f"Failed to disconnect: {e}")
        return jsonify({"error": str(e)}), 500

@streaming_bp.route('/status', methods=['GET'])
def stream_status():
    """Get streaming status."""
    return jsonify(streamer.get_status()), 200

@streaming_bp.route('/diagnostics', methods=['GET'])
def get_streamer_diagnostics():
    """
    Diagnostic endpoint to check WebSocket configuration.
    Returns detailed information about WebSocket URL, CustomerId, and user preferences.
    """
    try:
        tokens = load_tokens()
        if not tokens or 'access_token' not in tokens:
            return jsonify({
                "error": "Not authenticated",
                "message": "Please authenticate first using /auth/login"
            }), 401
        
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({
                "error": "No valid access token",
                "message": "Please authenticate first using /auth/login"
            }), 401
        
        # Get user preferences
        try:
            response = schwab_api_request("GET", SCHWAB_USER_PREF_URL, access_token)
            prefs = response.json()
        except Exception as e:
            return jsonify({
                "error": "Failed to get user preferences",
                "details": str(e),
                "endpoint": SCHWAB_USER_PREF_URL
            }), 500
        
        # Extract WebSocket configuration
        ws_url = None
        customer_id = None
        
        # Try to find WebSocket URL
        if 'streamerInfoUrl' in prefs:
            ws_url = prefs['streamerInfoUrl']
        elif 'streamerInfo' in prefs and isinstance(prefs['streamerInfo'], dict):
            ws_url = prefs['streamerInfo'].get('url') or prefs['streamerInfo'].get('streamerInfoUrl')
        else:
            # Search nested structures
            for key, value in prefs.items():
                if isinstance(value, dict) and 'streamerInfoUrl' in value:
                    ws_url = value['streamerInfoUrl']
                    break
        
        if not ws_url:
            ws_url = os.getenv("SCHWAB_WS_URL", "wss://streamer.schwab.com")
        
        # Try to find Customer ID
        customer_id = (
            prefs.get('schwabClientCustomerId') or 
            prefs.get('customerId') or
            prefs.get('clientId') or
            prefs.get('accountNumber')
        )
        
        if not customer_id and 'streamerInfo' in prefs:
            if isinstance(prefs['streamerInfo'], dict):
                customer_id = (
                    prefs['streamerInfo'].get('schwabClientCustomerId') or
                    prefs['streamerInfo'].get('customerId') or
                    prefs['streamerInfo'].get('clientId')
                )
        
        # Try accounts endpoint as fallback
        if not customer_id:
            try:
                from api.orders import SCHWAB_ACCOUNTS_URL
                accounts_response = schwab_api_request("GET", SCHWAB_ACCOUNTS_URL, access_token)
                accounts_data = accounts_response.json()
                
                if isinstance(accounts_data, dict):
                    accounts_data = [accounts_data]
                
                if accounts_data and len(accounts_data) > 0:
                    first_account = accounts_data[0]
                    sec_account = first_account.get("securitiesAccount", first_account)
                    customer_id = (
                        sec_account.get('accountNumber') or
                        first_account.get('accountNumber') or
                        str(sec_account.get('accountId', '')) or
                        str(first_account.get('accountId', ''))
                    )
            except Exception as e:
                logger.warning(f"Failed to get CustomerId from accounts: {e}")
        
        # Extract other config
        channel = prefs.get('schwabClientChannel') or prefs.get('channel', 'IO')
        function_id = prefs.get('schwabClientFunctionId') or prefs.get('functionId', 'APIAPP')
        
        return jsonify({
            "websocket_config": {
                "url": ws_url,
                "url_source": "user_preferences" if ws_url != os.getenv("SCHWAB_WS_URL", "wss://streamer.schwab.com") else "default_env",
                "customer_id": customer_id,
                "customer_id_source": "user_preferences" if customer_id else "accounts_endpoint_or_missing",
                "channel": channel,
                "function_id": function_id
            },
            "user_preferences_structure": {
                "top_level_keys": list(prefs.keys()),
                "has_streamerInfo": 'streamerInfo' in prefs,
                "has_streamerInfoUrl": 'streamerInfoUrl' in prefs,
                "full_structure": prefs  # Include full structure for debugging
            },
            "connection_status": streamer.get_status(),
            "recommendations": {
                "websocket_url_check": "Verify the WebSocket URL format matches Schwab's current requirements",
                "customer_id_check": "Ensure CustomerId is present and correct (required for Streamer connection)",
                "if_404_error": "The 404 error suggests the WebSocket URL or connection method may be incorrect"
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Diagnostics failed: {e}", exc_info=True)
        return jsonify({
            "error": "Diagnostics failed",
            "details": str(e)
        }), 500

@streaming_bp.route('/chart/latest/<symbol>', methods=['GET'])
def get_latest_chart_candle(symbol: str):
    """Get the latest real-time candle for a symbol."""
    symbol_upper = symbol.upper()
    
    # Check if Streamer is connected and authenticated
    if not streamer.is_connected or not streamer.is_authenticated:
        return jsonify({
            "symbol": symbol_upper,
            "candle": None,
            "has_data": False,
            "streamer_connected": False,
            "message": "Streamer not connected. Real-time data requires Streamer connection."
        }), 200  # Return 200 with has_data=false instead of 404
    
    if symbol_upper in latest_chart_data:
        return jsonify({
            "symbol": symbol_upper,
            "candle": latest_chart_data[symbol_upper],
            "has_data": True,
            "streamer_connected": True
        }), 200
    else:
        # Check if symbol is subscribed
        is_subscribed = (SERVICE_CHART_EQUITY in streamer.subscriptions and 
                        symbol_upper in streamer.subscriptions[SERVICE_CHART_EQUITY])
        
        return jsonify({
            "symbol": symbol_upper,
            "candle": None,
            "has_data": False,
            "streamer_connected": True,
            "is_subscribed": is_subscribed,
            "message": "No real-time data available yet. Data will appear once Streamer receives candle updates for this symbol."
        }), 200  # Return 200 with has_data=false instead of 404

# Legacy endpoints for backward compatibility
@streaming_bp.route('/subscribe/<symbol>', methods=['POST'])
def subscribe_symbol_legacy(symbol: str):
    """Legacy: Subscribe to LEVELONE_EQUITIES."""
    return subscribe_symbol(SERVICE_LEVELONE_EQUITIES, symbol)

@streaming_bp.route('/unsubscribe/<symbol>', methods=['POST'])
def unsubscribe_symbol_legacy(symbol: str):
    """Legacy: Unsubscribe from LEVELONE_EQUITIES."""
    return unsubscribe_symbol(SERVICE_LEVELONE_EQUITIES, symbol)
