"""
GPT-5 AI Signal Analyzer
Validates trading signals using OpenAI's GPT models
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
from core.config import config
from core.logger import logger
from core.velez_strategy import TradingSignal, SignalType

class AIAnalyzer:
    """AI-powered signal validation using OpenAI GPT models"""
    
    def __init__(self):
        self.api_key = config.OPENAI_API_KEY
        self.model = config.OPENAI_MODEL
        self.base_url = "https://api.openai.com/v1"
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _create_analysis_prompt(self, signal: TradingSignal, market_data: pd.DataFrame) -> str:
        """
        Create a detailed prompt for AI analysis
        """
        prompt = f"""
        You are an expert day trader specializing in Oliver Vélez's trading strategies. 
        Analyze the following trading signal and provide a comprehensive assessment.
        
        TRADING SIGNAL DETAILS:
        - Symbol: {signal.symbol}
        - Signal Type: {signal.signal_type.value}
        - Entry Price: ${signal.entry_price:.2f}
        - Stop Loss: ${signal.stop_loss:.2f}
        - Target Price: ${signal.target_price:.2f}
        - Risk/Reward Ratio: {signal.risk_reward_ratio:.2f}
        - Confidence: {signal.confidence:.2f}
        - Setup Quality: {signal.setup_quality}
        - Timestamp: {signal.timestamp}
        
        RECENT MARKET DATA (Last 10 candles):
        """
        
        # Add recent market data
        recent_data = market_data.tail(10)
        for idx, row in recent_data.iterrows():
            prompt += f"\n{idx}: Open=${row['open']:.2f}, High=${row['high']:.2f}, Low=${row['low']:.2f}, Close=${row['close']:.2f}"
            if 'volume' in row:
                prompt += f", Volume={row['volume']:,}"
        
        prompt += f"""
        
        ANALYSIS REQUIREMENTS:
        1. Validate the signal against Oliver Vélez's trading rules
        2. Assess market context and trend strength
        3. Evaluate risk management parameters
        4. Check for any conflicting signals or market conditions
        5. Provide a confidence score (0-100)
        6. Recommend action: BUY, SELL, or HOLD
        
        RESPONSE FORMAT (JSON):
        {{
            "validation_result": "VALID" | "INVALID" | "NEEDS_REVIEW",
            "confidence_score": 0-100,
            "recommendation": "BUY" | "SELL" | "HOLD",
            "reasoning": "Detailed explanation of the analysis",
            "risk_assessment": "LOW" | "MEDIUM" | "HIGH",
            "market_context": "Description of current market conditions",
            "strengths": ["List of positive factors"],
            "weaknesses": ["List of negative factors"],
            "alternative_actions": ["List of alternative trading strategies if applicable"]
        }}
        
        Provide a thorough analysis focusing on:
        - Pattern recognition accuracy
        - Market timing
        - Risk management
        - Overall trade setup quality
        """
        
        return prompt
    
    async def analyze_signal(self, signal: TradingSignal, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze a trading signal using AI
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            prompt = self._create_analysis_prompt(signal, market_data)
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': self.model,
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are an expert day trader with deep knowledge of Oliver Vélez\'s trading strategies. Provide accurate, data-driven analysis.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.3,
                'max_tokens': 1000
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    
                    # Try to parse JSON response
                    try:
                        analysis = json.loads(content)
                        analysis['timestamp'] = datetime.now().isoformat()
                        analysis['original_signal'] = {
                            'symbol': signal.symbol,
                            'signal_type': signal.signal_type.value,
                            'entry_price': signal.entry_price,
                            'stop_loss': signal.stop_loss,
                            'target_price': signal.target_price
                        }
                        
                        logger.info(f"AI analysis completed for {signal.symbol}")
                        return analysis
                        
                    except json.JSONDecodeError:
                        # If JSON parsing fails, create a structured response
                        logger.warning("Failed to parse AI response as JSON, creating structured response")
                        return {
                            'validation_result': 'NEEDS_REVIEW',
                            'confidence_score': 50,
                            'recommendation': 'HOLD',
                            'reasoning': content,
                            'risk_assessment': 'MEDIUM',
                            'market_context': 'Unable to parse AI response',
                            'strengths': [],
                            'weaknesses': ['AI response parsing failed'],
                            'alternative_actions': [],
                            'timestamp': datetime.now().isoformat(),
                            'original_signal': {
                                'symbol': signal.symbol,
                                'signal_type': signal.signal_type.value,
                                'entry_price': signal.entry_price,
                                'stop_loss': signal.stop_loss,
                                'target_price': signal.target_price
                            }
                        }
                else:
                    error_text = await response.text()
                    logger.error(f"AI analysis failed: {response.status} - {error_text}")
                    return self._create_error_response(signal, f"API Error: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error in AI analysis: {str(e)}")
            return self._create_error_response(signal, str(e))
    
    def _create_error_response(self, signal: TradingSignal, error_message: str) -> Dict[str, Any]:
        """Create an error response when AI analysis fails"""
        return {
            'validation_result': 'INVALID',
            'future_score': 0,
            'recommendation': 'HOLD',
            'reasoning': f'AI analysis failed: {error_message}',
            'risk_assessment': 'HIGH',
            'market_context': 'Unable to analyze due to technical error',
            'strengths': [],
            'weaknesses': [f'AI analysis error: {error_message}'],
            'alternative_actions': [],
            'timestamp': datetime.now().isoformat(),
            'original_signal': {
                'symbol': signal.symbol,
                'signal_type': signal.signal_type.value,
                'entry_price': signal.entry_price,
                'stop_loss': signal.stop_loss,
                'target_price': signal.target_price
            }
        }
    
    async def batch_analyze_signals(self, signals: List[TradingSignal], 
                                  market_data_dict: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Analyze multiple signals in batch
        """
        try:
            tasks = []
            for signal in signals:
                if signal.symbol in market_data_dict:
                    task = self.analyze_signal(signal, market_data_dict[signal.symbol])
                    tasks.append(task)
                else:
                    logger.warning(f"No market data available for {signal.symbol}")
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and log them
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Batch analysis error for signal {i}: {str(result)}")
                else:
                    valid_results.append(result)
            
            logger.info(f"Batch analysis completed: {len(valid_results)}/{len(signals)} signals analyzed")
            return valid_results
            
        except Exception as e:
            logger.error(f"Error in batch analysis: {str(e)}")
            return []
    
    def create_market_summary(self, analysis_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a summary of AI analysis results
        """
        try:
            if not analysis_results:
                return {
                    'total_signals': 0,
                    'valid_signals': 0,
                    'buy_recommendations': 0,
                    'average_confidence': 0,
                    'high_confidence_signals': 0,
                    'summary': 'No signals analyzed'
                }
            
            total_signals = len(analysis_results)
            valid_signals = len([r for r in analysis_results if r['validation_result'] == 'VALID'])
            buy_recommendations = len([r for r in analysis_results if r['recommendation'] == 'BUY'])
            
            confidence_scores = [r['confidence_score'] for r in analysis_results if isinstance(r['confidence_score'], (int, float))]
            average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            high_confidence_signals = len([r for r in analysis_results if r['confidence_score'] >= 80])
            
            summary = {
                'total_signals': total_signals,
                'valid_signals': valid_signals,
                'buy_recommendations': buy_recommendations,
                'average_confidence': round(average_confidence, 2),
                'high_confidence_signals': high_confidence_signals,
                'summary': f'Analyzed {total_signals} signals, {valid_signals} valid, {buy_recommendations} buy recommendations'
            }
            
            logger.info(f"Market summary created: {summary['summary']}")
            return summary
            
        except Exception as e:
            logger.error(f"Error creating market summary: {str(e)}")
            return {
                'total_signals': 0,
                'valid_signals': 0,
                'buy_recommendations': 0,
                'average_confidence': 0,
                'high_confidence_signals': 0,
                'summary': f'Error creating summary: {str(e)}'
            }
