"""
WSGI entry point for Gunicorn production server.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

