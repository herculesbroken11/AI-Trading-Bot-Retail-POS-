"""
Main Flask application for Oliver Vélez Trading System.
"""
import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from utils.logger import setup_logger

# Import blueprints
from api.auth import auth_bp
from api.quotes import quotes_bp
from api.orders import orders_bp
from api.reports import reports_bp

load_dotenv()

# Initialize logger
logger = setup_logger("main")

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Enable CORS
CORS(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(quotes_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(reports_bp)

@app.route('/', methods=['GET'])
def index():
    """Root endpoint - OAuth callback handler."""
    from flask import request
    from api.auth import callback
    
    # Check if this is an OAuth callback
    if request.args.get('code'):
        return callback()
    
    return jsonify({
        "message": "Oliver Vélez Trading System API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/auth/login - Start OAuth flow",
            "quotes": "/quotes/<symbol> - Get market data",
            "orders": "/orders/place - Place trade order",
            "reports": "/reports/daily - Get daily report"
        }
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "trading-system"
    }), 200

@app.route('/trading-signal', methods=['POST'])
def trading_signal():
    """
    Webhook endpoint for AI trading signals.
    Receives signal from AI module and executes trade.
    """
    from flask import request
    from api.orders import execute_signal
    
    return execute_signal()

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5035))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Flask server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)

