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

**Expected:** JSON with historical candles, summary, and setup:
```json
{
  "symbol": "AAPL",
  "candles_count": 390,
  "summary": {
    "current_price": 273.67,
    "sma_8": 272.50,
    "sma_20": 270.30,
    "sma_200": 265.00,
    "atr_14": 2.5,
    "rsi_14": 55.0,
    "trend": "BULLISH"
  },
  "setup": {...}
}
```

**Note:**
- System automatically detects correct column order from Schwab API response
- If insufficient data (< 200 candles), you'll get a warning but still receive available data
- Column misalignment issues are automatically fixed

#### 3.3 Get Market Analysis (Full OV Analysis)

```bash
curl http://localhost:5035/quotes/analyze/AAPL
```

**Expected:** JSON with:
- Market summary (price, SMAs, ATR, RSI, volume)
- Identified setup (if any)
- 4 Fantastics status
- 75% Candle Rule status

**Example Response:**
```json
{
  "symbol": "AAPL",
  "data_points": 390,
  "summary": {
    "current_price": 273.67,
    "sma_8": 272.50,
    "sma_20": 270.30,
    "sma_200": 265.00,
    "atr_14": 2.5,
    "rsi_14": 55.0,
    "volume": 5345634,
    "trend": "BULLISH",
    "above_sma200": true
  },
  "setup": {
    "type": "PULLBACK_LONG",
    "direction": "LONG",
    "entry_price": 273.50,
    "stop_loss": 271.00,
    "take_profit": 278.00,
    "confidence": 0.75
  }
}
```

**Note:**
- Prices should be in reasonable range (e.g., $1-$1000 for most stocks)
- If you see prices like 805517, that indicates column misalignment (now auto-fixed)
- Volume should be reasonable numbers, not timestamps

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
# Positions endpoint auto-detects account if not provided
curl http://localhost:5035/orders/positions

# Or specify account explicitly
curl "http://localhost:5035/orders/positions?accountId=YOUR_ACCOUNT_ID"
```

**Expected:** JSON with current positions:
```json
{
  "positions": [],
  "account_id": "18056335",
  "count": 0
}
```

**Note:** 
- Uses Schwab API: `GET /accounts/{accountNumber}?fields=positions`
- If no `accountId` is provided, the system automatically uses the first account
- Empty array `[]` means no open positions (this is normal)
- Positions are included in account details when `fields=positions` is specified

#### 4.3 Get All Orders

```bash
# Get orders for specific account (date parameters optional)
curl "http://localhost:5035/orders/all-orders?accountId=18056335"

# Get orders for specific account with date filter
curl "http://localhost:5035/orders/all-orders?accountId=18056335&fromEnteredTime=2024-10-20T00:00:00.000Z&toEnteredTime=2024-11-20T23:59:59.000Z"

# Get all orders for ALL accounts (date parameters REQUIRED)
curl "http://localhost:5035/orders/all-orders?fromEnteredTime=2024-10-20T00:00:00.000Z&toEnteredTime=2024-11-20T23:59:59.000Z&maxResults=100"
```

**Expected:** JSON array with orders

**Note:**
- For account-specific orders: date parameters are optional
- For all-accounts orders: `fromEnteredTime` and `toEnteredTime` are REQUIRED
- Date format: ISO-8601 `yyyy-MM-dd'T'HH:mm:ss.SSSZ`
- Maximum date range: 60 days for all-accounts, 1 year for account-specific

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

#### 9.1 Preview Order (Recommended First Step)

```bash
# Get your account ID first
ACCOUNT_ID=$(curl -s http://localhost:5035/orders/accounts | jq -r '.[0].securitiesAccount.accountNumber')

# Preview order before placing (SMALL AMOUNT!)
curl -X POST http://localhost:5035/orders/$ACCOUNT_ID/preview \
  -H "Content-Type: application/json" \
  -d "{
    \"symbol\": \"AAPL\",
    \"action\": \"BUY\",
    \"quantity\": 1,
    \"orderType\": \"LIMIT\",
    \"price\": 150.00
  }"
```

**Expected:** Preview response with validation results:
```json
{
  "message": "Order preview generated",
  "preview": {
    "orderValidationResult": {
      "rejects": [],
      "warns": [],
      "reviews": []
    },
    "orderStrategy": {
      "projectedCommission": 0,
      "projectedBuyingPower": 0
    }
  },
  "summary": {
    "valid": true,
    "has_warnings": false,
    "projected_commission": 0
  }
}
```

#### 9.2 Test Signal Execution

```bash
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

**Expected:** Order confirmation with 201 status:
```json
{
  "message": "Order placed successfully",
  "status": "PLACED",
  "location": "/accounts/18056335/orders/123456",
  "correlation_id": "abc-123",
  "order": null
}
```

**Note:**
- Order placement returns 201 (Created) status code
- Response body is empty (per Schwab API)
- `Location` header contains link to created order
- `Schwab-Client-CorrelId` header contains correlation ID

#### 9.3 Verify Order Was Placed

