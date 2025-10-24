# AI Trading Bot - Oliver Vélez Strategy Implementation

A comprehensive AI-assisted trading automation system that integrates TD Ameritrade API with GPT-5 AI validation for implementing Oliver Vélez's intraday trading strategies.

## 🚀 Features

- **TD Ameritrade Integration**: Real-time market data and trade execution
- **Oliver Vélez Strategies**: Implementation of 4 Fantastics, 75% candle rule, RBI/GBI/Whale/Kamikaze setups
- **GPT-5 AI Validation**: AI-powered signal validation using OpenAI's GPT models
- **Risk Management**: Strict risk controls with $300 max loss per trade
- **FastAPI Web Service**: RESTful API for AI ↔ VPS communication
- **Comprehensive Logging**: Detailed trade logs and performance reports
- **Adaptive Optimization**: AI-powered strategy parameter optimization

## 📁 Project Structure

```
AI Trading Bot/
├── core/                    # Core trading engine and strategy logic
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── logger.py           # Logging system
│   ├── td_api.py           # TD Ameritrade API wrapper
│   ├── velez_strategy.py   # Oliver Vélez strategy implementation
│   ├── ai_analyzer.py      # GPT-5 AI signal analyzer
│   ├── trade_executor.py   # Trade execution engine
│   ├── optimization.py     # AI optimization layer
│   └── trading_engine.py   # Main trading orchestrator
├── api/                    # FastAPI web service
│   ├── __init__.py
│   └── main.py            # API endpoints
├── data/                   # Database and reports
├── logs/                   # Runtime logs
├── main.py                 # Main entry point
├── requirements.txt        # Python dependencies
├── setup_env.sh           # VPS setup script
├── env_template.txt       # Environment variables template
└── README.md              # This file
```

## 🛠️ Installation & Setup

### 1. VPS Setup (Ubuntu 22.04)

```bash
# Clone the repository
git clone <repository-url>
cd AI-Trading-Bot

# Make setup script executable
chmod +x setup_env.sh

# Run setup script
./setup_env.sh

# Activate virtual environment
source /opt/ov_trading_env/bin/activate
```

### 2. Environment Configuration

```bash
# Copy environment template
cp env_template.txt .env

# Edit .env file with your credentials
nano .env
```

Required environment variables:
```env
# TD Ameritrade API Configuration
TD_AMERITRADE_CLIENT_ID=your_td_client_id
TD_AMERITRADE_REDIRECT_URI=http://localhost:8080
TD_AMERITRADE_ACCOUNT_ID=your_account_id

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4

# Trading Configuration
MAX_LOSS_PER_TRADE=300
MAX_POSITION_SIZE=1000
RISK_PERCENTAGE=0.02
```

### 3. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt
```

## 🚀 Usage

### Running the Trading Bot

```bash
# Start the main trading engine
python main.py
```

### Running the FastAPI Server

```bash
# Start the API server
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### API Endpoints

- `GET /` - Root endpoint with system status
- `GET /health` - Health check
- `POST /market-data` - Get market data for symbols
- `POST /analyze-signals` - Analyze trading signals
- `POST /validate-signal` - Validate specific signal with AI
- `POST /execute-trade` - Execute trade order
- `GET /account-info` - Get account information
- `GET /positions` - Get current positions
- `GET /daily-report` - Generate daily P&L report
- `POST /optimize-strategy` - Trigger strategy optimization

## 📊 Trading Strategies

### Oliver Vélez Patterns Implemented

1. **4 Fantastics**: Higher high, higher low, higher close, higher open
2. **75% Candle Rule**: Candle body is 75% or more of total range
3. **RBI (Rising Bottom Inside)**: Rising bottom with inside candle
4. **GBI (Great Bottom Inside)**: Enhanced RBI with multiple higher lows
5. **Whale Pattern**: Large volume spike with price breakout
6. **Kamikaze Pattern**: Sharp reversal after significant move

### Risk Management

- Maximum loss per trade: $300
- Position size limits based on account equity
- Stop-loss placement based on pattern analysis
- Cooldown periods between signals for same symbol

## 🤖 AI Integration

### GPT-5 Signal Validation

The system uses OpenAI's GPT models to validate trading signals by:
- Analyzing market context and trend strength
- Evaluating risk management parameters
- Checking for conflicting signals
- Providing confidence scores and recommendations

### Adaptive Optimization

The AI optimization layer:
- Analyzes trading performance metrics
- Identifies optimization opportunities
- Suggests parameter adjustments
- Tracks improvement over time

## 📈 Monitoring & Reports

### Daily Reports

- P&L summary
- Trade execution statistics
- Win rate analysis
- Risk metrics
- Performance optimization suggestions

### Logging

- Comprehensive trade logs
- Error tracking
- Performance metrics
- AI analysis results

## 🔧 Configuration

### Trading Parameters

- `MAX_LOSS_PER_TRADE`: Maximum loss per trade ($300 default)
- `MAX_POSITION_SIZE`: Maximum position size ($1000 default)
- `RISK_PERCENTAGE`: Risk percentage per trade (2% default)

### Market Data

- `MARKET_DATA_REFRESH_INTERVAL`: Refresh interval in minutes
- `WEBSOCKET_ENABLED`: Enable real-time data streaming

## 🚨 Important Notes

### Risk Disclaimer

This software is for educational and research purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results.

### API Limits

- TD Ameritrade API has rate limits
- OpenAI API has usage limits and costs
- Monitor your API usage and costs

### Security

- Never commit API keys to version control
- Use environment variables for all sensitive data
- Regularly rotate API keys
- Monitor account activity

## 🐛 Troubleshooting

### Common Issues

1. **Authentication Errors**: Check TD Ameritrade credentials and OAuth setup
2. **API Rate Limits**: Implement proper rate limiting and retry logic
3. **Insufficient Data**: Ensure market data is available for analysis
4. **Configuration Errors**: Validate all environment variables

### Logs

Check logs in the `./logs/` directory for detailed error information:
```bash
tail -f logs/trading_bot.log
```

## 📞 Support

For issues and questions:
1. Check the logs for error details
2. Verify configuration settings
3. Review API documentation
4. Check system requirements

## 🔄 Updates

To update the system:
1. Pull latest changes from repository
2. Update dependencies: `pip install -r requirements.txt`
3. Restart the trading engine
4. Monitor for any configuration changes

## 📄 License

This project is for educational purposes only. Please ensure compliance with all applicable laws and regulations in your jurisdiction.

---

**⚠️ Disclaimer**: This software is provided as-is for educational purposes. Trading involves substantial risk of loss. Use at your own risk and ensure compliance with all applicable laws and regulations.
