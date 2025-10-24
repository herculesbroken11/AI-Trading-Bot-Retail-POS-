#!/bin/bash

# AI Trading Bot Environment Setup Script
# For Ubuntu 22.04 VPS

echo "Setting up AI Trading Bot environment..."

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.11 and pip
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Install system dependencies
sudo apt install -y build-essential libssl-dev libffi-dev python3-dev

# Create virtual environment
python3.11 -m venv /opt/ov_trading_env

# Activate virtual environment
source /opt/ov_trading_env/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install required Python packages
pip install requests pandas ta websocket-client fastapi uvicorn openai python-dotenv tdameritrade sqlite3 asyncio aiohttp websockets

# Create project directories
mkdir -p /opt/ov_trading_bot/{core,api,data,logs}

# Set permissions
sudo chown -R $USER:$USER /opt/ov_trading_bot
chmod +x /opt/ov_trading_bot

echo "Environment setup complete!"
echo "To activate the environment, run:"
echo "source /opt/ov_trading_env/bin/activate"
echo ""
echo "To start the trading bot, run:"
echo "uvicorn api.main:app --host 0.0.0.0 --port 8000"
