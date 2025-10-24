#!/bin/bash

# AI Trading Bot Main Application Startup Script

echo "Starting AI Trading Bot..."

# Activate virtual environment
source /opt/ov_trading_env/bin/activate

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy env_template.txt to .env and configure your API keys."
    exit 1
fi

# Start the main trading engine
python main.py

echo "Trading Bot stopped."
