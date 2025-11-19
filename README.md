# Oliver Vélez Trading System

A fully automated trading system implementing the Oliver Vélez intraday trading methodology, integrated with Charles Schwab API and GPT-4o AI analysis.

## 🚀 Features

- **Oliver Vélez Strategy Engine**: Complete OV methodology including 4 Fantastics, Whale, Kamikaze, RBI, GBI setups, and 75% Candle Rule
- **AI-Powered Validation**: GPT-4o integration for intelligent signal validation and daily reporting
- **Fully Automated**: Runs continuously during market hours - no manual intervention needed
- **Advanced Position Management**: Trailing stops, break-even management, position scaling, auto-close at 4 PM ET
- **Schwab API Integration**: OAuth authentication, real-time market data, and trade execution
- **Risk Management**: Automated position sizing, $300 max risk per trade, ATR-based stops
- **Web Dashboard**: Real-time monitoring and control interface

## 📋 Quick Start

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
- `SCHWAB_REDIRECT_URI`: Your callback URL (e.g., `https://your-server.com`)
- `OPENAI_API_KEY`: Your OpenAI API key
- `TRADING_WATCHLIST`: Comma-separated symbols (e.g., `AAPL,MSFT,GOOGL,TSLA,NVDA`)

Optional:
- `AUTO_START_SCHEDULER=true` (default: enabled)
- `MAX_RISK_PER_TRADE=300` (default: $300)

### 3. Authenticate with Schwab

**Option A: Using callback script**
```bash
python callback.py
```
This opens your browser for authentication and saves tokens automatically.

**Option B: Manual flow**
1. Start server: `python main.py`
2. Visit: `http://localhost:5035/auth/login`
3. Complete authentication in browser
4. Tokens saved automatically

### 4. Run the Application

```bash
# Windows
python main.py

# Linux/Mac
python3 main.py

# Or use provided scripts
./start.sh  # Linux/Mac
start.bat   # Windows
```

**Once authenticated, automation starts automatically!**

## 🤖 How It Works

### Hybrid System: OV Engine + AI Validation

The bot uses a two-stage process:

```
1. OV Strategy Engine (Rule-Based)
   ↓
   Identifies setups using technical rules:
   - 4 Fantastics validation
   - Whale, Kamikaze, RBI, GBI setups
   - 75% Candle Rule
   - SMA8/20/200, ATR14, RSI calculations
   ↓
2. AI Validation (GPT-4o)
   ↓
   AI analyzes and validates:
   - Reviews all technical data
   - Applies OV methodology
   - Provides confidence score (0-1)
   - Final approval/rejection
   ↓
3. Trade Execution
   ↓
   Only executes if:
   - OV Engine found setup
   - 4 Fantastics all met
   - AI confirms (confidence > 0.7)
```

### Complete Automated Flow

```
Client Authenticates → Token Received
    ↓
Scheduler Starts Automatically
    ↓
Market Analysis Every 5 Minutes
    ↓
OV Engine Identifies Setups
    ↓
AI Validates Signals
    ↓
Trades Execute Automatically (if approved)
    ↓
Positions Managed Automatically:
  - Trailing stops updated every minute
  - Break-even set after 1 ATR profit
  - Position scaling when profitable
    ↓
Auto-Close All Positions at 4:00 PM ET
    ↓
Daily Report Generated
```

## 📊 Advanced OV Rules Implemented

### 4 Fantastics
All four conditions must be met:
1. Trend alignment (SMA8 > SMA20 > SMA200 for bullish)
2. Price position relative to SMA200
3. Volume confirmation (>1.2x average)
4. RSI in favorable zone (30-70)

### Setup Types
- **Whale Setup**: Massive volume spike (3x+) with price movement
- **Kamikaze Setup**: Rapid price reversal after strong move
- **RBI (Rapid Breakout Indicator)**: Fast breakout with volume surge
- **GBI (Gap Breakout Indicator)**: Gap up/down with continuation
- **Pullback/Breakout**: Classic OV setups

### 75% Candle Rule
Candle body must be ≥75% of total range for valid entry.

## 🎯 Position Management

### Automated Features

- **Trailing Stops**: Automatically trails by 0.5 ATR (only moves in favorable direction)
- **Break-Even**: Moves stop to entry after 1 ATR profit
- **Position Scaling**: Adds to winning positions (up to 2 additions)
- **Auto-Close**: Closes all positions at 4:00 PM ET
- **Real-Time Updates**: Position prices updated every minute

## 📡 API Endpoints

### Authentication
- `GET /auth/login` - Start OAuth flow
- `GET /auth/callback` - OAuth callback handler
- `GET /auth/status` - Check auth status
- `POST /auth/refresh` - Refresh access token

### Market Data
- `GET /quotes/<symbol>` - Get real-time quote
- `GET /quotes/historical/<symbol>` - Get historical data
- `GET /quotes/analyze/<symbol>` - Get analysis with indicators
- `GET /quotes/batch?symbols=AAPL,MSFT` - Get multiple quotes
- `GET /quotes/options/chains?symbol=AAPL` - Get option chain

### Trading
- `POST /orders/place` - Place a trade order
- `POST /orders/signal` - Execute AI trading signal
- `GET /orders/accounts` - Get trading accounts
- `GET /orders/positions` - Get current positions
- `GET /orders/all-orders?accountId=xxx` - Get all orders

### Automation
- `POST /automation/start` - Start automated trading
- `POST /automation/stop` - Stop automated trading
- `GET /automation/status` - Get automation status
- `GET/POST /automation/watchlist` - Manage watchlist

### Positions
- `GET /positions/active` - Get all active positions
- `POST /positions/close-all` - Close all positions
- `POST /positions/add-to/<symbol>/<account_id>` - Scale position

