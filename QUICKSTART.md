# Quick Start Guide

## 1. Initial Setup (5 minutes)

```bash
# Install dependencies
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Configure environment
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac
# Edit .env with your credentials
```

## 2. Authenticate with Schwab

**Option A: Use callback script**
```bash
python callback.py
```
This opens your browser → login → saves tokens automatically.

**Option B: Use API endpoint**
```bash
# Start server
python main.py

# In another terminal/browser
curl http://localhost:5035/auth/login
# Follow the auth_url in response
```

## 3. Start Trading System

```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh
./start.sh

# Or directly
python main.py
```

## 4. Test the System

```bash
# Check health
curl http://localhost:5035/health

# Check auth status
curl http://localhost:5035/auth/status

# Get market analysis for AAPL
curl http://localhost:5035/quotes/analyze/AAPL

# Get accounts
curl http://localhost:5035/orders/accounts
```

## 5. Execute a Trade Signal

```bash
curl -X POST http://localhost:5035/orders/signal \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "action": "BUY",
    "entry": 150.00,
    "stop": 145.00,
    "target": 160.00,
    "setup_type": "PULLBACK_LONG",
    "accountId": "YOUR_ACCOUNT_ID"
  }'
```

## 6. Generate Daily Report

```bash
curl http://localhost:5035/reports/daily?accountId=YOUR_ACCOUNT_ID
```

## Common Issues

**"Not authenticated" error:**
- Run `python callback.py` to authenticate
- Check `data/tokens.json` exists

**"Module not found" error:**
- Activate virtual environment: `venv\Scripts\activate`
- Install dependencies: `pip install -r requirements.txt`

**Port 5035 already in use:**
- Change `FLASK_PORT` in `.env`
- Or kill process using port 5035

## Next Steps

1. Configure your trading symbols in a watchlist
2. Set up automated signal generation (cron/scheduler)
3. Review daily reports in `data/reports/`
4. Monitor logs in `data/logs/`

