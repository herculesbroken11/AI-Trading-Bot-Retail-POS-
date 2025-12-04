# Project Structure

This project is separated into frontend and backend directories.

## Directory Structure

```
.
├── backend/                    # Backend Flask API
│   ├── api/                   # API endpoints (Flask blueprints)
│   │   ├── __init__.py
│   │   ├── auth.py           # Authentication endpoints
│   │   ├── orders.py         # Trade execution
│   │   ├── quotes.py         # Market data
│   │   ├── positions.py      # Position management
│   │   ├── reports.py        # Reporting
│   │   ├── automation.py     # Automation control
│   │   └── streaming.py      # WebSocket streaming
│   │
│   ├── core/                 # Core trading logic
│   │   ├── __init__.py
│   │   ├── ov_engine.py      # OV strategy engine
│   │   ├── position_manager.py  # Position management
│   │   └── scheduler.py      # Automation scheduler
│   │
│   ├── ai/                   # AI analysis
│   │   ├── __init__.py
│   │   └── analyze.py        # GPT-4o integration
│   │
│   ├── utils/                # Utilities
│   │   ├── __init__.py
│   │   ├── helpers.py        # Helper functions
│   │   ├── logger.py         # Logging setup
│   │   ├── database.py       # Database operations
│   │   └── risk_control.py   # Risk management
│   │
│   ├── data/                 # Data storage
│   │   ├── tokens.json       # OAuth tokens (gitignored)
│   │   ├── trades.csv        # Trade history (gitignored)
│   │   └── logs/             # Application logs (gitignored)
│   │
│   ├── static/               # Static files
│   │   ├── dashboard.html    # Old HTML dashboard (deprecated)
│   │   └── dashboard/        # React dashboard build output
│   │
│   ├── main.py              # Flask application entry point
│   ├── wsgi.py              # Gunicorn WSGI entry point
│   ├── callback.py          # OAuth callback helper
│   ├── exchange.py          # Token exchange helper
│   ├── requirements.txt     # Python dependencies
│   └── README.md            # Backend documentation
│
├── frontend/                 # React frontend
│   ├── src/                 # React source code
│   │   ├── components/      # React components
│   │   ├── services/        # API service layer
│   │   ├── App.jsx          # Main app component
│   │   ├── main.jsx         # Entry point
│   │   └── index.css        # Global styles
│   │
│   ├── index.html           # HTML template
│   ├── package.json         # Node dependencies
│   ├── vite.config.js        # Vite configuration
│   └── README.md            # Frontend documentation
│
├── start.sh                  # Linux/Mac startup script
├── start.bat                 # Windows startup script
├── README.md                 # Main project documentation
└── .gitignore               # Git ignore rules
```

## Key Points

1. **Backend** (`backend/`): All Python/Flask code
   - Run from `backend/` directory: `python main.py`
   - Or use startup scripts from root: `./start.sh` or `start.bat`

2. **Frontend** (`frontend/`): React application
   - Development: `cd frontend && npm run dev`
   - Build: `cd frontend && npm run build`
   - Build output goes to `backend/static/dashboard/`

3. **Data Storage**: All data files in `backend/data/`
   - Tokens, logs, CSV files are gitignored

4. **Static Files**: Served from `backend/static/`
   - React dashboard build in `backend/static/dashboard/`

## Running the Application

### Development

**Backend:**
```bash
cd backend
python main.py
```

**Frontend:**
```bash
cd frontend
npm run dev
```

### Production

**Build frontend:**
```bash
cd frontend
npm run build
```

**Run backend:**
```bash
cd backend
gunicorn -w 4 -b 0.0.0.0:5035 wsgi:application
```

Or use startup scripts from root directory.

