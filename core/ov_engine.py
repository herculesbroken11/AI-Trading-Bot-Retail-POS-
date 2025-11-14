"""
Oliver Vélez Trading Strategy Engine
Implements the core trading logic and technical indicators.
"""
import pandas as pd
import numpy as np
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from typing import Dict, Any, Optional, List
from utils.logger import setup_logger

logger = setup_logger("ov_engine")

class OVStrategyEngine:
    """
    Oliver Vélez Trading Strategy Engine
    
    Key Rules:
    - SMA8, SMA20, SMA200 for trend identification
    - ATR14 for volatility and stop placement
    - Volume analysis for confirmation
    - Intraday setups: pullbacks, breakouts, reversals
    """
    
    def __init__(self):
        self.sma_periods = [8, 20, 200]
        self.atr_period = 14
        self.rsi_period = 14
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators for the strategy.
        
        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            
        Returns:
            DataFrame with added indicator columns
        """
        if df.empty or len(df) < max(self.sma_periods):
            logger.warning("Insufficient data for indicator calculation")
            return df
        
        # Ensure we have the required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        df = df.copy()
        
        # Calculate SMAs
        for period in self.sma_periods:
            sma = SMAIndicator(close=df['close'], window=period)
            df[f'sma_{period}'] = sma.sma_indicator()
        
        # Calculate ATR
        atr = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=self.atr_period
        )
        df['atr_14'] = atr.average_true_range()
        
        # Calculate RSI
        rsi = RSIIndicator(close=df['close'], window=self.rsi_period)
        df['rsi_14'] = rsi.rsi()
        
        # Calculate volume moving average
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        
        # Price position relative to SMAs
        df['above_sma8'] = df['close'] > df['sma_8']
        df['above_sma20'] = df['close'] > df['sma_20']
        df['above_sma200'] = df['close'] > df['sma_200']
        
        # SMA alignment (bullish: 8 > 20 > 200)
        df['sma_aligned_bullish'] = (
            (df['sma_8'] > df['sma_20']) & 
            (df['sma_20'] > df['sma_200'])
        )
        
        # SMA alignment (bearish: 8 < 20 < 200)
        df['sma_aligned_bearish'] = (
            (df['sma_8'] < df['sma_20']) & 
            (df['sma_20'] < df['sma_200'])
        )
        
        return df
    
    def identify_setup(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Identify Oliver Vélez trading setups from the data.
        
        Args:
            df: DataFrame with indicators calculated
            
        Returns:
            Dictionary with setup information or None
        """
        if df.empty or len(df) < 2:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        setup = {
            "type": None,
            "direction": None,
            "strength": 0,
            "entry_price": float(latest['close']),
            "stop_loss": None,
            "take_profit": None,
            "confidence": 0.0
        }
        
        # Bullish Setup: Pullback to SMA8 or SMA20
        if (latest['above_sma200'] and 
            latest['sma_aligned_bullish'] and
            latest['rsi_14'] < 70 and
            latest['close'] <= latest['sma_20'] and
            latest['close'] >= latest['sma_8']):
            
            setup["type"] = "PULLBACK_LONG"
            setup["direction"] = "LONG"
            setup["entry_price"] = float(latest['close'])
            setup["stop_loss"] = float(latest['sma_20'] - (latest['atr_14'] * 1.5))
            setup["take_profit"] = float(latest['close'] + (latest['atr_14'] * 2))
            setup["confidence"] = 0.7
            setup["strength"] = 1
            
        # Bullish Setup: Breakout above SMA8
        elif (latest['above_sma200'] and
              latest['sma_aligned_bullish'] and
              prev['close'] <= prev['sma_8'] and
              latest['close'] > latest['sma_8'] and
              latest['volume'] > latest['volume_ma'] * 1.5):
            
            setup["type"] = "BREAKOUT_LONG"
            setup["direction"] = "LONG"
            setup["entry_price"] = float(latest['close'])
            setup["stop_loss"] = float(latest['sma_8'] - (latest['atr_14'] * 1))
            setup["take_profit"] = float(latest['close'] + (latest['atr_14'] * 2.5))
            setup["confidence"] = 0.75
            setup["strength"] = 2
            
        # Bearish Setup: Pullback to SMA8 or SMA20 (short)
        elif (not latest['above_sma200'] and
              latest['sma_aligned_bearish'] and
              latest['rsi_14'] > 30 and
              latest['close'] >= latest['sma_20'] and
              latest['close'] <= latest['sma_8']):
            
            setup["type"] = "PULLBACK_SHORT"
            setup["direction"] = "SHORT"
            setup["entry_price"] = float(latest['close'])
            setup["stop_loss"] = float(latest['sma_20'] + (latest['atr_14'] * 1.5))
            setup["take_profit"] = float(latest['close'] - (latest['atr_14'] * 2))
            setup["confidence"] = 0.7
            setup["strength"] = 1
            
        # Bearish Setup: Breakdown below SMA8
        elif (not latest['above_sma200'] and
              latest['sma_aligned_bearish'] and
              prev['close'] >= prev['sma_8'] and
              latest['close'] < latest['sma_8'] and
              latest['volume'] > latest['volume_ma'] * 1.5):
            
            setup["type"] = "BREAKDOWN_SHORT"
            setup["direction"] = "SHORT"
            setup["entry_price"] = float(latest['close'])
            setup["stop_loss"] = float(latest['sma_8'] + (latest['atr_14'] * 1))
            setup["take_profit"] = float(latest['close'] - (latest['atr_14'] * 2.5))
            setup["confidence"] = 0.75
            setup["strength"] = 2
        
        if setup["type"]:
            return setup
        
        return None
    
    def get_market_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate a market summary for AI analysis.
        
        Args:
            df: DataFrame with indicators
            
        Returns:
            Dictionary with market summary
        """
        if df.empty:
            return {}
        
        latest = df.iloc[-1]
        
        summary = {
            "current_price": float(latest['close']),
            "sma_8": float(latest['sma_8']) if not pd.isna(latest['sma_8']) else None,
            "sma_20": float(latest['sma_20']) if not pd.isna(latest['sma_20']) else None,
            "sma_200": float(latest['sma_200']) if not pd.isna(latest['sma_200']) else None,
            "atr_14": float(latest['atr_14']) if not pd.isna(latest['atr_14']) else None,
            "rsi_14": float(latest['rsi_14']) if not pd.isna(latest['rsi_14']) else None,
            "volume": int(latest['volume']),
            "volume_ma": float(latest['volume_ma']) if not pd.isna(latest['volume_ma']) else None,
            "trend": "BULLISH" if latest['sma_aligned_bullish'] else "BEARISH" if latest['sma_aligned_bearish'] else "NEUTRAL",
            "above_sma200": bool(latest['above_sma200']),
            "price_change_pct": float(((latest['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close']) * 100) if len(df) > 1 else 0.0
        }
        
        return summary

