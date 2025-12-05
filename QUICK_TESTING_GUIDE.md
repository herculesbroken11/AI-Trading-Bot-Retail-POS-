Quick Testing Guide - Oliver Vélez Trading System

This guide will help you test the system quickly and verify all functionality.

Prerequisites

1. Server Access: SSH access to your Ubuntu server
2. Domain/URL: Your domain should be configured (e.g., traidingov.cloud)
3. Schwab API Credentials: Client ID, Client Secret, and Redirect URI

Step 1: Initial Setup & Authentication

1.1 Configure Environment Variables

``bash
cd /home/ubuntu/AI-Trading-Bot-Retail-POS-/backend
nano .env
`

Required Variables:
`bash
Schwab API
SCHWAB_CLIENT_ID=your_client_id_here
SCHWAB_CLIENT_SECRET=your_client_secret_here
SCHWAB_REDIRECT_URI=https://traidingov.cloud

OpenAI (for AI validation)
OPENAI_API_KEY=your_openai_key_here

Trading Configuration
TRADING_WATCHLIST=AAPL,MSFT,GOOGL,TSLA,NVDA
MAX_RISK_PER_TRADE=300
AUTO_START_SCHEDULER=false

Flask
FLASK_PORT=5035
FLASK_HOST=0.0.0.0
FLASK_DEBUG=false
`

1.2 Start the Services

`bash
Start Gunicorn service
sudo systemctl start trading-system
sudo systemctl status trading-system

Check Nginx
sudo systemctl status nginx
`

1.3 Authenticate with Schwab

1. Open your browser and go to: https://traidingov.cloud/auth/login
2. You'll be redirected to Schwab's login page
3. Log in with your Schwab credentials
4. Authorize the application
5. You'll be redirected back and tokens will be saved automatically

Verify Authentication:
`bash
Check if tokens were saved
cat /home/ubuntu/AI-Trading-Bot-Retail-POS-/backend/data/tokens.json
`

Step 2: Test API Endpoints

2.1 Health Check

`bash
curl https://traidingov.cloud/health
`

Expected Response:
`json
{
  "status": "healthy",
  "service": "trading-system"
}
`

2.2 Authentication Status

`bash
curl https://traidingov.cloud/auth/status
`

Expected Response:
`json
{
  "authenticated": true,
  "token_valid": true
}
`

2.3 Get Trading Accounts

`bash
curl https://traidingov.cloud/orders/accounts
`

Expected Response: List of your trading accounts

2.4 Get Market Quotes

`bash
curl "https://traidingov.cloud/quotes/AAPL"
`

Expected Response: Current quote data for AAPL

2.5 Get Historical Data

`bash
curl "https://traidingov.cloud/quotes/historical/AAPL?periodType=day&period=1&frequencyType=minute&frequency=5"
`

Expected Response: Historical candlestick data

Step 3: Test Dashboard

3.1 Access Dashboard

1. Open browser: https://traidingov.cloud/dashboard/
2. Verify you can see:
   - Header with system name
   - Automation Control panel
   - Account Summary
   - System Health indicators
   - Positions Table
   - Daily Report section
   - Optimization Panel

3.2 Test Dashboard Features

Automation Control:
- Click "Start Automation" - should show "Running" status
- Click "Stop Automation" - should show "Stopped" status

Account Summary:
- Should display account balance, buying power, etc.

Positions:
- Should show any open positions (if you have any)

Daily Report:
- Click "Refresh Report" - should load daily P&L data

Optimization Panel:
- Should display performance metrics
- Click "Refresh" to load latest data

Step 4: Test Trading Functionality

4.1 Get Active Positions

`bash
curl https://traidingov.cloud/positions/active
`

4.2 Test Order Preview (Dry Run)

`bash
curl -X POST https://traidingov.cloud/orders/18056335/preview \
  -H "Content-Type: application/json" \
  -d '{
    "orderType": "MARKET",
    "session": "NORMAL",
    "duration": "DAY",
    "orderStrategyType": "SINGLE",
    "orderLegCollection": [{
      "instruction": "BUY",
      "quantity": 1,
      "instrument": {
        "symbol": "AAPL",
        "assetType": "EQUITY"
      }
    }]
  }'
