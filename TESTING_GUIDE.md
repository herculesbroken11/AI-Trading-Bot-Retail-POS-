# Testing Guide - Development Mode on Ubuntu Server

## 🎯 Testing Overview

This guide will help you test the entire system in development mode (`python main.py`) before moving to production with gunicorn.

---

## 📋 Pre-Testing Checklist

### 1. Server Setup

```bash
# SSH into your Ubuntu server
ssh user@your-server

# Navigate to project directory
cd /path/to/AI-Trading-Bot-Retail-POS-

# Activate virtual environment
source venv/bin/activate

# Verify Python version (should be 3.11+)
python3 --version

# Verify all dependencies installed
pip list | grep -E "flask|requests|pandas|openai|schedule"
```

### 2. Environment Configuration

```bash
# Check .env file exists
ls -la .env

# Verify required variables are set
cat .env | grep -E "SCHWAB|OPENAI|TRADING_WATCHLIST"

# Required variables:
# - SCHWAB_CLIENT_ID
# - SCHWAB_CLIENT_SECRET
# - SCHWAB_REDIRECT_URI
# - OPENAI_API_KEY
# - TRADING_WATCHLIST (e.g., AAPL,MSFT,GOOGL)
```

### 3. Directory Structure

```bash
# Verify all directories exist
ls -la
# Should see: core/, api/, ai/, data/, utils/, static/

# Check data directory is writable
mkdir -p data/logs
chmod 755 data
```

---

## 🧪 Step-by-Step Testing

### Test 1: Start Server (Development Mode)

```bash
# Start Flask in development mode
python3 main.py

# Expected output:
# Starting Flask server on 0.0.0.0:5035
# Dashboard available at: http://0.0.0.0:5035/dashboard
```

**✅ Success Criteria:**
- Server starts without errors
- No import errors
- Server listening on port 5035
- Can access `http://your-server:5035/health`

**Test it:**
```bash
# In another terminal
curl http://localhost:5035/health
# Should return: {"status": "healthy", "service": "trading-system"}
```

---

### Test 2: Authentication Flow

#### 2.1 Check Auth Status (Before Login)

```bash
curl http://localhost:5035/auth/status
```

**Expected:** `{"authenticated": false}` or `{"error": "Not authenticated"}`

#### 2.2 Initiate OAuth Login

```bash
# Get login URL
curl http://localhost:5035/auth/login

# Or open in browser:
# http://your-server:5035/auth/login
```

**Expected Response:**
```json
{
  "message": "Please complete authentication in your browser",
  "auth_url": "https://api.schwabapi.com/v1/oauth/authorize?..."
}
```

#### 2.3 Complete Authentication

1. Open the `auth_url` in browser
2. Login with Schwab credentials
3. Authorize the application
4. You'll be redirected back with a code

**Check callback:**
```bash
# The callback should automatically save tokens
# Check if tokens were saved:
ls -la data/tokens.json

# View tokens (first few chars only):
cat data/tokens.json | head -c 100
```

#### 2.4 Verify Authentication

```bash
curl http://localhost:5035/auth/status
```

**Expected:** `{"authenticated": true, "expires_in": 1800}`

**✅ Success Criteria:**
- OAuth flow completes
- `data/tokens.json` file created
- Auth status shows authenticated
- Automation scheduler started automatically (check logs)

---

### Test 3: Market Data Endpoints

#### 3.1 Get Real-Time Quote

```bash
curl http://localhost:5035/quotes/AAPL
```

**Expected:** JSON with quote data for AAPL

#### 3.2 Get Historical Data

```bash
curl "http://localhost:5035/quotes/historical/AAPL?periodType=day&period=1&frequencyType=minute&frequency=5"
```

**Expected:** JSON with historical candles

#### 3.3 Get Market Analysis (Full OV Analysis)

```bash
curl http://localhost:5035/quotes/analyze/AAPL
```

**Expected:** JSON with:
- Market summary (price, SMAs, ATR, RSI, volume)
- Identified setup (if any)
- 4 Fantastics status
- 75% Candle Rule status

**✅ Success Criteria:**
- All endpoints return data (not 401/403 errors)
- Analysis includes all indicators
- Setup identification works

---

### Test 4: Account & Position Endpoints

#### 4.1 Get Trading Accounts

```bash
curl http://localhost:5035/orders/accounts
```

**Expected:** JSON array with account information

**Note:** If you get 401, token may need refresh. Check logs.

#### 4.2 Get Positions

```bash
curl http://localhost:5035/orders/positions
```

**Expected:** JSON with current positions (may be empty if no positions)

#### 4.3 Get All Orders

```bash
# Replace YOUR_ACCOUNT_ID with actual account ID from step 4.1
curl "http://localhost:5035/orders/all-orders?accountId=YOUR_ACCOUNT_ID"
```

**Expected:** JSON array with orders