### Reporting
- `GET /reports/daily?accountId=xxx` - Generate daily P&L report
- `GET /reports/compliance?accountId=xxx` - Compliance metrics
- `GET /reports/trades?accountId=xxx` - Get trade history

### Streaming
- `POST /streaming/connect` - Connect to WebSocket
- `POST /streaming/subscribe/<symbol>` - Subscribe to symbol
- `GET /streaming/status` - Get streaming status

**See `API_DOCUMENTATION.md` for complete API reference.**

## 🖥️ Dashboard

Access the web dashboard at:
```
http://your-server.com/dashboard
```

Features:
- Real-time position monitoring
- Automation status and control
- P&L tracking
- Auto-refreshes every 30 seconds

## 🚢 Deployment to Ubuntu VPS

### 1. Transfer Files

```bash
scp -r . user@your-server:/opt/trading-system/
```

### 2. Setup on VPS

```bash
ssh user@your-server
cd /opt/trading-system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your credentials
```

### 3. Authenticate (One-Time)

```bash
# Start server temporarily
python3 main.py

# In browser, visit:
http://your-server:5035/auth/login

# Complete authentication
# Tokens saved to data/tokens.json
```

### 4. Create Systemd Service

Create `/etc/systemd/system/trading-system.service`:

```ini
[Unit]
Description=Oliver Vélez Trading System
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/opt/trading-system
Environment="PATH=/opt/trading-system/venv/bin"
ExecStart=/opt/trading-system/venv/bin/python3 /opt/trading-system/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-system
sudo systemctl start trading-system

# Check status
sudo systemctl status trading-system

# View logs
sudo journalctl -u trading-system -f
```

### 5. Configure Nginx (Optional)

```nginx
server {
    listen 80;
    server_name your-server.com;

    location / {
        proxy_pass http://localhost:5035;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## ⚙️ Configuration

### Auto-Start Scheduler

By default, automation starts automatically after authentication. To disable:

```bash
# In .env
AUTO_START_SCHEDULER=false
```

Then manually start:
```bash
curl -X POST http://your-server.com/automation/start
```

### Watchlist

Set trading symbols in `.env`:
```bash
TRADING_WATCHLIST=AAPL,MSFT,GOOGL,TSLA,NVDA
```

Or update via API:
```bash
curl -X POST http://your-server.com/automation/watchlist \
  -H "Content-Type: application/json" \
  -d '{"watchlist": ["AAPL", "MSFT", "GOOGL"]}'
```

### Risk Management

Configure in `.env`:
```bash
MAX_RISK_PER_TRADE=300  # Maximum risk per trade in dollars
```

## 📁 Project Structure

```
.
├── core/              # OV strategy engine (indicators, setups)
│   ├── ov_engine.py   # Main strategy engine
│   ├── position_manager.py  # Position management
│   └── scheduler.py   # Automation scheduler
├── api/               # Flask routes
│   ├── auth.py        # Authentication
│   ├── quotes.py      # Market data
│   ├── orders.py      # Trade execution
│   ├── automation.py  # Automation control
│   ├── positions.py   # Position management API
│   ├── streaming.py   # WebSocket streaming
│   └── reports.py     # Reporting
├── ai/                # AI analysis module
│   └── analyze.py     # GPT-4o integration
├── data/              # Tokens, logs, CSV files, reports
├── static/            # Static files
│   └── dashboard.html # Web dashboard
├── utils/             # Helpers, logger, risk control
├── main.py            # Main Flask application
└── requirements.txt   # Dependencies
```

## 📝 Usage Examples

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
    "setup_type": "WHALE_LONG",
    "accountId": "your_account_id"
  }'
```

### Check Automation Status

```bash
curl http://localhost:5035/automation/status
```

### Generate Daily Report

```bash
curl http://localhost:5035/reports/daily?accountId=your_account_id
```

## 🔒 Risk Management

- **Maximum risk per trade**: $300 (configurable)
- **Stop loss**: ATR14-based (1.0-1.5x depending on setup)
- **Take profit**: ATR14-based (2.0-2.5x)
- **Auto-close positions**: 4:00 PM ET
- **Position sizing**: Based on risk per share
- **Trailing stops**: 0.5 ATR trailing
- **Break-even**: Set after 1 ATR profit

## 📊 Logging

Logs are stored in `data/logs/`:
- Daily log files: `trading_YYYYMMDD.log`
- Trade log: `data/trades.csv`
- Reports: `data/reports/daily_report_YYYYMMDD.txt`
- Active positions: `data/active_positions.json`

## 🐛 Troubleshooting

**See `TROUBLESHOOTING.md` for detailed troubleshooting guide.**

Common issues:

1. **401 Unauthorized**: Check redirect URI matches exactly in Schwab Developer Portal
2. **Scheduler not starting**: Verify `AUTO_START_SCHEDULER=true` in `.env`
3. **Positions not closing**: Check server time zone (should be ET or configured correctly)
4. **AI errors**: Verify `OPENAI_API_KEY` is set correctly

## 📚 Documentation

- **API_DOCUMENTATION.md** - Complete API reference
- **TROUBLESHOOTING.md** - Troubleshooting guide

## 🔐 Security Notes

- Never commit `.env` file to version control
- Keep `data/tokens.json` secure (contains access tokens)
- Use HTTPS in production
- Regularly rotate API keys

## 📄 License

Private - For authorized use only.

## 🆘 Support

For issues or questions:
1. Check logs in `data/logs/`
2. Review `TROUBLESHOOTING.md`
3. Check API documentation in `API_DOCUMENTATION.md`

---

**The system is fully automated - once authenticated, it runs hands-off! 🚀**
