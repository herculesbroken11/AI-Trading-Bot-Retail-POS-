# Schwab AI Trading Bot

A production-ready Python application for automated trading with Charles Schwab API integration, featuring OAuth authentication, FastAPI service, and AI-ready architecture.

## Features

- ✅ **Secure OAuth Authentication** - Multiple authentication flows (local browser, manual code paste)
- ✅ **Schwab API Integration** - Account access, market data, and trading endpoints
- ✅ **FastAPI Service** - RESTful API for trading signals and simulation
- ✅ **Simulation Mode** - Safe default mode prevents accidental live trades
- ✅ **Token Management** - Automatic token refresh and secure storage
- ✅ **Database Support** - SQLite for trade history and signals
- ✅ **Production Ready** - Logging, error handling, and security best practices

## Project Structure

```
Schwab-AI-Trading-Bot/
├── core/
│   ├── __init__.py
│   ├── schwab_client.py      # Schwab API client
│   ├── auth.py                # OAuth authentication helpers
│   ├── config.py              # Configuration management
│   └── strategy_stub.py       # Trading strategy placeholder
├── api/
│   ├── __init__.py
│   └── main.py                # FastAPI application
├── scripts/
│   ├── auth_local.py          # Local browser OAuth
│   ├── exchange_code.py       # Manual code exchange
│   ├── test_connection.py     # API connection test
│   └── init_db.py             # Database initialization
├── data/                      # Data files (tokens, database)
├── logs/                      # Log files
├── tests/                     # Unit tests
├── requirements.txt
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.11+
- Charles Schwab Developer Portal account
- Schwab App Key and Secret
- Virtual environment (venv)

## Installation

### Windows

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Ubuntu/Linux

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. **Copy environment template:**
   ```bash
   cp env_template.txt .env
   ```

2. **Edit `.env` file with your credentials:**
   ```env
   SCHWAB_CLIENT_ID=your_app_key_here
   SCHWAB_CLIENT_SECRET=your_secret_here
   SCHWAB_REDIRECT_URI=https://127.0.0.1:5035
   ```

3. **Configure Schwab Developer Portal:**
   - Log in to [Charles Schwab Developer Portal](https://developer.schwab.com/)
   - Set your app's callback URL to: `https://127.0.0.1:5035`
   - Ensure your app has "Accounts and Trading Production" API access

## Authentication

### Method 1: Local Browser Authentication (Windows/Local)

This method opens a browser automatically and captures the OAuth callback:

```bash
python scripts/auth_local.py
```

**Steps:**
1. Script generates authorization URL
2. Browser opens automatically
3. Log in with your Schwab credentials
4. Approve the application
5. Redirect captured automatically
6. Tokens saved to `./data/schwab_tokens.json`

### Method 2: Manual Code Exchange

If the local listener doesn't work (e.g., on VPS), use manual code exchange:

1. **Generate authorization URL:**
   ```bash
   python scripts/auth_local.py
   ```
   Copy the authorization URL from the output.

2. **Open URL in browser:**
   - Open the URL in any browser (can be on different machine)
   - Log in and approve the application
   - Copy the **full redirect URL** (with `?code=...`)

3. **Exchange code for tokens:**
   ```bash
   python scripts/exchange_code.py
   ```
   Paste the full redirect URL when prompted.

## Testing Connection

After authentication, test your API connection:

```bash
python scripts/test_connection.py
```

This will:
- Verify tokens are valid
- Test account access
- Get market quote for SPY
- Display account information

## Database Initialization

Initialize the SQLite database:

```bash
python scripts/init_db.py
```

This creates tables for:
- Trades
- Signals
- Optimization results
- Logs

## Running the API Server

Start the FastAPI server:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**API Endpoints:**
- `GET /` - API information
- `GET /health` - Health check
- `POST /simulate` - Simulate a trade
- `POST /signal` - Process trading signal
- `GET /config` - Get configuration (safe values only)

**Example:**
```bash
# Health check
curl http://localhost:8000/health

# Simulate trade
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"symbol": "SPY", "action": "BUY", "quantity": 1}'
```

## Deployment to Ubuntu VPS

### Step 1: Transfer Files to VPS

```bash
# On local machine
scp -r Schwab-AI-Trading-Bot/ user@your-server:/opt/

# On VPS
cd /opt/Schwab-AI-Trading-Bot
```

