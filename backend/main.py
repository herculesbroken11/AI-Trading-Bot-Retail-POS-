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
from api.optimization import optimization_bp
from api.activity import activity_bp
from api.vision import vision_bp
from api.charts import charts_bp
from api.polygon_data import polygon_data_bp
from api.polygon_monitor import polygon_monitor_bp

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
app.register_blueprint(optimization_bp)
app.register_blueprint(activity_bp)
app.register_blueprint(vision_bp)
app.register_blueprint(charts_bp)
app.register_blueprint(polygon_data_bp)
app.register_blueprint(polygon_monitor_bp)

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
@app.route('/dashboard/')
@app.route('/dashboard/<path:path>')
def dashboard(path='index.html'):
    """Serve React dashboard from frontend/dist."""
    import os
    from pathlib import Path
    from flask import abort, send_file
    
    try:
        # Get the project root directory (parent of backend)
        backend_dir = Path(__file__).parent.absolute()
        project_root = backend_dir.parent.absolute()
        frontend_dist = project_root / 'frontend' / 'dist'
        
        # Convert to absolute path string
        dist_path = str(frontend_dist)
        
        logger.info(f"Dashboard request - path: {path}, dist_path: {dist_path}")
        
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
        
        # Handle root dashboard request
        if path == 'index.html' or path == '':
            index_path = os.path.join(dist_path, 'index.html')
            if os.path.exists(index_path):
                logger.info(f"Serving index.html from {index_path}")
                return send_file(index_path)
            else:
                logger.error(f"index.html not found at {index_path}")
                return jsonify({
                    "error": "index.html not found",
                    "path": index_path
                }), 404
        
        # Check if file exists
        file_path = os.path.join(dist_path, path)
        logger.info(f"Checking file: {file_path}, exists: {os.path.exists(file_path)}")
        
        if not os.path.exists(file_path):
            # For React Router - serve index.html for all routes
            logger.info(f"File not found, serving index.html for React Router")
            index_path = os.path.join(dist_path, 'index.html')
            if os.path.exists(index_path):
                return send_file(index_path)
            else:
                return jsonify({
                    "error": "File not found and index.html missing",
                    "requested": path,
                    "dist_path": dist_path
                }), 404
        
        # Serve the file
        logger.info(f"Serving file: {file_path}")
        return send_file(file_path)
        
    except Exception as e:
        logger.error(f"Error serving dashboard: {e}", exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Traceback: {error_trace}")
        return jsonify({
            "error": "Dashboard error",
            "message": str(e),
            "traceback": error_trace
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5035))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Flask server on {host}:{port}")
    logger.info(f"Dashboard available at: http://{host}:{port}/dashboard")
    app.run(host=host, port=port, debug=debug)

