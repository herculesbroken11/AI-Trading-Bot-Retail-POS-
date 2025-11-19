# Complete API Documentation - Oliver Vélez Trading System

**Base URL:** `https://traidingov.cloud`

All endpoints require authentication via OAuth. Get your access token by visiting `/auth/login`.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Health & Info](#health--info)
3. [Accounts](#accounts)
4. [Market Data](#market-data)
5. [Orders](#orders)
6. [Positions](#positions)
7. [Transactions](#transactions)
8. [User Preferences](#user-preferences)
9. [Reports](#reports)
10. [Webhooks](#webhooks)

---

## Authentication

### Start OAuth Flow
```http
GET /auth/login
```
**Description:** Initiates OAuth authentication flow with Schwab.

**Response:**
- Redirects to Schwab login page, OR
- Returns JSON with `auth_url` if `?format=json` is used

**Example:**
```bash
curl https://traidingov.cloud/auth/login
# Or visit in browser
```

---

### Check Authentication Status
```http
GET /auth/status
```
**Description:** Check if user is authenticated and token status.

**Response:**
```json
{
  "authenticated": true,
  "has_access_token": true,
  "has_refresh_token": true,
  "expires_in": 1800
}
```

**Example:**
```bash
curl https://traidingov.cloud/auth/status
```

---

### Refresh Access Token
```http
POST /auth/refresh
```
**Description:** Refresh expired access token using refresh token.

**Response:**
```json
{
  "message": "Token refreshed",
  "access_token": "I0.b2F1dGgyLmJkYy5zY..."
}
```

**Example:**
```bash
curl -X POST https://traidingov.cloud/auth/refresh
```

---

## Health & Info

### Health Check
```http
GET /health
```
**Description:** Check if the service is running.

**Response:**
```json
{
  "status": "healthy",
  "service": "trading-system"
}
```

---

### API Information
```http
GET /
```
**Description:** Get API information and available endpoints.

**Response:**
```json
{
  "message": "Oliver Vélez Trading System API",
  "version": "1.0.0",
  "endpoints": {...}
}
```

---

## Accounts

### Get All Accounts
```http
GET /orders/accounts
```
**Description:** Get all linked accounts with balances and positions.

**Schwab API:** `GET /accounts`

**Response:**
```json
[
  {
    "securitiesAccount": {
      "accountNumber": "18056335",
      "currentBalances": {...},
      "initialBalances": {...}
    }
  }
]
```

**Example:**
```bash
curl https://traidingov.cloud/orders/accounts
```

---

### Get Specific Account
```http
GET /orders/account/<account_id>
```
**Description:** Get specific account balance and positions.

**Schwab API:** `GET /accounts/{accountNumber}`

**Parameters:**
- `account_id` (path): Account number (e.g., "18056335")

**Example:**
```bash
curl https://traidingov.cloud/orders/account/18056335
```

---

### Get Account Numbers
```http
GET /orders/account-numbers
```
**Description:** Get list of account numbers and their encrypted values.

**Schwab API:** `GET /accounts/accountNumbers`

**Example:**
```bash
curl https://traidingov.cloud/orders/account-numbers
```

---

## Market Data

### Get Quote (Single Symbol)
```http
GET /quotes/<symbol>
```
**Description:** Get real-time quote for a single symbol.

**Schwab API:** `GET /quotes?symbols={symbol}`

**Parameters:**
- `symbol` (path): Stock symbol (e.g., "AAPL")

**Example:**
```bash
curl https://traidingov.cloud/quotes/AAPL
```

---

### Get Quotes (Batch)
```http
GET /quotes/batch?symbols=<symbol1,symbol2,...>
```
**Description:** Get quotes for multiple symbols.

**Schwab API:** `GET /quotes?symbols={symbol1,symbol2,...}`

**Query Parameters:**
- `symbols` (required): Comma-separated list of symbols

**Example:**
```bash
curl "https://traidingov.cloud/quotes/batch?symbols=AAPL,MSFT,GOOGL"
```

---

### Get Quote (Alternative Format)
```http
GET /quotes/single/<symbol_id>
```
**Description:** Get quote by single symbol (alternative API format).

**Schwab API:** `GET /{symbol_id}/quotes`

**Example:**
```bash
curl https://traidingov.cloud/quotes/single/AAPL
```

---

### Get Historical Data
```http
GET /quotes/historical/<symbol>?periodType=<type>&period=<n>&frequencyType=<type>&frequency=<n>
```
**Description:** Get historical price data with candles.

**Schwab API:** `GET /pricehistory`

**Query Parameters:**
- `periodType`: `day`, `month`, `year`, `ytd`
- `period`: `1`, `2`, `3`, `4`, `5`, `10`, `15`, `20`
- `frequencyType`: `minute`, `daily`, `weekly`, `monthly`
- `frequency`: `1`, `5`, `10`, `15`, `30`

**Example:**
```bash
# 1-minute candles for today
curl "https://traidingov.cloud/quotes/historical/AAPL?periodType=day&period=1&frequencyType=minute&frequency=1"

# Daily data for 1 month
curl "https://traidingov.cloud/quotes/historical/AAPL?periodType=month&period=1&frequencyType=daily&frequency=1"
```

**Response:** Includes candles, calculated indicators (SMA, ATR, RSI), and CSV file path.

---

### Market Analysis (Full Analysis)
```http
GET /quotes/analyze/<symbol>
```
**Description:** Get comprehensive market analysis with indicators and trading setup identification.

**Response:**
```json
{
  "symbol": "AAPL",
  "summary": {
    "current_price": 150.00,
    "sma_8": 148.50,
    "sma_20": 147.00,
    "sma_200": 145.00,
    "atr_14": 2.50,
    "rsi_14": 55.0,
    "trend": "BULLISH",
    ...
  },
  "setup": {
    "type": "PULLBACK_LONG",
    "direction": "LONG",
    "entry_price": 150.00,
    "stop_loss": 146.25,
    "take_profit": 155.00,
    "confidence": 0.7
  }
}
```

**Example:**
```bash
curl https://traidingov.cloud/quotes/analyze/AAPL
```

---

### Get Option Chains
```http
GET /quotes/options/chains?symbol=<symbol>&contractType=<type>&strikeCount=<n>
```
**Description:** Get option chain for an optionable symbol.

**Schwab API:** `GET /chains`

**Query Parameters:**
- `symbol` (required): Optionable symbol (e.g., "AAPL")
- `contractType`: `CALL`, `PUT`, or `ALL` (default: `ALL`)
- `strikeCount`: Number of strikes (default: `10`)
- `includeQuotes`: `TRUE` or `FALSE` (default: `TRUE`)
- `strategy`: `SINGLE`, `ANALYTICAL`, `COVERED`, `VERTICAL`, etc. (default: `SINGLE`)
- `range`: `ITM`, `NTM`, `OTM`, `ALL` (default: `ALL`)
- `fromDate`: Start date (YYYY-MM-DD)
- `toDate`: End date (YYYY-MM-DD)
- `optionType`: `S` (Standard) or `NS` (Non-standard) (default: `S`)

**Example:**
```bash
curl "https://traidingov.cloud/quotes/options/chains?symbol=AAPL&contractType=ALL&strikeCount=20"
```

---

### Get Option Expiration Chain
```http
GET /quotes/options/expiration-chain?symbol=<symbol>
```
**Description:** Get option expiration chain for an optionable symbol.

**Schwab API:** `GET /expirationchain`

**Query Parameters:**
- `symbol` (required): Optionable symbol

**Example:**
```bash
curl "https://traidingov.cloud/quotes/options/expiration-chain?symbol=AAPL"
```

---

### Get Market Movers
```http
GET /quotes/movers/<symbol_id>?direction=<up|down>&change=<percent|value>
```
**Description:** Get movers for a specific index.

**Schwab API:** `GET /movers/{symbol_id}`

**Parameters:**
- `symbol_id` (path): Index symbol (e.g., `$DJI` for Dow Jones, `$SPX.X` for S&P 500)

**Query Parameters:**
- `direction`: `up` or `down` (default: `up`)
- `change`: `percent` or `value` (default: `percent`)

**Example:**
```bash
# Dow Jones movers
curl "https://traidingov.cloud/quotes/movers/%24DJI?direction=up&change=percent"

# S&P 500 movers
curl "https://traidingov.cloud/quotes/movers/%24SPX.X?direction=down&change=value"
```

---

### Get Market Hours
```http
GET /quotes/markets?market=<type>
```
**Description:** Get market hours for different markets.

**Schwab API:** `GET /markets`

**Query Parameters:**
- `market`: `EQUITY`, `OPTION`, `FUTURE`, `BOND`, `FOREX`

**Example:**
```bash
curl "https://traidingov.cloud/quotes/markets?market=EQUITY"
```

---

### Get Market Hours (Single Market)
```http
GET /quotes/markets/<market_id>
```
**Description:** Get market hours for a single market.

**Schwab API:** `GET /markets/{market_id}`

**Parameters:**
- `market_id` (path): Market identifier (e.g., `EQUITY`, `OPTION`)

**Example:**
```bash
curl https://traidingov.cloud/quotes/markets/EQUITY
```

---

### Get Instruments
```http
GET /quotes/instruments?symbol=<symbol>&projection=<type>
```
**Description:** Get instruments by symbols and projections.

**Schwab API:** `GET /instruments`

**Query Parameters:**
- `symbol` (required): Symbol to search for
- `projection`: `symbol-search`, `symbol-regex`, `desc-search`, `desc-regex`, `fundamental` (default: `symbol-search`)

**Example:**
```bash
curl "https://traidingov.cloud/quotes/instruments?symbol=AAPL&projection=symbol-search"
```

---

### Get Instrument by CUSIP
```http
GET /quotes/instruments/<cusip_id>
```
**Description:** Get instrument by specific CUSIP.

**Schwab API:** `GET /instruments/{cusip_id}`

**Parameters:**
- `cusip_id` (path): CUSIP identifier

**Example:**
```bash
curl https://traidingov.cloud/quotes/instruments/037833100
```

---

## Orders

### Place Order
```http
POST /orders/place
```
**Description:** Place a new trade order.

**Schwab API:** `POST /accounts/{accountNumber}/orders`

**Request Body:**
```json
{
  "symbol": "AAPL",
  "action": "BUY",
  "quantity": 10,
  "orderType": "MARKET",
  "price": 150.00,
  "stopPrice": 145.00,
  "accountId": "18056335"
}
```

**Fields:**
- `symbol` (required): Stock symbol
- `action` (required): `BUY`, `SELL`, `SHORT`
- `quantity` (required): Number of shares
- `orderType` (required): `MARKET`, `LIMIT`, `STOP`
- `price` (optional): Price for LIMIT orders
- `stopPrice` (optional): Stop price
- `accountId` (required): Account number

**Example:**
```bash
curl -X POST https://traidingov.cloud/orders/place \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "action": "BUY",
    "quantity": 1,
    "orderType": "LIMIT",
    "price": 100.00,
    "accountId": "18056335"
  }'
```

---

### Execute AI Trading Signal
```http
POST /orders/signal
```
**Description:** Execute a trading signal from AI analysis with automatic position sizing.

**Request Body:**
```json
{
  "symbol": "AAPL",
  "action": "BUY",
  "entry": 150.00,
  "stop": 145.00,
  "target": 160.00,
  "setup_type": "PULLBACK_LONG",
  "position_size": 10,
  "accountId": "18056335"
}
```

**Example:**
```bash
curl -X POST https://traidingov.cloud/orders/signal \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "action": "BUY",
    "entry": 150.00,
    "stop": 145.00,
    "target": 160.00,
    "setup_type": "PULLBACK_LONG",
    "position_size": 1,
    "accountId": "18056335"
  }'
```

---

### Get All Orders
```http
GET /orders/all-orders?accountId=<id>&maxResults=<n>&status=<status>
```
**Description:** Get all orders for all accounts or a specific account.

**Schwab API:** `GET /orders` or `GET /accounts/{accountNumber}/orders`

**Query Parameters:**
- `accountId` (optional): If provided, get orders for specific account
- `maxResults`: Max number of results (default: `3000`)
- `fromEnteredTime`: Start date/time
- `toEnteredTime`: End date/time
- `status`: Order status filter

**Example:**
```bash
# All orders for all accounts
curl https://traidingov.cloud/orders/all-orders

# Orders for specific account
curl "https://traidingov.cloud/orders/all-orders?accountId=18056335"
```

---

### Get Specific Order
```http
GET /orders/<account_id>/orders/<order_id>
```
**Description:** Get a specific order by its ID.

**Schwab API:** `GET /accounts/{accountNumber}/orders/{orderId}`

**Parameters:**
- `account_id` (path): Account number
- `order_id` (path): Order ID

**Example:**
```bash
curl https://traidingov.cloud/orders/18056335/orders/123456
```

---

### Cancel Order
```http
DELETE /orders/<account_id>/orders/<order_id>
```
**Description:** Cancel an order for a specific account.

**Schwab API:** `DELETE /accounts/{accountNumber}/orders/{orderId}`

**Parameters:**
- `account_id` (path): Account number
- `order_id` (path): Order ID

**Example:**
```bash
curl -X DELETE https://traidingov.cloud/orders/18056335/orders/123456
```

---

### Replace Order
```http
PUT /orders/<account_id>/orders/<order_id>
```
**Description:** Replace an order for a specific account.

**Schwab API:** `PUT /accounts/{accountNumber}/orders/{orderId}`

**Request Body:** Same as place order

**Example:**
```bash
curl -X PUT https://traidingov.cloud/orders/18056335/orders/123456 \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "action": "BUY",
    "quantity": 5,
    "orderType": "LIMIT",
    "price": 155.00,
    "accountId": "18056335"
  }'
```

---

### Preview Order
```http
POST /orders/<account_id>/preview
```
**Description:** Preview an order before placing it.

**Schwab API:** `POST /accounts/{accountNumber}/previewOrder`

**Request Body:** Same as place order

**Example:**
```bash
curl -X POST https://traidingov.cloud/orders/18056335/preview \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "action": "BUY",
    "quantity": 10,
    "orderType": "LIMIT",
    "price": 150.00,
    "accountId": "18056335"
  }'
```

---

## Positions

### Get Positions
```http
GET /orders/positions?accountId=<id>
```
**Description:** Get current positions for an account.

**Schwab API:** `GET /accounts/{accountNumber}/positions`

**Query Parameters:**
- `accountId` (required): Account number

**Example:**
```bash
curl "https://traidingov.cloud/orders/positions?accountId=18056335"
```

---

## Transactions

### Get All Transactions
```http
GET /orders/<account_id>/transactions?startDate=<date>&endDate=<date>&symbol=<symbol>&types=<types>
```
**Description:** Get all transactions for a specific account.

**Schwab API:** `GET /accounts/{accountNumber}/transactions`

**Parameters:**
- `account_id` (path): Account number

**Query Parameters:**
- `startDate`: Start date (YYYY-MM-DD)
- `endDate`: End date (YYYY-MM-DD)
- `symbol`: Filter by symbol
- `types`: Transaction types (TRADE, RECEIVE_AND_DELIVER, DIVIDEND_OR_INTEREST, etc.)

**Example:**
```bash
curl "https://traidingov.cloud/orders/18056335/transactions?startDate=2025-11-01&endDate=2025-11-17"
```

---

### Get Specific Transaction
```http
GET /orders/<account_id>/transactions/<transaction_id>
```
**Description:** Get specific transaction information.

**Schwab API:** `GET /accounts/{accountNumber}/transactions/{transactionId}`

**Parameters:**
- `account_id` (path): Account number
- `transaction_id` (path): Transaction ID

**Example:**
```bash
curl https://traidingov.cloud/orders/18056335/transactions/123456
```

---

## User Preferences

### Get User Preferences
```http
GET /orders/user-preference
```
**Description:** Get user preference information.

**Schwab API:** `GET /userPreference`

**Example:**
```bash
curl https://traidingov.cloud/orders/user-preference
```

---

## Reports

### Daily Report
```http
GET /reports/daily?accountId=<id>
```
**Description:** Generate daily P&L and trading report.

**Query Parameters:**
- `accountId` (required): Account number

**Response:** Includes P&L summary, trades, and AI-generated report.

**Example:**
```bash
curl "https://traidingov.cloud/reports/daily?accountId=18056335"
```

---

### Compliance Report
```http
GET /reports/compliance?start_date=<date>&end_date=<date>
```
**Description:** Generate compliance report with trade statistics.

**Query Parameters:**
- `start_date`: Start date (YYYY-MM-DD, default: today)
- `end_date`: End date (YYYY-MM-DD, default: today)

**Example:**
```bash
curl "https://traidingov.cloud/reports/compliance?start_date=2025-11-01&end_date=2025-11-17"
```

---

### Trade History
```http
GET /reports/trades?start_date=<date>&end_date=<date>
```
**Description:** Get trade history from CSV file.

**Query Parameters:**
- `start_date` (optional): Start date filter
- `end_date` (optional): End date filter

**Example:**
```bash
curl "https://traidingov.cloud/reports/trades?start_date=2025-11-01&end_date=2025-11-17"
```

---

## Webhooks

### Trading Signal Webhook
```http
POST /trading-signal
```
**Description:** Webhook endpoint for AI trading signals (same as `/orders/signal`).

**Request Body:** Same as `/orders/signal`

**Example:**
```bash
curl -X POST https://traidingov.cloud/trading-signal \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "action": "BUY",
    "entry": 150.00,
    "stop": 145.00,
    "target": 160.00,
    "setup_type": "PULLBACK_LONG",
    "position_size": 1,
    "accountId": "18056335"
  }'
```

---

## Error Responses

All endpoints may return the following error responses:

### 401 Unauthorized
```json
{
  "error": "Not authenticated"
}
```
**Solution:** Re-authenticate via `/auth/login`

### 400 Bad Request
```json
{
  "error": "Missing required field: accountId"
}
```
**Solution:** Check request parameters

### 500 Internal Server Error
```json
{
  "error": "Schwab API request failed: ..."
}
```
**Solution:** Check server logs and Schwab API status

---

## Rate Limits

- **Market Data:** Check Schwab API documentation for rate limits
- **Orders:** 60 orders per day (as configured in Schwab Developer Portal)
- **Token Refresh:** Automatic on 401 errors

---

## Authentication Flow

1. Visit `/auth/login` or send client to that URL
2. Complete Schwab login in browser
3. Redirected back with authorization code
4. Code automatically exchanged for tokens
5. Tokens saved to `data/tokens.json`
6. Access token valid for 30 minutes (1800 seconds)
7. Auto-refresh on 401 errors

---

## Quick Reference

### Your Account ID
```
18056335
```

### Common Endpoints
```bash
# Health check
curl https://traidingov.cloud/health

# Get accounts
curl https://traidingov.cloud/orders/accounts

# Market analysis
curl https://traidingov.cloud/quotes/analyze/AAPL

# Get positions
curl "https://traidingov.cloud/orders/positions?accountId=18056335"

# Place order (LIMIT - safe for testing)
curl -X POST https://traidingov.cloud/orders/place \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "action": "BUY", "quantity": 1, "orderType": "LIMIT", "price": 100.00, "accountId": "18056335"}'
```

---

## Implementation Status

✅ **All Schwab API Endpoints Implemented:**

- **Authentication:** 4/4 endpoints
- **Accounts:** 3/3 endpoints
- **Market Data:** 10/10 endpoints
- **Orders:** 7/7 endpoints
- **Positions:** 1/1 endpoint
- **Transactions:** 2/2 endpoints
- **User Preferences:** 1/1 endpoint
- **Reports:** 3/3 endpoints (custom)

**Total: 31 endpoints fully implemented**

---

## Support

For issues or questions:
- Check logs: `data/logs/trading_*.log`
- Verify authentication: `/auth/status`
- Check Schwab API status: Schwab Developer Portal

