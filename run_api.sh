#!/bin/bash

# AI Trading Bot API Server Startup Script

echo "Starting AI Trading Bot API Server..."

# Activate virtual environment
source /opt/ov_trading_env/bin/activate

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy env_template.txt to .env and configure your API keys."
    exit 1
fi

# Start the FastAPI server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

echo "API Server stopped."