### Step 2: Setup on VPS

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env_template.txt .env
nano .env  # Edit with your credentials
```

### Step 3: Transfer Tokens

**Option A: Secure Copy (Recommended)**
```bash
# On local machine
scp ./data/schwab_tokens.json user@your-server:/opt/Schwab-AI-Trading-Bot/data/
```

**Option B: Manual Creation**
- Authenticate on local machine
- Copy `schwab_tokens.json` content
- Create file on VPS: `nano ./data/schwab_tokens.json`
- Paste content and save

### Step 4: Initialize Database

```bash
python scripts/init_db.py
python scripts/test_connection.py  # Verify tokens work
```

### Step 5: Run as Systemd Service

Create service file: `/etc/systemd/system/schwab-trading-bot.service`

```ini
[Unit]
Description=Schwab AI Trading Bot API
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/opt/Schwab-AI-Trading-Bot
Environment="PATH=/opt/Schwab-AI-Trading-Bot/venv/bin"
ExecStart=/opt/Schwab-AI-Trading-Bot/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable schwab-trading-bot
sudo systemctl start schwab-trading-bot
sudo systemctl status schwab-trading-bot
```

### Step 6: Run with Screen (Alternative)

```bash
# Install screen if needed
sudo apt install screen

# Start screen session
screen -S trading-bot

# Activate venv and run
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Detach: Ctrl+A, then D
# Reattach: screen -r trading-bot
```

## Security Checklist

- ✅ **Never commit `.env` file** - Already in `.gitignore`
- ✅ **Never commit `schwab_tokens.json`** - Already in `.gitignore`
- ✅ **Set secure file permissions:**
  ```bash
  chmod 600 .env
  chmod 600 ./data/schwab_tokens.json
  ```
- ✅ **Rotate credentials regularly** - Update tokens every 90 days
- ✅ **Use strong passwords** - For Schwab account and VPS
- ✅ **Never share credentials** - Use secure channels (encrypted files, password managers)
- ✅ **Do not use AnyDesk/remote desktop** - To type passwords (security risk)
- ✅ **Enable firewall** - Only allow necessary ports (8000 for API)
- ✅ **Use HTTPS** - When deploying to production (use reverse proxy like nginx)

## Token Rotation

Tokens expire after a period. To refresh:

1. **Automatic refresh:**
   - Tokens auto-refresh when expired
   - No action needed if refresh token is valid

2. **Manual re-authentication:**
   ```bash
   # Delete old tokens
   rm ./data/schwab_tokens.json
   
   # Re-authenticate
   python scripts/auth_local.py
   ```

## Troubleshooting

### Authentication Issues

**Error: "Disallowed hostname"**
- Solution: Ensure callback URL in Schwab Developer Portal is `https://127.0.0.1:5035`

**Error: "Port already in use"**
- Solution: Change `SCHWAB_REDIRECT_URI` port in `.env` or close conflicting application

**Error: "Token exchange failed"**
- Solution: Codes expire quickly - generate new code immediately
- Verify `SCHWAB_CLIENT_ID` and `SCHWAB_CLIENT_SECRET` are correct
- Ensure redirect URI matches exactly in Developer Portal

### API Connection Issues

**Error: "No valid access token"**
- Solution: Re-authenticate using `auth_local.py` or `exchange_code.py`

**Error: "Failed to get accounts"**
- Solution: Check API permissions in Schwab Developer Portal
- Verify account has API access enabled

### Deployment Issues

**Service won't start:**
- Check logs: `sudo journalctl -u schwab-trading-bot -f`
- Verify paths in systemd service file
- Check file permissions

**Tokens not working on VPS:**
- Verify tokens file was transferred correctly
- Check file permissions: `chmod 600 ./data/schwab_tokens.json`
- Test connection: `python scripts/test_connection.py`

## Development

### Running Tests

```bash
pytest tests/
```

### Adding AI Integration

The project includes a placeholder for AI integration in `core/strategy_stub.py`. To add OpenAI:

1. Add OpenAI API key to `.env`:
   ```env
   OPENAI_API_KEY=your_key_here
   ```

2. Update `core/strategy_stub.py` to use OpenAI API

3. The strategy will automatically use AI when key is present

## Simulation Mode

By default, the bot runs in **simulation mode** (`SIMULATION_MODE=true`). This means:
- ✅ Signals are logged but not executed
- ✅ `/simulate` endpoint returns fake trade results
- ✅ No actual orders are placed

To enable live trading (USE WITH CAUTION):
```env
SIMULATION_MODE=false
ENABLE_LIVE_TRADING=true
```

**⚠️ Warning:** Only enable live trading after thorough testing in simulation mode.

## License

This project is for educational purposes only. Trading involves substantial risk of loss.

## Support

For issues:
1. Check logs in `./logs/trading_bot.log`
2. Review troubleshooting section
3. Verify configuration in `.env`
4. Test connection with `test_connection.py`

## Contributing

This is a production-ready scaffold. Extend with:
- AI trading strategies
- Advanced risk management
- Performance analytics
- Real-time market data streaming

---

**⚠️ Disclaimer:** This software is provided as-is for educational purposes. Trading involves substantial risk of loss. Use at your own risk and ensure compliance with all applicable laws and regulations.
