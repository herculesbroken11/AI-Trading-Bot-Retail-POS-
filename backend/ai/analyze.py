"""
GPT-5 AI Analysis Module for Oliver Vélez Trading System.
"""
import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from utils.logger import setup_logger
from dotenv import load_dotenv

load_dotenv()

logger = setup_logger("ai_analyze")

class TradingAIAnalyzer:
    """
    AI-powered trading signal analyzer using GPT-5.
    """
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        # Initialize OpenAI client
        # Note: OpenAI library v1.3.0 may have issues with proxy env vars
        # We explicitly only pass api_key to avoid any argument conflicts
        try:
            # Create client with only api_key parameter
            client_kwargs = {"api_key": api_key}
            self.client = OpenAI(**client_kwargs)
        except TypeError as e:
            # If there's a TypeError about unexpected arguments, log and re-raise
            # This helps identify if there are environment variables causing issues
            logger.error(f"Failed to initialize OpenAI client: {e}")
            logger.error("This may be caused by proxy environment variables or OpenAI library version mismatch")
            raise ValueError(f"OpenAI client initialization failed: {e}. Please check OPENAI_API_KEY and library version.")
        
        self.model = "gpt-4o"  # Using GPT-4o as GPT-5 is not yet available
    
    def analyze_market_data(
        self,
        symbol: str,
        market_summary: Dict[str, Any],
        setup: Optional[Dict[str, Any]] = None,
        chart_image: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze market data using GPT-4o with vision and generate trading signal.
        
        Args:
            symbol: Stock symbol
            market_summary: Market summary from OV engine
            setup: Optional identified setup from strategy engine
            chart_image: Optional base64-encoded chart image for vision analysis
            
        Returns:
            Trading signal dictionary
        """
        try:
            # Build prompt based on Oliver Vélez rules
            prompt = self._build_analysis_prompt(symbol, market_summary, setup)
            
            # Prepare messages
            messages = [
                {
                    "role": "system",
                    "content": self._get_system_prompt()
                }
            ]
            
            # Add chart image if provided (for vision analysis)
            if chart_image:
                user_content = [
                    {
                        "type": "text",
                        "text": prompt + "\n\nIMPORTANT: Analyze the provided chart image carefully. Look for:\n"
                                "- Visual confirmation of trend (price position relative to SMAs)\n"
                                "- Candlestick patterns (engulfing, doji, hammers, etc.)\n"
                                "- Volume spikes visible in the chart\n"
                                "- Support/resistance levels\n"
                                "- Visual setup patterns (pullbacks, breakouts, reversals)\n"
                                "- 75% candle rule compliance (visual inspection)\n"
                                "The chart shows candlesticks with SMA8 (blue), SMA20 (orange), SMA200 (purple), and volume bars.\n"
                                "Use both the numerical data AND the visual chart to make your decision."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{chart_image}"
                        }
                    }
                ]
                messages.append({
                    "role": "user",
                    "content": user_content
                })
            else:
                messages.append({
                    "role": "user",
                    "content": prompt
                })
            
            # Call OpenAI API with vision support
            response = self.client.chat.completions.create(
                model="gpt-4o",  # GPT-4o supports vision
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent analysis
                response_format={"type": "json_object"}
            )
            
            # Parse response
            content = response.choices[0].message.content
            signal = json.loads(content)
            
            analysis_type = "with chart vision" if chart_image else "text-only"
            logger.info(f"AI analysis completed for {symbol} ({analysis_type}): {signal.get('action', 'NONE')}")
            
            return signal
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            raise
    
    def _get_system_prompt(self) -> str:
        """Get system prompt with Oliver Vélez trading rules."""
        return """You are an expert trading analyst specializing in the Oliver Vélez intraday trading methodology.

When analyzing charts with images:
- Carefully examine the candlestick patterns visually
- Verify SMA alignment visually (SMA8 above/below SMA20, price relative to SMA200)
- Check volume bars for confirmation spikes
- Look for visual patterns: pullbacks, breakouts, reversals, gaps
- Verify 75% candle rule by visual inspection of candle bodies
- Identify support/resistance levels from the chart
- Use BOTH numerical data AND visual chart patterns for decision-making

Key Rules:
1. Trend Identification:
   - Use SMA8, SMA20, SMA200 to identify trend direction
   - Bullish: Price above SMA200, SMA8 > SMA20 > SMA200
   - Bearish: Price below SMA200, SMA8 < SMA20 < SMA200

2. Entry Setups:
   - Pullback Long: Price pulls back to SMA8 or SMA20 in uptrend, RSI < 70
   - Breakout Long: Price breaks above SMA8 with volume confirmation
   - Pullback Short: Price pulls back to SMA8 or SMA20 in downtrend, RSI > 30
   - Breakdown Short: Price breaks below SMA8 with volume confirmation

3. Risk Management:
   - Stop Loss: Use ATR14 * 1.5 for pullbacks, ATR14 * 1.0 for breakouts
   - Take Profit: Use ATR14 * 2.0-2.5
   - Maximum risk: $300 per trade
   - Position size based on risk per share

4. Volume Confirmation:
   - Breakouts/breakdowns require volume > 1.5x average volume
   - Low volume = weak signal

5. Time Management:
   - Close all positions by 4:00 PM ET
   - Avoid new entries after 3:30 PM ET

Analyze the provided market data and return a JSON signal with:
{
    "action": "BUY" | "SELL" | "HOLD" | "SHORT",
    "entry": float,
    "stop": float,
    "target": float,
    "setup_type": string,
    "position_size": int,
    "confidence": float (0-1),
    "reasoning": string
}

If no valid setup exists, return action: "HOLD" with reasoning."""
    
    def _build_analysis_prompt(
        self,
        symbol: str,
        market_summary: Dict[str, Any],
        setup: Optional[Dict[str, Any]]
    ) -> str:
        """Build analysis prompt from market data."""
        prompt = f"""Analyze the following market data for {symbol}:

Current Price: ${market_summary.get('current_price', 0):.2f}
SMA8: ${market_summary.get('sma_8', 0):.2f}
SMA20: ${market_summary.get('sma_20', 0):.2f}
SMA200: ${market_summary.get('sma_200', 0):.2f}
ATR14: ${market_summary.get('atr_14', 0):.2f}
RSI14: {market_summary.get('rsi_14', 0):.2f}
Volume: {market_summary.get('volume', 0):,}
Volume MA: {market_summary.get('volume_ma', 0):,.0f}
Trend: {market_summary.get('trend', 'UNKNOWN')}
Above SMA200: {market_summary.get('above_sma200', False)}
Price Change: {market_summary.get('price_change_pct', 0):.2f}%
"""
        
        if setup:
            prompt += f"""
Identified Setup:
Type: {setup.get('type', 'NONE')}
Direction: {setup.get('direction', 'NONE')}
Entry: ${setup.get('entry_price', 0):.2f}
Stop: ${setup.get('stop_loss', 0):.2f}
Target: ${setup.get('take_profit', 0):.2f}
Confidence: {setup.get('confidence', 0):.2f}
"""
        else:
            prompt += "\nNo setup identified by strategy engine.\n"
        
        prompt += """
Apply Oliver Vélez trading rules and provide a trading signal.
Consider:
- Is the trend clear and aligned?
- Is there a valid entry setup?
- Is volume confirming the move?
- Is risk/reward favorable (minimum 1:1.5)?
- Is there enough time in the trading day?

Return your analysis as JSON."""
        
        return prompt
    
    def generate_daily_report(self, trades: list, account_value: float) -> str:
        """
        Generate daily trading report using AI.
        
        Args:
            trades: List of trades executed today
            account_value: Current account value
            
        Returns:
            Formatted report string
        """
        try:
            prompt = f"""Generate a professional daily trading report.

Account Value: ${account_value:,.2f}
Trades Executed: {len(trades)}

Trade Details:
{json.dumps(trades, indent=2)}

Provide a comprehensive report including:
1. Summary of trading activity
2. Performance metrics (win rate, P&L)
3. Key observations
4. Lessons learned
5. Recommendations for tomorrow

Format as a professional trading report."""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional trading analyst generating daily reports."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Failed to generate daily report: {e}")
            return f"Error generating report: {str(e)}"

