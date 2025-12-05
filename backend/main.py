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
    """Serve React dashboard from frontend/dist."""
    import os
    from pathlib import Path
    from flask import abort
    
    # Get the project root directory (parent of backend)
    backend_dir = Path(__file__).parent.absolute()
    project_root = backend_dir.parent.absolute()
    frontend_dist = project_root / 'frontend' / 'dist'
    
    # Convert to absolute path string
    dist_path = str(frontend_dist)
    
    # Check if directory exists
    if not os.path.exists(dist_path):
        logger.error(f"Dashboard directory not found: {dist_path}")
        logger.error(f"Backend dir: {backend_dir}")
        logger.error(f"Project root: {project_root}")
        return jsonify({
            "error": "Dashboard not found",
            "path": dist_path,
            "message": "Frontend build not found. Please run 'npm run build' in frontend directory."
        }), 404
    
    # Check if file exists
    file_path = os.path.join(dist_path, path)
    if not os.path.exists(file_path) and path != 'index.html':
        # For React Router - serve index.html for all routes
        path = 'index.html'
    
    try:
        return send_from_directory(dist_path, path)
    except Exception as e:
        logger.error(f"Error serving dashboard file: {e}", exc_info=True)
        # Fallback to index.html
        try:
            return send_from_directory(dist_path, 'index.html')
        except Exception as e2:
            logger.error(f"Error serving index.html: {e2}", exc_info=True)
            return jsonify({
                "error": "Dashboard error",
                "message": str(e2),
                "path": dist_path
            }), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5035))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Flask server on {host}:{port}")
    logger.info(f"Dashboard available at: http://{host}:{port}/dashboard")
    app.run(host=host, port=port, debug=debug)

