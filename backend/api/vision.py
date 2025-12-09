"""
Vision Analysis API
Allows manual image upload for AI vision analysis.
"""
import os
import base64
import requests
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from typing import Dict, Any, Optional
from ai.analyze import TradingAIAnalyzer
from utils.logger import setup_logger

vision_bp = Blueprint('vision', __name__, url_prefix='/vision')
logger = setup_logger("vision")

# Initialize AI analyzer
try:
    ai_analyzer = TradingAIAnalyzer()
except Exception as e:
    logger.error(f"Failed to initialize AI analyzer: {e}")
    ai_analyzer = None

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def download_image_from_url(url: str) -> Optional[str]:
    """
    Download image from URL and convert to base64.
    
    Args:
        url: Image URL
        
    Returns:
        Base64 encoded image string or None
    """
    try:
        response = requests.get(url, timeout=10, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logger.warning(f"URL does not point to an image: {content_type}")
            return None
        
        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_FILE_SIZE:
            logger.warning(f"Image too large: {content_length} bytes")
            return None
        
        # Download and encode
        image_data = response.content
        if len(image_data) > MAX_FILE_SIZE:
            logger.warning(f"Image too large: {len(image_data)} bytes")
            return None
        
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        logger.info(f"Successfully downloaded image from URL: {len(image_data)} bytes")
        return image_base64
        
    except Exception as e:
        logger.error(f"Failed to download image from URL: {e}")
        return None

@vision_bp.route('/analyze', methods=['POST'])
def analyze_image():
    """
    Analyze an uploaded image or image URL using AI vision.
    
    Request body (JSON):
        - image_url: Optional URL to image
        - symbol: Optional stock symbol for context
        
    Request body (multipart/form-data):
        - file: Image file to upload
        
    Returns:
        JSON with AI analysis results
    """
    try:
        if not ai_analyzer:
            return jsonify({
                "error": "AI analyzer not available"
            }), 500
        
        image_base64 = None
        symbol = None
        
        # Check if JSON request (for URL)
        if request.is_json:
            data = request.get_json()
            image_url = data.get('image_url')
            symbol = data.get('symbol', 'UNKNOWN')
            
            if not image_url:
                return jsonify({
                    "error": "image_url is required in JSON request"
                }), 400
            
            image_base64 = download_image_from_url(image_url)
            if not image_base64:
                return jsonify({
                    "error": "Failed to download image from URL"
                }), 400
        
        # Check if multipart/form-data (for file upload)
        elif 'file' in request.files:
            file = request.files['file']
            symbol = request.form.get('symbol', 'UNKNOWN')
            
            if file.filename == '':
                return jsonify({
                    "error": "No file selected"
                }), 400
            
            if not allowed_file(file.filename):
                return jsonify({
                    "error": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
                }), 400
            
            # Read file
            file_data = file.read()
            if len(file_data) > MAX_FILE_SIZE:
                return jsonify({
                    "error": f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
                }), 400
            
            # Convert to base64
            image_base64 = base64.b64encode(file_data).decode('utf-8')
            logger.info(f"Image uploaded: {file.filename}, {len(file_data)} bytes")
        
        else:
            return jsonify({
                "error": "Either 'image_url' (JSON) or 'file' (form-data) is required"
            }), 400
        
        if not image_base64:
            return jsonify({
                "error": "Failed to process image"
            }), 400
        
        # Analyze image using AI vision
        try:
            # Create a prompt for chart analysis
            prompt = f"""Analyze this trading chart image for {symbol if symbol != 'UNKNOWN' else 'the stock'}.

Focus on:
1. Price Action: Identify candlestick patterns, support/resistance levels, trend direction
2. Moving Averages: Check SMA alignment (SMA8, SMA20, SMA200) and price position relative to them
3. Volume: Assess volume patterns and confirmations
4. Indicators: Analyze RSI, ATR, and other visible indicators
5. Setup Patterns: Identify any Oliver Vélez trading setups (Whale, Kamikaze, RBI, GBI, etc.)
6. Entry/Exit Points: Suggest optimal entry, stop loss, and take profit levels
7. Risk Assessment: Evaluate risk/reward ratio

Apply Oliver Vélez trading rules:
- 4 Fantastics must be met (Price > SMA200, SMA alignment, Volume > average, RSI in range)
- Use ATR for stop placement (1.5x ATR for pullbacks, 1.0x ATR for breakouts)
- Minimum risk/reward ratio: 1:1.5
- Consider time of day (avoid entries after 3:30 PM ET)

Return your analysis as JSON with:
{{
    "action": "BUY" | "SELL" | "HOLD" | "SHORT",
    "entry": float,
    "stop": float,
    "target": float,
    "setup_type": string,
    "position_size": int,
    "confidence": float (0-1),
    "reasoning": string,
    "chart_observations": string,
    "pattern_identified": string,
    "risk_reward_ratio": float
}}"""

            # Use GPT-4o Vision
            response = ai_analyzer.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": ai_analyzer._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            content = response.choices[0].message.content
            analysis = json.loads(content)
            
            logger.info(f"Vision analysis completed for {symbol}")
            
            return jsonify({
                "status": "success",
                "symbol": symbol,
                "analysis": analysis,
                "image_size": len(image_base64)
            }), 200
            
        except Exception as e:
            logger.error(f"AI vision analysis failed: {e}", exc_info=True)
            return jsonify({
                "error": f"AI analysis failed: {str(e)}"
            }), 500
        
    except Exception as e:
        logger.error(f"Vision analysis endpoint error: {e}", exc_info=True)
        return jsonify({
            "error": str(e)
        }), 500

@vision_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "ai_analyzer_available": ai_analyzer is not None
    }), 200

