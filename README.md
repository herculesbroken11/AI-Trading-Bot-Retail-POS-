# Oliver Vélez Trading System

Automated trading system using Oliver Vélez (OV) methodology with AI validation.

## Project Structure

```
.
├── backend/              # Backend Flask API
│   ├── api/             # API endpoints (auth, orders, quotes, etc.)
│   ├── core/            # OV strategy engine
│   ├── ai/              # AI analysis module
│   ├── utils/           # Utilities (logger, helpers, database)
│   ├── data/            # Data storage (tokens, logs, CSV)
│   ├── static/          # Static files (dashboard build)
│   ├── main.py          # Flask application entry point
│   ├── wsgi.py          # Gunicorn WSGI entry point
│   └── requirements.txt # Python dependencies
│
├── frontend/            # React frontend
│   ├── src/             # React source code
│   ├── package.json     # Node dependencies
│   └── vite.config.js   # Vite configuration
│
├── start.sh             # Linux/Mac startup script
└── start.bat            # Windows startup script
```

## Quick Start

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Schwab API credentials
```

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Build for production
npm run build
```

### 3. Run the Application

**Option A: Use startup scripts (recommended)**

```bash
# Linux/Mac
./start.sh

# Windows
start.bat
```

**Option B: Manual**

```bash
# Terminal 1: Backend
cd backend
python main.py

# Terminal 2: Frontend (development)
cd frontend
npm run dev
```

### 4. Access Dashboard

- Production: `http://localhost:5035/dashboard`
- Development: `http://localhost:5173` (Vite dev server)

## Authentication

1. Start the backend server
2. Visit: `http://localhost:5035/auth/login`
3. Complete OAuth authentication in browser
4. Tokens are saved automatically to `backend/data/tokens.json`

## Development

### Backend Development

```bash
cd backend
source venv/bin/activate
python main.py
```

### Frontend Development

```bash
cd frontend
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies API requests to the backend.

### Building Frontend for Production

```bash
cd frontend
npm run build
```

This builds the React app to `backend/static/dashboard/` which is served by Flask.

## Deployment

### Ubuntu VPS with Gunicorn

1. **Transfer files to server:**
```bash
scp -r . user@your-server:/opt/trading-system/
```

2. **Setup on server:**
```bash
ssh user@your-server
cd /opt/trading-system

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend build
cd ../frontend
npm install
npm run build

# Configure .env
cd ../backend
cp .env.example .env
nano .env
```

3. **Create systemd service** (`/etc/systemd/system/trading-system.service`):
```ini
[Unit]
Description=Oliver Vélez Trading System
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/opt/trading-system/backend
Environment="PATH=/opt/trading-system/backend/venv/bin"
ExecStart=/opt/trading-system/backend/venv/bin/gunicorn -w 4 -b 0.0.0.0:5035 wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

4. **Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-system
sudo systemctl start trading-system
```

## API Endpoints

See `API_DOCUMENTATION.md` for complete API reference.

### Key Endpoints:
- `GET /auth/login` - Start OAuth flow
- `GET /orders/accounts` - Get trading accounts
- `GET /positions/active` - Get active positions
- `GET /reports/daily?accountId=xxx` - Daily P&L report
- `POST /automation/start` - Start automated trading
- `POST /automation/stop` - Stop automated trading

## Configuration

### Environment Variables (`.env` in `backend/`)

```bash
# Schwab API
SCHWAB_CLIENT_ID=your_client_id
SCHWAB_CLIENT_SECRET=your_client_secret
SCHWAB_REDIRECT_URI=http://localhost:5035

# OpenAI (for AI validation)
OPENAI_API_KEY=your_openai_key

# Trading Configuration
TRADING_WATCHLIST=AAPL,MSFT,GOOGL,TSLA,NVDA
MAX_RISK_PER_TRADE=300
AUTO_START_SCHEDULER=true

# Flask
FLASK_PORT=5035
FLASK_HOST=0.0.0.0
FLASK_DEBUG=false
```

## Features

- **OV Strategy Engine**: Implements Oliver Vélez trading methodology
- **AI Validation**: GPT-4o validates trading signals
- **Automated Trading**: Fully automated position management
- **Real-time Dashboard**: React-based web interface
- **Risk Management**: Built-in position sizing and stop-loss management
- **Compliance Reporting**: Daily reports and audit metrics

## Documentation

- `API_DOCUMENTATION.md` - Complete API reference
- `TESTING_GUIDE.md` - Testing instructions
- `TROUBLESHOOTING.md` - Common issues and solutions

## License

Proprietary - All rights reserved
