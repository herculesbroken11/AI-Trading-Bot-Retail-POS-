"""
Massive (Polygon.io) API Client Wrapper
Uses the official Massive SDK from client-python directory.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from utils.logger import setup_logger

logger = setup_logger("massive_client")

# Add client-python to Python path
_client_python_path = Path(__file__).parent.parent.parent / "client-python"
if _client_python_path.exists() and str(_client_python_path) not in sys.path:
    sys.path.insert(0, str(_client_python_path))

try:
    from massive import RESTClient
    from massive.exceptions import AuthError, BadResponse
    SDK_AVAILABLE = True
except ImportError:
    # SDK not available - this is expected if client-python directory is removed
    # Don't log as warning, just silently mark as unavailable
    SDK_AVAILABLE = False
    RESTClient = None
    AuthError = Exception
    BadResponse = Exception


class MassiveClientWrapper:
    """
    Wrapper around Massive SDK RESTClient that maintains our existing interface.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Massive client.
        
        Args:
            api_key: API key (if None, loads from POLYGON_API_KEY env var)
        """
        if not SDK_AVAILABLE:
            raise ImportError("Massive SDK not available. Please ensure client-python directory exists.")
        
        if api_key is None:
            api_key = os.getenv('POLYGON_API_KEY') or os.getenv('MASSIVE_API_KEY')
            if not api_key:
                raise ValueError("POLYGON_API_KEY or MASSIVE_API_KEY not found in environment variables")
        
        # Use api.massive.com (new) or api.polygon.io (legacy)
        # Both work, but massive.com is the new default
        base_url = os.getenv('POLYGON_BASE_URL', 'https://api.massive.com')
        
        self.client = RESTClient(
            api_key=api_key,
            base=base_url,
            pagination=False,  # We'll handle pagination manually for now
            retries=3,
            connect_timeout=10.0,
            read_timeout=30.0,
        )
        logger.info(f"Massive client initialized with base URL: {base_url}")
    
    def get_aggregates(
        self,
        symbol: str,
        multiplier: int,
        timespan: str,
        from_date: str,
        to_date: str,
        adjusted: bool = True,
        sort: str = "asc",
        limit: Optional[int] = 50000,
    ) -> Dict[str, Any]:
        """
        Get aggregate bars (candles) for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            multiplier: Size of the timespan multiplier (e.g., 1 for 1 minute)
            timespan: Size of the time window ('minute', 'hour', 'day', etc.)
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            adjusted: Whether results are adjusted for splits
            sort: Sort order ('asc' or 'desc')
            limit: Maximum number of results (default 50000)
        
        Returns:
            Dictionary with 'candles' array matching our existing format
        """
        try:
            # Use the SDK's get_aggs method (non-paginated, returns list)
            aggs = self.client.get_aggs(
                ticker=symbol.upper(),
                multiplier=multiplier,
                timespan=timespan,
                from_=from_date,
                to=to_date,
                adjusted=adjusted,
                sort=sort,
                limit=limit,
            )
            
            # Convert SDK format to our existing format
            candles = []
            for agg in aggs:
                candle = {
                    "datetime": agg.timestamp,  # Timestamp in milliseconds
                    "open": agg.open,
                    "high": agg.high,
                    "low": agg.low,
                    "close": agg.close,
                    "volume": agg.volume,
                }
                candles.append(candle)
            
            logger.info(f"Fetched {len(candles)} candles from Massive API for {symbol}")
            return {"candles": candles}
            
        except AuthError as e:
            logger.error(f"Massive API authentication error: {e}")
            raise Exception(f"Massive API authentication failed: {str(e)}")
        except BadResponse as e:
            logger.error(f"Massive API bad response: {e}")
            raise Exception(f"Massive API request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Massive API request error: {e}")
            raise Exception(f"Massive API request failed: {str(e)}")


def polygon_api_request_v2(
    symbol: str,
    multiplier: int,
    timespan: str,
    from_date: str,
    to_date: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch historical market data from Massive (Polygon.io) API using the official SDK.
    This is the new version that uses the SDK.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        multiplier: Size of the timespan multiplier (e.g., 1 for 1 minute)
        timespan: Size of the time window ('minute', 'hour', 'day', etc.)
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format
        api_key: API key (if None, loads from POLYGON_API_KEY env var)
    
    Returns:
        Dictionary with 'candles' array matching Schwab format
    """
    if not SDK_AVAILABLE:
        # Raise ImportError to trigger fallback in helpers.py
        raise ImportError("Massive SDK not available")
    
    client = MassiveClientWrapper(api_key=api_key)
    return client.get_aggregates(
        symbol=symbol,
        multiplier=multiplier,
        timespan=timespan,
        from_date=from_date,
        to_date=to_date,
    )

