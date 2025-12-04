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
from api.streaming import streaming_bp
from api.automation import automation_bp
from api.positions import positions_bp

load_dotenv()

# Initialize logger
logger = setup_logger("main")

# Initialize database
try:
    from utils.database import init_database
    init_database()
    logger.info("Database initialized")
except Exception as e:
    logger.warning(f"Database initialization failed: {e}")

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
app.register_blueprint(streaming_bp)
app.register_blueprint(automation_bp)
app.register_blueprint(positions_bp)

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
            "reports": "/reports/daily - Get daily report",
            "streaming": "/streaming/* - Real-time WebSocket quotes",
            "automation": "/automation/* - Automated trading control"
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

# Serve static files (dashboard)
from flask import send_from_directory

@app.route('/dashboard')
@app.route('/dashboard/<path:path>')
def dashboard(path='index.html'):
    """Serve React dashboard."""
    try:
        return send_from_directory('static/dashboard', path)
    except:
        # Fallback to index.html for React Router
        return send_from_directory('static/dashboard', 'index.html')

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5035))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Flask server on {host}:{port}")
    logger.info(f"Dashboard available at: http://{host}:{port}/dashboard")
    app.run(host=host, port=port, debug=debug)