`

Note: Replace 18056335 with your actual account number

4.3 Test Automation Status

`bash
curl https://traidingov.cloud/automation/status
`

Expected Response:
`json
{
  "status": "stopped",
  "running": false,
  "watchlist": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
}
`

Step 5: Test Reports

5.1 Daily Report

`bash
curl "https://traidingov.cloud/reports/daily?accountId=18056335"
`

Note: Replace 18056335 with your actual account number

Expected Response: Daily P&L report with trades and AI summary

5.2 Compliance Report

`bash
curl "https://traidingov.cloud/reports/compliance?start_date=2024-01-01&end_date=2024-01-31"
`

Step 6: Test Optimization (Phase 7)

6.1 Performance Analysis

`bash
curl "https://traidingov.cloud/optimization/performance?days=30"
`

6.2 Setup Weights

`bash
curl https://traidingov.cloud/optimization/setup-weights
`

6.3 Optimized Parameters

`bash
curl https://traidingov.cloud/optimization/parameters
`

6.4 Optimization Summary

`bash
curl https://traidingov.cloud/optimization/summary
`

Step 7: Test Automation (Optional - Use with Caution)

WARNING: Only test automation if you want the system to actually trade!

7.1 Start Automation

`bash
curl -X POST https://traidingov.cloud/automation/start
`

Expected Response:
`json
{
  "status": "started",
  "watchlist": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
}
`

7.2 Monitor Automation

`bash
Check status
curl https://traidingov.cloud/automation/status

View logs
sudo journalctl -u trading-system -f
`

7.3 Stop Automation

`bash
curl -X POST https://traidingov.cloud/automation/stop
`

Step 8: Verify Logs

8.1 Check Gunicorn Logs

`bash
View service logs
sudo journalctl -u trading-system -f

View error logs
tail -f /home/ubuntu/AI-Trading-Bot-Retail-POS-/backend/logs/gunicorn-error.log

View access logs
tail -f /home/ubuntu/AI-Trading-Bot-Retail-POS-/backend/logs/gunicorn-access.log
`

8.2 Check Nginx Logs

`bash
Error logs
sudo tail -f /var/log/nginx/traidingov-error.log

Access logs
sudo tail -f /var/log/nginx/traidingov-access.log
`

Step 9: Browser Testing

9.1 Test All Dashboard Features

1. Open: https://traidingov.cloud/dashboard/
2. Test each panel:
   - Automation Control: Start/Stop buttons
   - Account Summary: Should show account data
   - System Health: Should show green indicators
   - Positions: Should list any open positions
   - Daily Report: Should load when you click refresh
   - Optimization Panel: Should show performance data

9.2 Test API from Browser Console

Open browser console (F12) and test:

`javascript
// Test API calls
fetch('https://traidingov.cloud/health')
  .then(r => r.json())
  .then(console.log)

fetch('https://traidingov.cloud/auth/status')
  .then(r => r.json())
  .then(console.log)

fetch('https://traidingov.cloud/automation/status')
  .then(r => r.json())
  .then(console.log)
`

Common Issues & Solutions

Issue: 404 Errors on API Endpoints

Solution: Check Nginx configuration - it should proxy / to Flask, not /api

`bash
sudo nginx -t
sudo systemctl reload nginx
`

Issue: Authentication Fails

Solution: 
1. Check .env file has correct credentials
2. Verify redirect URI matches in Schwab developer portal
3. Try re-authenticating: https://traidingov.cloud/auth/login

Issue: Dashboard Not Loading

Solution:
1. Check if frontend is built: ls -la /home/ubuntu/AI-Trading-Bot-Retail-POS-/frontend/dist
2. Rebuild if needed: cd frontend && npm run build
3. Check Nginx permissions: sudo chown -R ubuntu:www-data frontend/dist

Issue: Gunicorn Not Starting

Solution:
`bash
Check status
sudo systemctl status trading-system

Check logs
sudo journalctl -u trading-system -n 50

Fix permissions
chmod +x /home/ubuntu/AI-Trading-Bot-Retail-POS-/backend/venv/bin/gunicorn
`

Testing Checklist

- [ ] Health endpoint responds
- [ ] Authentication works (can log in to Schwab)
- [ ] Can get account information
- [ ] Can get market quotes
- [ ] Dashboard loads correctly
- [ ] All dashboard panels display data
- [ ] Automation can start/stop
- [ ] Reports can be generated
- [ ] Optimization endpoints work
- [ ] Logs are being written
- [ ] No errors in browser console
- [ ] No errors in server logs

Quick Test Script

Save this as test.sh and run it:

`bash
!/bin/bash

BASE_URL="https://traidingov.cloud"

echo "Testing Health..."
curl -s "$BASE_URL/health" | jq .

echo -e "\nTesting Auth Status..."
curl -s "$BASE_URL/auth/status" | jq .

echo -e "\nTesting Accounts..."
curl -s "$BASE_URL/orders/accounts" | jq .

echo -e "\nTesting Quote..."
curl -s "$BASE_URL/quotes/AAPL" | jq .

echo -e "\nTesting Automation Status..."
curl -s "$BASE_URL/automation/status" | jq .

echo -e "\nAll tests complete!"
`

Run with: bash test.sh

Need Help?

If you encounter any issues:
1. Check the logs (Step 8)
2. Review the troubleshooting section
3. Verify all environment variables are set correctly
4. Ensure services are running: sudo systemctl status trading-system nginx`

Ready to Test? Start with Step 1 (Authentication) and work through each step sequentially.