```bash
# Get orders for account (with date range)
curl "http://localhost:5035/orders/all-orders?accountId=$ACCOUNT_ID&fromEnteredTime=2024-11-20T00:00:00.000Z&toEnteredTime=2024-11-20T23:59:59.000Z"
```

**Expected:** Your test order appears in the list

**✅ Success Criteria:**
- Order execution works
- Order appears in account
- Risk controls enforced ($300 max)

---

### Test 10: Transactions

#### 10.1 Get Transactions

```bash
# Get account ID
ACCOUNT_ID=$(curl -s http://localhost:5035/orders/accounts | jq -r '.[0].securitiesAccount.accountNumber')

# Get transactions (startDate, endDate, and types are REQUIRED)
curl "http://localhost:5035/orders/$ACCOUNT_ID/transactions?startDate=2024-10-20T00:00:00.000Z&endDate=2024-11-20T23:59:59.000Z&types=TRADE"

# Get multiple transaction types
curl "http://localhost:5035/orders/$ACCOUNT_ID/transactions?startDate=2024-10-20T00:00:00.000Z&endDate=2024-11-20T23:59:59.000Z&types=TRADE,DIVIDEND_OR_INTEREST"

# Filter by symbol
curl "http://localhost:5035/orders/$ACCOUNT_ID/transactions?startDate=2024-10-20T00:00:00.000Z&endDate=2024-11-20T23:59:59.000Z&types=TRADE&symbol=AAPL"
```

**Expected:** JSON with transactions:
```json
{
  "transactions": [],
  "account_id": "18056335",
  "count": 0,
  "note": "Maximum 3000 transactions returned, maximum date range is 1 year"
}
```

**Note:**
- `startDate` and `endDate` are REQUIRED (ISO-8601 format)
- `types` parameter is REQUIRED (comma-separated)
- Maximum 3000 transactions per response
- Maximum date range is 1 year
- Available types: TRADE, DIVIDEND_OR_INTEREST, ACH_RECEIPT, etc.

#### 10.2 Get Specific Transaction

```bash
# Get specific transaction by ID
curl "http://localhost:5035/orders/$ACCOUNT_ID/transactions/123456"
```

**Expected:** JSON with transaction details

**✅ Success Criteria:**
- Can retrieve transactions with required parameters
- Date format validation works
- Transaction types filter correctly

---

### Test 11: Reporting

#### 11.1 Generate Daily Report

```bash
# Get account ID
ACCOUNT_ID=$(curl -s http://localhost:5035/orders/accounts | jq -r '.[0].securitiesAccount.accountNumber')

# Generate report
curl "http://localhost:5035/reports/daily?accountId=$ACCOUNT_ID"
```

**Expected:** JSON with daily P&L, trades, compliance metrics

#### 11.2 Check Trade History

```bash
curl "http://localhost:5035/reports/trades?accountId=$ACCOUNT_ID"
```

**Expected:** JSON array with trade history

**✅ Success Criteria:**
- Reports generate successfully
- Trade history is accurate
- P&L calculations correct

---

### Test 12: Dashboard

#### 12.1 Access Dashboard

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

### Test 13: Auto-Close at 4 PM ET

#### 13.1 Test Auto-Close Logic

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

echo -e "\n6. Positions (auto-detects account)..."
curl -s $BASE_URL/orders/positions | jq .

echo -e "\n7. Automation Status..."
curl -s $BASE_URL/automation/status | jq .

echo -e "\n8. Active Positions..."
curl -s $BASE_URL/positions/active | jq .

echo -e "\n9. Preview Order (example)..."
ACCOUNT_ID=$(curl -s $BASE_URL/orders/accounts | jq -r '.[0].securitiesAccount.accountNumber')
echo "Account ID: $ACCOUNT_ID"

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
- [ ] Position endpoints work (auto-detects account, uses fields=positions)
- [ ] Historical data column detection works
- [ ] Prices are in correct range (not misaligned)
- [ ] Orders endpoint works (with correct date parameters)
- [ ] Transactions endpoint works (with required parameters)
- [ ] Order placement returns 201 with Location header
- [ ] Preview order shows validation results
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

# Or re-authenticate
curl http://localhost:5035/auth/login
# Follow the auth_url in response
```

### Issue: Positions endpoint returns 404

**Solution:**
- This has been fixed! The endpoint now uses `GET /accounts/{accountNumber}?fields=positions`
- If you still get 404, check that accountId is correct
- The endpoint will return an empty array `[]` if no positions exist
- Verify account: `curl http://localhost:5035/orders/accounts`

### Issue: Historical data shows incorrect prices (e.g., 805517 instead of ~275)

**Solution:**
- This has been fixed! The system now auto-detects column order
- If you still see this, check server logs for "Auto-detected column order"
- The system automatically identifies datetime, volume, and price columns
- Try the endpoint again - it should work correctly now

### Issue: AI analysis fails

**Solution:**
```bash
# Check OPENAI_API_KEY in .env
cat .env | grep OPENAI

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# If you see "Client.__init__() got an unexpected keyword argument 'proxies'"
# Update OpenAI library:
pip install --upgrade "openai>=1.12.0"
```

### Issue: Scheduler fails to start with import errors

