@echo off
REM Windows startup script for Oliver Vélez Trading System

echo Starting Oliver Vélez Trading System...
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies if needed
if not exist "venv\Lib\site-packages\flask" (
    echo Installing dependencies...
    pip install -r backend\requirements.txt
)

REM Check for .env file
if not exist "backend\.env" (
    echo WARNING: .env file not found!
    echo Please copy .env.example to .env and configure your credentials.
    pause
)

REM Start Flask server
echo Starting Flask server on port 5035...
echo.
cd backend
python main.py

pause

