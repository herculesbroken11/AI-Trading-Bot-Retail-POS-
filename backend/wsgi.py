"""
WSGI entry point for Gunicorn production server.
Run from backend directory: gunicorn wsgi:application
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from backend directory
backend_dir = Path(__file__).parent
env_path = backend_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

# Ensure backend directory is in Python path
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import the Flask app from main.py
from main import app

# Gunicorn expects the application variable
application = app

# Optional: Configure for production
if __name__ == "__main__":
    # This block won't run under gunicorn, but useful for testing
    port = int(os.getenv('FLASK_PORT', 5035))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    application.run(host=host, port=port)

