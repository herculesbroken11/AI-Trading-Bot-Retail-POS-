"""
Data Normalization Service
Normalizes market data to different timeframes (1min, 5min, daily) and calculates indicators.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.logger import setup_logger
from utils.market_data_db import store_market_data, get_market_data

logger = setup_logger("data_normalizer")

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Volume-Weighted Average Price (VWAP).
    
    Args:
        df: DataFrame with 'close' and 'volume' columns
        
    Returns:
        Series with VWAP values
    """
    if df.empty or 'close' not in df.columns or 'volume' not in df.columns:
        return pd.Series(dtype=float)
    
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).
    
    Args:
        df: DataFrame with price data
        period: EMA period
        column: Column to calculate EMA on (default: 'close')
        
    Returns:
        Series with EMA values
    """
    if df.empty or column not in df.columns:
        return pd.Series(dtype=float)
    
    return df[column].ewm(span=period, adjust=False).mean()

def normalize_to_timeframe(
    df: pd.DataFrame,
    target_timeframe: str,
    symbol: str
) -> pd.DataFrame:
    """
    Normalize market data to target timeframe.
    
    Args:
        df: DataFrame with OHLCV data (must have datetime index)
        target_timeframe: Target timeframe ('1min', '5min', 'daily')
        symbol: Stock symbol
        
    Returns:
        Normalized DataFrame
    """
    if df.empty:
        return df
    
    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'datetime' in df.columns:
            df.set_index('datetime', inplace=True)
        elif 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('datetime', inplace=True)
        else:
            logger.error("DataFrame must have datetime index or datetime/timestamp column")
            return pd.DataFrame()
    
    # Resample to target timeframe
    if target_timeframe == '1min':
        rule = '1T'  # 1 minute
    elif target_timeframe == '5min':
        rule = '5T'  # 5 minutes
    elif target_timeframe == 'daily':
        rule = '1D'  # 1 day
    else:
        logger.error(f"Unsupported timeframe: {target_timeframe}")
        return pd.DataFrame()
    
    # Resample OHLCV data
    resampled = pd.DataFrame()
    resampled['open'] = df['open'].resample(rule).first()
    resampled['high'] = df['high'].resample(rule).max()
    resampled['low'] = df['low'].resample(rule).min()
    resampled['close'] = df['close'].resample(rule).last()
    resampled['volume'] = df['volume'].resample(rule).sum()
    
    # Remove NaN rows (incomplete bars)
    resampled = resampled.dropna()
    
    if resampled.empty:
        return resampled
    
    # Calculate VWAP
    resampled['vwap'] = calculate_vwap(resampled)
    
    # Calculate EMA 20 and EMA 200
    resampled['ema_20'] = calculate_ema(resampled, 20)
    resampled['ema_200'] = calculate_ema(resampled, 200)
    
    # Convert index back to timestamp in milliseconds
    resampled['timestamp'] = resampled.index.astype(np.int64) // 10**6
    
    logger.info(f"Normalized {len(df)} bars to {len(resampled)} {target_timeframe} bars for {symbol}")
    
    return resampled

def process_and_store_bar(
    symbol: str,
    bar_data: Dict,
    source_timeframe: str = '1min'
):
    """
    Process a new bar and store it in database.
    Also normalizes to other timeframes if needed.
    
    Args:
        symbol: Stock symbol
        bar_data: Dictionary with OHLCV data
        source_timeframe: Timeframe of the source data
    """
    try:
        # Store the original bar
        store_market_data(
            symbol=symbol,
            timestamp=bar_data['timestamp'],
            timeframe=source_timeframe,
            open_price=bar_data['open'],
            high=bar_data['high'],
            low=bar_data['low'],
            close=bar_data['close'],
            volume=bar_data['volume'],
            vwap=bar_data.get('vwap'),
            ema_20=bar_data.get('ema_20'),
            ema_200=bar_data.get('ema_200')
        )
        
        # If source is 1min, we can normalize to 5min and daily
        if source_timeframe == '1min':
            # Get recent 1min data for normalization
            end_time = bar_data['timestamp']
            start_time = end_time - (24 * 60 * 60 * 1000)  # Last 24 hours
            
            df_1min = get_market_data(symbol, '1min', start_time, end_time)
            
            if not df_1min.empty and len(df_1min) >= 5:
                # Normalize to 5min
                df_5min = normalize_to_timeframe(df_1min, '5min', symbol)
                if not df_5min.empty:
                    # Store latest 5min bar
                    latest_5min = df_5min.iloc[-1]
                    store_market_data(
                        symbol=symbol,
                        timestamp=int(latest_5min['timestamp']),
                        timeframe='5min',
                        open_price=latest_5min['open'],
                        high=latest_5min['high'],
                        low=latest_5min['low'],
                        close=latest_5min['close'],
                        volume=int(latest_5min['volume']),
                        vwap=latest_5min.get('vwap'),
                        ema_20=latest_5min.get('ema_20'),
                        ema_200=latest_5min.get('ema_200')
                    )
            
            # For daily, we'd check if it's end of day
            # This is simplified - in production, you'd check market hours
            if not df_1min.empty:
                df_daily = normalize_to_timeframe(df_1min, 'daily', symbol)
                if not df_daily.empty:
                    latest_daily = df_daily.iloc[-1]
                    store_market_data(
                        symbol=symbol,
                        timestamp=int(latest_daily['timestamp']),
                        timeframe='daily',
                        open_price=latest_daily['open'],
                        high=latest_daily['high'],
                        low=latest_daily['low'],
                        close=latest_daily['close'],
                        volume=int(latest_daily['volume']),
                        vwap=latest_daily.get('vwap'),
                        ema_20=latest_daily.get('ema_20'),
                        ema_200=latest_daily.get('ema_200')
                    )
    
    except Exception as e:
        logger.error(f"Failed to process and store bar: {e}", exc_info=True)

