# Backend - Oliver Vélez Trading System

Flask-based backend API for the trading system.

## Structure

```
backend/
├── api/              # API endpoints (Flask blueprints)
│   ├── auth.py       # Authentication endpoints
│   ├── orders.py     # Trade execution
│   ├── quotes.py     # Market data
│   ├── positions.py  # Position management
│   ├── reports.py    # Reporting
│   ├── automation.py  # Automation control
│   └── streaming.py  # WebSocket streaming
│
├── core/             # Core trading logic
│   ├── ov_engine.py  # OV strategy engine
│   ├── position_manager.py  # Position management
│   └── scheduler.py  # Automation scheduler
│
├── ai/               # AI analysis
│   └── analyze.py    # GPT-4o integration
│
├── utils/            # Utilities
│   ├── helpers.py    # Helper functions
│   ├── logger.py     # Logging setup
│   ├── database.py   # Database operations
│   └── risk_control.py  # Risk management
│
├── data/             # Data storage
│   ├── tokens.json   # OAuth tokens
│   ├── trades.csv    # Trade history
│   └── logs/         # Application logs
│
├── static/           # Static files
│   └── dashboard/    # React dashboard build
│
├── main.py           # Flask application
├── wsgi.py           # Gunicorn entry point
└── requirements.txt  # Python dependencies
```

## Setup

1. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Run:
```bash
python main.py
```

## Production Deployment

Use Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5035 wsgi:application
```

## API Documentation

See `../API_DOCUMENTATION.md` for complete API reference.

