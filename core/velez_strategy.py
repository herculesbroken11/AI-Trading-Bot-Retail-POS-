"""
Oliver Vélez Trading Strategy Implementation
Implements the 4 Fantastics, 75% candle rule, RBI/GBI/Whale/Kamikaze setups
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from core.logger import logger

class SignalType(Enum):
    """Trading signal types"""
    RBI = "RBI"  # Rising Bottom Inside
    GBI = "GBI"  # Great Bottom Inside
    WHALE = "WHALE"  # Whale pattern
    KAMIKAZE = "KAMIKAZE"  # Kamikaze pattern
    FOUR_FANTASTICS = "FOUR_FANTASTICS"

@dataclass
class TradingSignal:
    """Trading signal data structure"""
    signal_type: SignalType
    symbol: str
    entry_price: float
    stop_loss: float
    target_price: float
    confidence: float
    timestamp: pd.Timestamp
    setup_quality: str
    risk_reward_ratio: float

class VelezStrategy:
    """Implementation of Oliver Vélez trading strategies"""
    
    def __init__(self):
        self.min_volume_threshold = 100000  # Minimum daily volume
        self.min_price_threshold = 5.0  # Minimum stock price
        self.max_price_threshold = 500.0  # Maximum stock price
    
    def analyze_four_fantastics(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """
        Analyze for the 4 Fantastics pattern:
        1. Higher high
        2. Higher low
        3. Higher close
        4. Higher open
        """
        try:
            if len(df) < 20:
                return None
            
            # Get the last 5 candles for analysis
            recent_candles = df.tail(5)
            
            # Check for higher high
            higher_high = recent_candles['high'].iloc[-1] > recent_candles['high'].iloc[-2]
            
            # Check for higher low
            higher_low = recent_candles['low'].iloc[-1] > recent_candles['low'].iloc[-2]
            
            # Check for higher close
            higher_close = recent_candles['close'].iloc[-1] > recent_candles['close'].iloc[-2]
            
            # Check for higher open
            higher_open = recent_candles['open'].iloc[-1] > recent_candles['open'].iloc[-2]
            
            # All 4 conditions must be met
            if higher_high and higher_low and higher_close and higher_open:
                current_candle = recent_candles.iloc[-1]
                entry_price = current_candle['close']
                stop_loss = current_candle['low']
                target_price = entry_price + (entry_price - stop_loss) * 2  # 1:2 risk/reward
                
                risk_reward = (target_price - entry_price) / (entry_price - stop_loss)
                
                signal = TradingSignal(
                    signal_type=SignalType.FOUR_FANTASTICS,
                    symbol="",  # Will be set by caller
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    confidence=0.85,
                    timestamp=current_candle.name,
                    setup_quality="HIGH",
                    risk_reward_ratio=risk_reward
                )
                
                logger.info("4 Fantastics pattern detected")
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing 4 Fantastics: {str(e)}")
            return None
    
    def analyze_75_percent_candle_rule(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """
        Analyze for the 75% candle rule:
        Current candle's body should be at least 75% of the total range
        """
        try:
            if len(df) < 2:
                return None
            
            current_candle = df.iloc[-1]
            previous_candle = df.iloc[-2]
            
            # Calculate candle body size
            current_body = abs(current_candle['close'] - current_candle['open'])
            current_range = current_candle['high'] - current_candle['low']
            
            if current_range == 0:
                return None
            
            body_percentage = (current_body / current_range) * 100
            
            # 75% rule: body should be at least 75% of total range
            if body_percentage >= 75:
                # Determine direction
                is_bullish = current_candle['close'] > current_candle['open']
                
                if is_bullish:
                    entry_price = current_candle['close']
                    stop_loss = current_candle['low']
                    target_price = entry_price + (entry_price - stop_loss) * 1.5
                    
                    risk_reward = (target_price - entry_price) / (entry_price - stop_loss)
                    
                    signal = TradingSignal(
                        signal_type=SignalType.RBI,  # Using RBI as base for bullish patterns
                        symbol="",
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_price=target_price,
                        confidence=0.80,
                        timestamp=current_candle.name,
                        setup_quality="HIGH",
                        risk_reward_ratio=risk_reward
                    )
                    
                    logger.info("75% candle rule pattern detected (bullish)")
                    return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing 75% candle rule: {str(e)}")
            return None
    
    def analyze_rbi_pattern(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """
        Analyze for RBI (Rising Bottom Inside) pattern:
        Current candle's low is higher than previous candle's low
        """
        try:
            if len(df) < 3:
                return None
            
            current_candle = df.iloc[-1]
            previous_candle = df.iloc[-2]
            two_ago_candle = df.iloc[-3]
            
            # Check for rising bottom
            rising_bottom = (current_candle['low'] > previous_candle['low'] > two_ago_candle['low'])
            
            # Check if current candle is inside the previous one
            inside_candle = (current_candle['high'] < previous_candle['high'] and 
                           current_candle['low'] > previous_candle['low'])
            
            if rising_bottom and inside_candle:
                entry_price = current_candle['close']
                stop_loss = current_candle['low']
                target_price = entry_price + (entry_price - stop_loss) * 2
                
                risk_reward = (target_price - entry_price) / (entry_price - stop_loss)
                
                signal = TradingSignal(
                    signal_type=SignalType.RBI,
                    symbol="",
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    confidence=0.75,
                    timestamp=current_candle.name,
                    setup_quality="MEDIUM",
                    risk_reward_ratio=risk_reward
                )
                
                logger.info("RBI pattern detected")
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing RBI pattern: {str(e)}")
            return None
    
    def analyze_gbi_pattern(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """
        Analyze for GBI (Great Bottom Inside) pattern:
        Similar to RBI but with stronger confirmation
        """
        try:
            if len(df) < 4:
                return None
            
            current_candle = df.iloc[-1]
            previous_candle = df.iloc[-2]
            two_ago_candle = df.iloc[-3]
            three_ago_candle = df.iloc[-4]
            
            # Check for great rising bottom (3 consecutive higher lows)
            great_rising_bottom = (current_candle['low'] > previous_candle['low'] > 
                                 two_ago_candle['low'] > three_ago_candle['low'])
            
            # Check for inside candle
            inside_candle = (current_candle['high'] < previous_candle['high'] and 
                           current_candle['low'] > previous_candle['low'])
            
            if great_rising_bottom and inside_candle:
                entry_price = current_candle['close']
                stop_loss = current_candle['low']
                target_price = entry_price + (entry_price - stop_loss) * 2.5
                
                risk_reward = (target_price - entry_price) / (entry_price - stop_loss)
                
                signal = TradingSignal(
                    signal_type=SignalType.GBI,
                    symbol="",
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    confidence=0.85,
                    timestamp=current_candle.name,
                    setup_quality="HIGH",
                    risk_reward_ratio=risk_reward
                )
                
                logger.info("GBI pattern detected")
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing GBI pattern: {str(e)}")
            return None
    
    def analyze_whale_pattern(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """
        Analyze for Whale pattern:
        Large volume spike with price breakout
        """
        try:
            if len(df) < 10:
                return None
            
            # Check if volume data is available
            if 'volume' not in df.columns:
                return None
            
            current_candle = df.iloc[-1]
            
            # Calculate average volume over last 10 periods
            avg_volume = df['volume'].tail(10).mean()
            current_volume = current_candle['volume']
            
            # Volume should be at least 2x average
            volume_spike = current_volume >= (avg_volume * 2)
            
            # Price should break above recent high
            recent_high = df['high'].tail(10).max()
            price_breakout = current_candle['close'] > recent_high
            
            if volume_spike and price_breakout:
                entry_price = current_candle['close']
                stop_loss = current_candle['low']
                target_price = entry_price + (entry_price - stop_loss) * 3
                
                risk_reward = (target_price - entry_price) / (entry_price - stop_loss)
                
                signal = TradingSignal(
                    signal_type=SignalType.WHALE,
                    symbol="",
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    confidence=0.90,
                    timestamp=current_candle.name,
                    setup_quality="HIGH",
                    risk_reward_ratio=risk_reward
                )
                
                logger.info("Whale pattern detected")
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing Whale pattern: {str(e)}")
            return None
    
    def analyze_kamikaze_pattern(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """
        Analyze for Kamikaze pattern:
        Sharp reversal pattern after significant move
        """
        try:
            if len(df) < 5:
                return None
            
            current_candle = df.iloc[-1]
            previous_candle = df.iloc[-2]
            
            # Check for sharp reversal (close above open after previous close below open)
            sharp_reversal = (current_candle['close'] > current_candle['open'] and 
                            previous_candle['close'] < previous_candle['open'])
            
            # Check for significant price movement
            price_range = current_candle['high'] - current_candle['low']
            significant_move = price_range > (df['close'].tail(10).std() * 2)
            
            if sharp_reversal and significant_move:
                entry_price = current_candle['close']
                stop_loss = current_candle['low']
                target_price = entry_price + (entry_price - stop_loss) * 2
                
                risk_reward = (target_price - entry_price) / (entry_price - stop_loss)
                
                signal = TradingSignal(
                    signal_type=SignalType.KAMIKAZE,
                    symbol="",
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    confidence=0.70,
                    timestamp=current_candle.name,
                    setup_quality="MEDIUM",
                    risk_reward_ratio=risk_reward
                )
                
                logger.info("Kamikaze pattern detected")
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing Kamikaze pattern: {str(e)}")
            return None
    
    def analyze_all_patterns(self, df: pd.DataFrame, symbol: str) -> List[TradingSignal]:
        """
        Analyze all patterns and return list of signals
        """
        signals = []
        
        try:
            # Analyze each pattern
            patterns = [
                self.analyze_four_fantastics,
                self.analyze_75_percent_candle_rule,
                self.analyze_rbi_pattern,
                self.analyze_gbi_pattern,
                self.analyze_whale_pattern,
                self.analyze_kamikaze_pattern
            ]
            
            for pattern_func in patterns:
                signal = pattern_func(df)
                if signal:
                    signal.symbol = symbol
                    signals.append(signal)
            
            # Sort by confidence and quality
            signals.sort(key=lambda x: (x.confidence, x.risk_reward_ratio), reverse=True)
            
            logger.info(f"Found {len(signals)} trading signals for {symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error analyzing patterns for {symbol}: {str(e)}")
            return []
    
    def validate_signal(self, signal: TradingSignal, df: pd.DataFrame) -> bool:
        """
        Validate a trading signal against additional criteria
        """
        try:
            # Check if stock meets minimum criteria
            if len(df) < 20:
                return False
            
            # Check price range
            current_price = signal.entry_price
            if current_price < self.min_price_threshold or current_price > self.max_price_threshold:
                return False
            
            # Check volume if available
            if 'volume' in df.columns:
                avg_volume = df['volume'].tail(20).mean()
                if avg_volume < self.min_volume_threshold:
                    return False
            
            # Check risk/reward ratio
            if signal.risk_reward_ratio < 1.5:
                return False
            
            # Check if stop loss is reasonable (not more than 10% of entry price)
            stop_loss_percentage = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
            if stop_loss_percentage > 0.10:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating signal: {str(e)}")
            return False