**✅ Success Criteria:**
- Can retrieve account information
- Can retrieve positions
- Can retrieve orders
- No 401/403 errors

---

### Test 5: OV Strategy Engine (Advanced Rules)

#### 5.1 Test 4 Fantastics

```bash
# Get analysis for a symbol
curl http://localhost:5035/quotes/analyze/AAPL > analysis.json

# Check if 4 Fantastics are in response
cat analysis.json | grep -i "fantastic"
```

**Expected:** Response includes `fantastics` object with all 4 conditions

#### 5.2 Test Setup Identification

```bash
# Check what setup was identified
cat analysis.json | grep -i "setup\|type"
```

**Expected:** Setup type (WHALE_LONG, RBI_LONG, GBI_LONG, etc.) or null if no setup

**✅ Success Criteria:**
- 4 Fantastics are calculated
- Setup types are identified correctly
- 75% Candle Rule is checked

---

### Test 6: AI Integration

#### 6.1 Test AI Analysis

The AI analysis happens automatically when you call `/quotes/analyze/<symbol>`. 

**Check logs for AI activity:**
```bash
# In the terminal running main.py, you should see:
# "AI analysis completed for AAPL: BUY" or similar
```

#### 6.2 Verify AI Signal Format

```bash
# The analyze endpoint should return AI signal if setup found
curl http://localhost:5035/quotes/analyze/AAPL | jq '.ai_signal'
```

**Expected:** JSON with:
- `action`: "BUY", "SELL", or "HOLD"
- `entry`: entry price
- `stop`: stop loss
- `target`: take profit
- `confidence`: 0.0-1.0
- `reasoning`: explanation

**✅ Success Criteria:**
- AI analysis completes without errors
- Signal format is correct
- Confidence score is provided
- Reasoning is included

---

### Test 7: Automation Scheduler

#### 7.1 Check Automation Status

```bash
curl http://localhost:5035/automation/status
```

**Expected:**
```json
{
  "status": "running",
  "running": true,
  "watchlist": ["AAPL", "MSFT", "GOOGL"],
  "market_hours": true/false
}
```

#### 7.2 Verify Scheduler is Running

**Check logs:**
```bash
# In terminal running main.py, look for:
# "Starting automated market analysis..."
# "Market analysis complete"
```

**Or check log files:**
```bash
tail -f data/logs/trading_*.log
```

**Expected:** Logs show:
- Scheduler starting
- Market analysis every 5 minutes (during market hours)
- Setup identification
- AI analysis

#### 7.3 Test Manual Start/Stop

```bash
# Stop automation
curl -X POST http://localhost:5035/automation/stop

# Check status (should be stopped)
curl http://localhost:5035/automation/status

# Start automation
curl -X POST http://localhost:5035/automation/start

# Check status (should be running)
curl http://localhost:5035/automation/status
```

**✅ Success Criteria:**
- Automation starts automatically after auth
- Status endpoint works
- Can manually start/stop
- Scheduler runs during market hours

---

### Test 8: Position Management

#### 8.1 Get Active Positions

```bash
curl http://localhost:5035/positions/active
```

**Expected:** JSON array (may be empty if no positions)

#### 8.2 Test Position Updates

```bash
# Update positions with current prices
curl -X POST http://localhost:5035/positions/update-prices \
  -H "Content-Type: application/json" \
  -d '{"prices": {"AAPL": 150.00}}'
```

**Expected:** `{"status": "updated"}`

**✅ Success Criteria:**
- Can retrieve active positions
- Can update positions
- Position tracking works

---

### Test 9: Order Execution (Paper Trading Recommended)

⚠️ **WARNING:** This will place REAL orders. Test with small amounts or paper trading first!

#### 9.1 Test Signal Execution

```bash
# Get your account ID first
ACCOUNT_ID=$(curl -s http://localhost:5035/orders/accounts | jq -r '.[0].accountNumber')

# Execute a test signal (SMALL AMOUNT!)
curl -X POST http://localhost:5035/orders/signal \
  -H "Content-Type: application/json" \
  -d "{
    \"symbol\": \"AAPL\",
    \"action\": \"BUY\",
    \"entry\": 150.00,
    \"stop\": 145.00,
    \"target\": 160.00,
    \"setup_type\": \"TEST\",
    \"accountId\": \"$ACCOUNT_ID\",
    \"position_size\": 1
  }"
```

**Expected:** Order confirmation JSON

#### 9.2 Verify Order Was Placed

```bash
curl "http://localhost:5035/orders/all-orders?accountId=$ACCOUNT_ID"
```

**Expected:** Your test order appears in the list

**✅ Success Criteria:**
- Order execution works
- Order appears in account
- Risk controls enforced ($300 max)

---

### Test 10: Reporting

#### 10.1 Generate Daily Report

```bash
# Get account ID
ACCOUNT_ID=$(curl -s http://localhost:5035/orders/accounts | jq -r '.[0].accountNumber')

# Generate report
curl "http://localhost:5035/reports/daily?accountId=$ACCOUNT_ID"
```

