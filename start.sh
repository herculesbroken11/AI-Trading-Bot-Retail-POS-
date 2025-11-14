#!/bin/bash
# Linux/Mac startup script for Oliver Vélez Trading System

echo "Starting Oliver Vélez Trading System..."
echo

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/lib/python*/site-packages/flask/__init__.py" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found!"
    echo "Please copy .env.example to .env and configure your credentials."
    exit 1
fi

# Start Flask server
echo "Starting Flask server on port 5035..."
echo
python main.py