**Solution:**
```bash
# Check for import errors in logs
tail -f data/logs/*.log | grep -i "import\|error"

# Common fixes:
# 1. Ensure all dependencies installed
pip install -r requirements.txt

# 2. Check virtual environment is activated
which python3
source venv/bin/activate

# 3. Verify all modules exist
ls -la core/ api/ ai/ utils/
```

### Issue: Transactions endpoint returns 400 error

**Solution:**
```bash
# Transactions endpoint requires startDate, endDate, and types
# All three parameters are REQUIRED

# Correct usage:
curl "http://localhost:5035/orders/18056335/transactions?startDate=2024-10-20T00:00:00.000Z&endDate=2024-11-20T23:59:59.000Z&types=TRADE"

# Date format must be ISO-8601: yyyy-MM-dd'T'HH:mm:ss.SSSZ
# Available types: TRADE, DIVIDEND_OR_INTEREST, ACH_RECEIPT, etc.
```

### Issue: Orders endpoint returns 400 error

**Solution:**
```bash
# For GET /orders (all accounts), date parameters are REQUIRED
# For account-specific orders, dates are optional

# All accounts (requires dates):
curl "http://localhost:5035/orders/all-orders?fromEnteredTime=2024-10-20T00:00:00.000Z&toEnteredTime=2024-11-20T23:59:59.000Z"

# Account-specific (dates optional):
curl "http://localhost:5035/orders/all-orders?accountId=18056335"
```

### Issue: Order placement returns empty response

**Solution:**
- This is normal! Schwab API returns 201 with empty body
- Check the `Location` header in response - it contains the order link
- The `correlation_id` is in the `Schwab-Client-CorrelId` header
- Use the Location URL to get order details

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
2. Verify all endpoints work correctly
3. Check logs for any errors
4. Test with actual account (small amounts)
5. Configure gunicorn
6. Set up systemd service
7. Deploy to production

---

## 📌 Recent Fixes & Updates

### Fixed Issues:
1. **Positions Endpoint (404 Error)**
   - Fixed: Now uses `GET /accounts/{accountNumber}?fields=positions` (official API method)
   - Auto-detects account if not provided
   - Returns empty array if no positions (not an error)

2. **Historical Data Column Misalignment**
   - Fixed: Auto-detects column order from Schwab API response
   - Handles both dictionary and array candle formats
   - Validates prices are in reasonable range

3. **OpenAI Client Initialization**
   - Fixed: Lazy initialization to prevent startup errors
   - Graceful fallback if AI analyzer fails
   - Updated to OpenAI library >= 1.12.0

4. **Scheduler Import Errors**
   - Fixed: Removed invalid imports
   - Uses helper functions instead of Flask route handlers
   - Direct API calls for better performance

5. **Order Payload Structure**
   - Fixed: Now matches official Schwab API Order Object structure
   - Includes positionEffect, quantityType, taxLotMethod fields
   - Proper handling of LIMIT and STOP orders

6. **Order Placement Response**
   - Fixed: Handles 201 status code with empty response body
   - Extracts Location header (link to created order)
   - Extracts Schwab-Client-CorrelId header

7. **Transactions Endpoint**
   - Fixed: Now requires startDate, endDate, and types parameters
   - Validates ISO-8601 date format
   - Provides clear error messages with examples

8. **Orders Endpoint**
   - Fixed: Requires date parameters for GET /orders (all accounts)
   - Optional dates for account-specific orders
   - Validates date range (60 days for all-accounts, 1 year for account-specific)

### API Endpoint Updates:
- `/orders/positions` - Uses `GET /accounts/{accountNumber}?fields=positions` (official API method)
- `/orders/all-orders` - Requires date parameters for all-accounts endpoint
- `/orders/<account_id>/transactions` - Requires startDate, endDate, and types parameters
- `/orders/<account_id>/preview` - Enhanced with validation summary extraction
- `/orders/place` and `/orders/signal` - Handle 201 response with Location header
- `/quotes/historical/<symbol>` - Auto-detects column order, handles insufficient data
- `/quotes/analyze/<symbol>` - Improved error handling, better data validation

### Order Payload Updates:
- Matches official Schwab API Order Object structure
- Includes positionEffect, quantityType, taxLotMethod fields
- Supports optional fields (session, duration, specialInstruction, etc.)
- Proper handling of LIMIT and STOP orders with price link fields

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

# Quick positions check (auto-detects account)
curl http://localhost:5035/orders/positions

# Quick orders check (account-specific, no dates needed)
ACCOUNT_ID=$(curl -s http://localhost:5035/orders/accounts | jq -r '.[0].securitiesAccount.accountNumber')
curl "http://localhost:5035/orders/all-orders?accountId=$ACCOUNT_ID"

# Quick transactions check (requires dates and types)
curl "http://localhost:5035/orders/$ACCOUNT_ID/transactions?startDate=2024-11-01T00:00:00.000Z&endDate=2024-11-20T23:59:59.000Z&types=TRADE"
```

**All should return valid JSON responses!**

**Note:** 
- Positions endpoint auto-detects account
- Orders endpoint works without dates for account-specific queries
- Transactions endpoint requires startDate, endDate, and types

