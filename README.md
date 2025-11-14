# Oliver Vélez Trading System

A Flask-based automated trading system implementing the Oliver Vélez intraday trading methodology, integrated with Charles Schwab API and GPT-5 AI analysis.

## Features

- **Oliver Vélez Strategy Engine**: Implements SMA8/20/200 trend analysis, ATR-based stops, and volume confirmation
- **Schwab API Integration**: OAuth authentication, market data, and trade execution
- **AI-Powered Analysis**: GPT-5 integration for signal generation and daily reporting
- **Risk Management**: Automated position sizing, stop losses, and $300 max risk per trade
- **Daily Reporting**: Automated P&L tracking and compliance reports

## Project Structure

```
.
├── core/           # OV strategy engine (indicators, setups)
├── api/            # Flask routes (auth, quotes, orders, reports)
├── data/           # Tokens, logs, CSV files, reports
├── ai/             # GPT-5 analysis module
├── utils/          # Helpers, logger, risk control
├── main.py         # Main Flask application
├── callback.py     # OAuth callback helper
├── exchange.py     # Token exchange helper
└── requirements.txt
```

## Setup

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:
- `SCHWAB_CLIENT_ID`: Your Schwab app key
- `SCHWAB_CLIENT_SECRET`: Your Schwab app secret
- `SCHWAB_REDIRECT_URI`: `http://localhost:5035`
- `OPENAI_API_KEY`: Your OpenAI API key

### 3. Authenticate with Schwab

**Option A: Using callback script**
```bash
python callback.py
```
This will open your browser for authentication.

**Option B: Manual flow**
1. Visit `/auth/login` endpoint
2. Complete authentication in browser
3. Callback will save tokens automatically

### 4. Run the Application

```bash
# Windows
set FLASK_APP=main.py
flask run --host=0.0.0.0 --port=5035

# Linux/Mac
export FLASK_APP=main.py
flask run --host=0.0.0.0 --port=5035

# Or directly
python main.py
```

## API Endpoints

### Authentication
- `GET /auth/login` - Start OAuth flow
- `GET /auth/callback` - OAuth callback handler
- `GET /auth/status` - Check auth status
- `POST /auth/refresh` - Refresh access token

### Market Data
- `GET /quotes/<symbol>` - Get real-time quote
- `GET /quotes/historical/<symbol>` - Get historical data
- `GET /quotes/analyze/<symbol>` - Get analysis with indicators

### Trading
- `POST /orders/place` - Place a trade order
- `POST /orders/signal` - Execute AI trading signal
- `GET /orders/accounts` - Get trading accounts
- `GET /orders/positions` - Get current positions

### Reporting
- `GET /reports/daily` - Generate daily P&L report
- `GET /reports/compliance` - Compliance metrics
- `GET /reports/trades` - Get trade history

### Webhooks
- `POST /trading-signal` - AI signal webhook endpoint

## Usage Examples

### Get Market Analysis
```bash
curl http://localhost:5035/quotes/analyze/AAPL
```

### Execute AI Signal
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
    "accountId": "your_account_id"
  }'
```

### Generate Daily Report
```bash
curl http://localhost:5035/reports/daily?accountId=your_account_id
```

## Deployment to Ubuntu VPS

### 1. Transfer Files
```bash
scp -r . user@31.220.54.199:/opt/trading-system/
```

### 2. Setup on VPS
```bash
ssh user@31.220.54.199
cd /opt/trading-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create Systemd Service
Create `/etc/systemd/system/trading-system.service`:
```ini
[Unit]
Description=Oliver Vélez Trading System
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/opt/trading-system
Environment="PATH=/opt/trading-system/venv/bin"
ExecStart=/opt/trading-system/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-system
sudo systemctl start trading-system
```

## Risk Management

- Maximum risk per trade: $300 (configurable)
- Stop loss: ATR14-based (1.0-1.5x)
- Take profit: ATR14-based (2.0-2.5x)
- Auto-close positions: 4:00 PM ET
- Position sizing: Based on risk per share

## Logging

Logs are stored in `data/logs/`:
- Daily log files: `trading_YYYYMMDD.log`
- Trade log: `data/trades.csv`
- Reports: `data/reports/daily_report_YYYYMMDD.txt`

## License

Private - For authorized use only.

