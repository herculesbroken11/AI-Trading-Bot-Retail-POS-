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
    
    def check_75_percent_candle_rule(self, df: pd.DataFrame, index: int = -1) -> bool:
        """
        Check if candle meets 75% rule: body must be at least 75% of total range.
        
        Args:
            df: DataFrame with OHLC data
            index: Index of candle to check (default: -1 for latest)
            
        Returns:
            True if candle meets 75% rule
        """
        if df.empty or abs(index) > len(df):
            return False
        
        candle = df.iloc[index]
        total_range = candle['high'] - candle['low']
        body_size = abs(candle['close'] - candle['open'])
        
        if total_range == 0:
            return False
        
        body_percentage = (body_size / total_range) * 100
        return body_percentage >= 75.0
    
    def check_4_fantastics(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Check the 4 Fantastics conditions for OV strategy.
        
        1. Trend alignment (SMA8 > SMA20 > SMA200 for bullish, reverse for bearish)
        2. Price above/below SMA200
        3. Volume confirmation (above average)
        4. RSI in favorable zone (not overbought/oversold)
        
        Args:
            df: DataFrame with indicators
            
        Returns:
            Dictionary with each fantastic condition status
        """
        if df.empty:
            return {"fantastic_1": False, "fantastic_2": False, "fantastic_3": False, "fantastic_4": False}
        
        latest = df.iloc[-1]
        
        # Fantastic 1: Trend Alignment
        fantastic_1 = (
            (latest['sma_aligned_bullish'] and latest['above_sma200']) or
            (latest['sma_aligned_bearish'] and not latest['above_sma200'])
        )
        
        # Fantastic 2: Price position relative to SMA200
        fantastic_2 = (
            (latest['above_sma200'] and latest['sma_aligned_bullish']) or
            (not latest['above_sma200'] and latest['sma_aligned_bearish'])
        )
        
        # Fantastic 3: Volume confirmation
        fantastic_3 = latest['volume'] > latest['volume_ma'] * 1.2
        
        # Fantastic 4: RSI in favorable zone
        rsi = latest['rsi_14']
        if latest['above_sma200']:
            fantastic_4 = 30 < rsi < 70  # Not overbought for longs
        else:
            fantastic_4 = 30 < rsi < 70  # Not oversold for shorts
        
        return {
            "fantastic_1": bool(fantastic_1),
            "fantastic_2": bool(fantastic_2),
            "fantastic_3": bool(fantastic_3),
            "fantastic_4": bool(fantastic_4),
            "all_fantastics": bool(fantastic_1 and fantastic_2 and fantastic_3 and fantastic_4)
        }
    
    def identify_whale_setup(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Whale Setup: Large volume spike with price movement above SMA8.
        Typically occurs when institutional money enters.
        
        Args:
            df: DataFrame with indicators
            
        Returns:
            Setup dictionary or None
        """
        if df.empty or len(df) < 3:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Whale conditions: massive volume spike (3x+) with price above SMA8
        volume_spike = latest['volume'] > latest['volume_ma'] * 3.0
        price_above_sma8 = latest['close'] > latest['sma_8']
        bullish_trend = latest['above_sma200'] and latest['sma_aligned_bullish']
        price_moved_up = latest['close'] > prev['close']
        
        if volume_spike and price_above_sma8 and bullish_trend and price_moved_up:
            return {
                "type": "WHALE_LONG",
                "direction": "LONG",
                "entry_price": float(latest['close']),
                "stop_loss": float(latest['sma_8'] - (latest['atr_14'] * 1.2)),
                "take_profit": float(latest['close'] + (latest['atr_14'] * 3)),
                "confidence": 0.85,
                "strength": 3
            }
        
        return None
    
    def identify_kamikaze_setup(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Kamikaze Setup: Rapid price reversal after a strong move.
        High risk, high reward setup.
        
        Args:
            df: DataFrame with indicators
            
        Returns:
            Setup dictionary or None
        """
        if df.empty or len(df) < 5:
            return None
        
        latest = df.iloc[-1]
        
        # Look for rapid reversal pattern
        # Price was moving in one direction, then reverses sharply
        recent_candles = df.iloc[-5:]
        
        # Check for bullish kamikaze (dip then sharp reversal up)
        if latest['above_sma200'] and latest['sma_aligned_bullish']:
            # Price dipped below SMA8 but closed above it
            dipped = any(candle['low'] < candle['sma_8'] for _, candle in recent_candles.iterrows())
            recovered = latest['close'] > latest['sma_8']
            volume_confirmed = latest['volume'] > latest['volume_ma'] * 1.5
            
            if dipped and recovered and volume_confirmed:
                return {
                    "type": "KAMIKAZE_LONG",
                    "direction": "LONG",
                    "entry_price": float(latest['close']),
                    "stop_loss": float(latest['sma_8'] - (latest['atr_14'] * 1.5)),
                    "take_profit": float(latest['close'] + (latest['atr_14'] * 2.5)),
                    "confidence": 0.70,
                    "strength": 2
                }
        
        # Check for bearish kamikaze
        if not latest['above_sma200'] and latest['sma_aligned_bearish']:
            # Price spiked above SMA8 but closed below it
            spiked = any(candle['high'] > candle['sma_8'] for _, candle in recent_candles.iterrows())
            rejected = latest['close'] < latest['sma_8']
            volume_confirmed = latest['volume'] > latest['volume_ma'] * 1.5
            
            if spiked and rejected and volume_confirmed:
                return {
                    "type": "KAMIKAZE_SHORT",
                    "direction": "SHORT",
                    "entry_price": float(latest['close']),
                    "stop_loss": float(latest['sma_8'] + (latest['atr_14'] * 1.5)),
                    "take_profit": float(latest['close'] - (latest['atr_14'] * 2.5)),
                    "confidence": 0.70,
                    "strength": 2
                }
        
        return None
    
    def identify_rbi_setup(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        RBI (Rapid Breakout Indicator): Fast price breakout with volume.
        Quick momentum play.
        
        Args:
            df: DataFrame with indicators
            
        Returns:
            Setup dictionary or None
        """
        if df.empty or len(df) < 3:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # RBI: Rapid breakout above resistance (SMA8 or SMA20)
        if latest['above_sma200'] and latest['sma_aligned_bullish']:
            # Price breaks above SMA8 rapidly
            rapid_breakout = (
                prev['close'] <= prev['sma_8'] and
                latest['close'] > latest['sma_8'] and
                (latest['close'] - prev['close']) > (latest['atr_14'] * 0.5)  # Fast move
            )
            volume_surge = latest['volume'] > latest['volume_ma'] * 2.0
            
            if rapid_breakout and volume_surge:
                return {
                    "type": "RBI_LONG",
                    "direction": "LONG",
                    "entry_price": float(latest['close']),
                    "stop_loss": float(latest['sma_8'] - (latest['atr_14'] * 0.8)),
                    "take_profit": float(latest['close'] + (latest['atr_14'] * 2.5)),
                    "confidence": 0.80,
                    "strength": 3
                }
        
        # Bearish RBI
        if not latest['above_sma200'] and latest['sma_aligned_bearish']:
            rapid_breakdown = (
                prev['close'] >= prev['sma_8'] and
                latest['close'] < latest['sma_8'] and
                (prev['close'] - latest['close']) > (latest['atr_14'] * 0.5)
            )
            volume_surge = latest['volume'] > latest['volume_ma'] * 2.0
            
            if rapid_breakdown and volume_surge:
                return {
                    "type": "RBI_SHORT",
                    "direction": "SHORT",
                    "entry_price": float(latest['close']),
                    "stop_loss": float(latest['sma_8'] + (latest['atr_14'] * 0.8)),
                    "take_profit": float(latest['close'] - (latest['atr_14'] * 2.5)),
                    "confidence": 0.80,
                    "strength": 3
                }
        
        return None
    
    def identify_gbi_setup(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        GBI (Gap Breakout Indicator): Gap up/down with continuation.
        Gap must hold and continue in gap direction.
        
        Args:
            df: DataFrame with indicators
            
        Returns:
            Setup dictionary or None
        """
        if df.empty or len(df) < 2:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Calculate gap (difference between previous close and current open)
        gap_size = abs(latest['open'] - prev['close'])
        gap_percentage = (gap_size / prev['close']) * 100 if prev['close'] > 0 else 0
        
        # GBI requires significant gap (>0.5% of price)
        if gap_percentage < 0.5:
            return None
        
        # Bullish GBI: Gap up and continues up
        if latest['above_sma200'] and latest['sma_aligned_bullish']:
            gap_up = latest['open'] > prev['close']
            continues_up = latest['close'] > latest['open']  # Closes above open
            volume_confirmed = latest['volume'] > latest['volume_ma'] * 1.5
            
            if gap_up and continues_up and volume_confirmed:
                return {
                    "type": "GBI_LONG",
                    "direction": "LONG",
                    "entry_price": float(latest['close']),
                    "stop_loss": float(latest['open'] - (latest['atr_14'] * 1.0)),  # Below gap
                    "take_profit": float(latest['close'] + (latest['atr_14'] * 3)),
                    "confidence": 0.75,
                    "strength": 3
                }
        
        # Bearish GBI: Gap down and continues down
        if not latest['above_sma200'] and latest['sma_aligned_bearish']:
            gap_down = latest['open'] < prev['close']
            continues_down = latest['close'] < latest['open']  # Closes below open
            volume_confirmed = latest['volume'] > latest['volume_ma'] * 1.5
            
            if gap_down and continues_down and volume_confirmed:
                return {
                    "type": "GBI_SHORT",
                    "direction": "SHORT",
                    "entry_price": float(latest['close']),
                    "stop_loss": float(latest['open'] + (latest['atr_14'] * 1.0)),  # Above gap
                    "take_profit": float(latest['close'] - (latest['atr_14'] * 3)),
                    "confidence": 0.75,
                    "strength": 3
                }
        
        return None
    
    def identify_setup(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Identify Oliver Vélez trading setups from the data.
        Now includes all advanced setups: Whale, Kamikaze, RBI, GBI.
        
        Args:
            df: DataFrame with indicators calculated
            
        Returns:
            Dictionary with setup information or None
        """
        if df.empty or len(df) < 2:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # Check 4 Fantastics first
        fantastics = self.check_4_fantastics(df)
        
        # Check advanced setups first (higher priority)
        # 1. GBI (Gap Breakout)
        gbi_setup = self.identify_gbi_setup(df)
        if gbi_setup:
            gbi_setup["fantastics"] = fantastics
            gbi_setup["meets_75_percent_rule"] = self.check_75_percent_candle_rule(df)
            return gbi_setup
        
        # 2. Whale Setup
        whale_setup = self.identify_whale_setup(df)
        if whale_setup:
            whale_setup["fantastics"] = fantastics
            whale_setup["meets_75_percent_rule"] = self.check_75_percent_candle_rule(df)
            return whale_setup
        
        # 3. RBI (Rapid Breakout)
        rbi_setup = self.identify_rbi_setup(df)
        if rbi_setup:
            rbi_setup["fantastics"] = fantastics
            rbi_setup["meets_75_percent_rule"] = self.check_75_percent_candle_rule(df)
            return rbi_setup
        
        # 4. Kamikaze Setup
        kamikaze_setup = self.identify_kamikaze_setup(df)
        if kamikaze_setup:
            kamikaze_setup["fantastics"] = fantastics
            kamikaze_setup["meets_75_percent_rule"] = self.check_75_percent_candle_rule(df)
            return kamikaze_setup
        
        # 5. Basic setups (Pullback/Breakout)
        setup = {
            "type": None,
            "direction": None,
            "strength": 0,
            "entry_price": float(latest['close']),
            "stop_loss": None,
            "take_profit": None,
            "confidence": 0.0,
            "fantastics": fantastics,
            "meets_75_percent_rule": self.check_75_percent_candle_rule(df)
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
            setup["confidence"] = 0.7 if fantastics["all_fantastics"] else 0.5
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
            setup["confidence"] = 0.75 if fantastics["all_fantastics"] else 0.6
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
            setup["confidence"] = 0.7 if fantastics["all_fantastics"] else 0.5
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
            setup["confidence"] = 0.75 if fantastics["all_fantastics"] else 0.6
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