**Expected:** JSON with daily P&L, trades, compliance metrics

#### 10.2 Check Trade History

```bash
curl "http://localhost:5035/reports/trades?accountId=$ACCOUNT_ID"
```

**Expected:** JSON array with trade history

**✅ Success Criteria:**
- Reports generate successfully
- Trade history is accurate
- P&L calculations correct

---

### Test 11: Dashboard

#### 11.1 Access Dashboard

Open in browser:
```
http://your-server:5035/dashboard
```

**Expected:**
- Dashboard loads
- Shows automation status
- Shows active positions (if any)
- Auto-refreshes every 30 seconds

**✅ Success Criteria:**
- Dashboard accessible
- All widgets load
- Real-time updates work

---

### Test 12: Auto-Close at 4 PM ET

#### 12.1 Test Auto-Close Logic

```bash
# Check if auto-close time detection works
# This is tested by checking the scheduler logs at 4 PM ET

# Or manually trigger (for testing):
curl -X POST http://localhost:5035/positions/close-all
```

**Expected:** All positions closed

**✅ Success Criteria:**
- Auto-close triggers at 4 PM ET
- All positions closed
- Logs show close activity

---

## 🔍 Comprehensive Test Script

Create a test script to run all tests:

```bash
#!/bin/bash
# save as test_all.sh

BASE_URL="http://localhost:5035"

echo "=== Testing Trading System ==="

echo "1. Health Check..."
curl -s $BASE_URL/health | jq .

echo -e "\n2. Auth Status..."
curl -s $BASE_URL/auth/status | jq .

echo -e "\n3. Market Data..."
curl -s $BASE_URL/quotes/AAPL | jq . | head -20

echo -e "\n4. Market Analysis..."
curl -s $BASE_URL/quotes/analyze/AAPL | jq . | head -30

echo -e "\n5. Accounts..."
curl -s $BASE_URL/orders/accounts | jq .

echo -e "\n6. Automation Status..."
curl -s $BASE_URL/automation/status | jq .

echo -e "\n7. Active Positions..."
curl -s $BASE_URL/positions/active | jq .

echo -e "\n=== Tests Complete ==="
```

Make it executable and run:
```bash
chmod +x test_all.sh
./test_all.sh
```

---

## 📊 Testing Checklist

Use this checklist to track your testing:

- [ ] Server starts without errors
- [ ] Health endpoint works
- [ ] Authentication flow completes
- [ ] Tokens saved correctly
- [ ] Market data endpoints work
- [ ] Historical data retrieval works
- [ ] Market analysis works
- [ ] 4 Fantastics calculated
- [ ] Setup identification works
- [ ] AI analysis completes
- [ ] Account endpoints work
- [ ] Position endpoints work
- [ ] Automation scheduler starts
- [ ] Automation status works
- [ ] Position management works
- [ ] Dashboard accessible
- [ ] Reports generate
- [ ] Logs are created
- [ ] Error handling works

---

## 🐛 Common Issues & Solutions

### Issue: "Not authenticated" errors

**Solution:**
```bash
# Re-authenticate
curl http://localhost:5035/auth/login
# Follow the auth_url in response
```

### Issue: "Module not found" errors

**Solution:**
```bash
# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Port 5035 already in use

**Solution:**
```bash
# Find process using port
sudo lsof -i :5035

# Kill process
sudo kill -9 <PID>

# Or change port in .env
# FLASK_PORT=5036
```

### Issue: Token expired (401 errors)

**Solution:**
```bash
# Refresh token
curl -X POST http://localhost:5035/auth/refresh
```

### Issue: AI analysis fails

**Solution:**
```bash
# Check OPENAI_API_KEY in .env
cat .env | grep OPENAI

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## 📝 Testing Log Template

Keep a testing log:

```
Date: YYYY-MM-DD
Tester: Your Name

Test Results:
- Authentication: ✅/❌
- Market Data: ✅/❌
- Order Execution: ✅/❌
- Automation: ✅/❌
- Position Management: ✅/❌
- Reporting: ✅/❌

Issues Found:
1. [Issue description]
   Solution: [Solution applied]

Notes:
[Any additional notes]
```

---

## ✅ Ready for Gunicorn?

After all tests pass, you're ready to move to production with gunicorn!

**Next Steps:**
1. All tests pass ✅
2. Review `GUNICORN_DEPLOYMENT.md` (will create)
3. Configure gunicorn
4. Set up systemd service
5. Deploy to production

---

## 🎯 Quick Test Commands

```bash
# Quick health check
curl http://localhost:5035/health

# Quick auth check
curl http://localhost:5035/auth/status

# Quick market test
curl http://localhost:5035/quotes/analyze/AAPL

# Quick automation check
curl http://localhost:5035/automation/status
```

**All should return valid JSON responses!**

