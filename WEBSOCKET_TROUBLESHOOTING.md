# WebSocket Troubleshooting Guide for Schwab Streamer API

## How to Verify WebSocket URL Format

### Step 1: Use the Diagnostic Endpoint

After authenticating, call the diagnostic endpoint to see your WebSocket configuration:

```bash
GET https://your-domain.com/streaming/diagnostics
```

Or via browser:
```
https://your-domain.com/streaming/diagnostics
```

This will return:
- The WebSocket URL being used
- Where the URL came from (user preferences or default)
- Customer ID and its source
- Full user preferences structure
- Connection status

### Step 2: Check User Preferences Directly

You can also check the user preferences endpoint:

```bash
GET https://your-domain.com/orders/user-preference
```

Or via browser:
```
https://your-domain.com/orders/user-preference
```

This shows the raw response from Schwab's `/trader/v1/userPreference` endpoint.

### Step 3: What to Look For

In the user preferences response, look for:
- `streamerInfoUrl` - The WebSocket URL
- `schwabClientCustomerId` - Your customer ID
- `streamerInfo` object - May contain nested WebSocket configuration

## What to Ask Schwab Support

When contacting Schwab API Support (via https://developer.schwab.com/), ask the following:

### 1. WebSocket URL Format Question

**Subject:** WebSocket 404 Error - Streamer API Connection Issue

**Message Template:**

```
Hello Schwab API Support Team,

I'm experiencing a 404 error when attempting to connect to the Schwab Streamer API WebSocket. 

Current Situation:
- Using the Schwab Trader API (api.schwabapi.com)
- Successfully authenticated with OAuth 2.0
- Accessing user preferences via GET /trader/v1/userPreference
- Receiving WebSocket URL from user preferences endpoint
- WebSocket handshake fails with "404 Not Found" error

Questions:
1. What is the correct WebSocket URL format for the Streamer API?
   - Is it: wss://streamer.schwab.com?
   - Or a different URL format?
   - Does the URL come from the user preferences endpoint?

2. Are there any specific requirements for the WebSocket connection?
   - Do I need to include specific headers in the WebSocket handshake?
   - Are there any authentication parameters required in the URL itself?

3. What should the user preferences response structure look like?
   - What field contains the WebSocket URL?
   - What field contains the CustomerId required for Streamer connection?

4. Are there any account-level settings or permissions needed?
   - Do I need to enable Streamer API access in my account settings?
   - Are there any subscription requirements?

Current Configuration:
- WebSocket URL: [from diagnostics endpoint]
- Customer ID: [from diagnostics endpoint]
- Error: Handshake status 404 Not Found

Thank you for your assistance.
```

### 2. Customer ID Question

If CustomerId is missing or incorrect:

```
Hello Schwab API Support Team,

I'm trying to connect to the Schwab Streamer API but cannot find the correct CustomerId.

Questions:
1. What field in the user preferences response contains the CustomerId for Streamer API?
2. Is the CustomerId the same as my account number?
3. Should I use the accountNumber from the accounts endpoint, or is there a different identifier?
4. Are there any account-level settings I need to enable to get the CustomerId in user preferences?

Current Status:
- User preferences endpoint: GET /trader/v1/userPreference returns: [show structure]
- Accounts endpoint: GET /trader/v1/accounts returns: [show relevant fields]
- CustomerId found: [Yes/No] - [value if found]

Thank you.
```

### 3. Connection Method Question

If the URL is correct but connection still fails:

```
Hello Schwab API Support Team,

I have the correct WebSocket URL and CustomerId, but the connection still fails with 404.

Questions:
1. What is the correct WebSocket connection method?
   - Should I use standard WebSocket handshake?
   - Are there any specific headers required?
   - Should I send authentication in the URL or after connection?

2. What is the correct LOGIN command format?
   - Should I send LOGIN immediately after WebSocket opens?
   - What parameters are required in the LOGIN request?

3. Are there any rate limits or connection restrictions?
   - How many concurrent WebSocket connections are allowed?
   - Are there any IP whitelist requirements?

Current Implementation:
- WebSocket Library: websocket-client (Python)
- Connection Method: WebSocketApp with run_forever()
- LOGIN Command Format: [show your LOGIN request structure]

Thank you.
```

## Checking in Developer Portal

### 1. API Products Section
- Go to: https://developer.schwab.com/
- Navigate to: **API Products** → **Trader API Individual** → **Learn More**
- Check: **Market Data Production Details** → **Documentation**
- Look for: Streamer API documentation and WebSocket connection details

### 2. Application Settings
- Check your app's configuration
- Verify: Market Data Production is enabled
- Check: Any Streamer-specific settings or permissions

### 3. API Documentation
- Look for: "Streamer API" or "WebSocket" documentation
- Check: Connection examples and requirements
- Verify: URL format and authentication method

## Common Issues and Solutions

### Issue 1: 404 Error on WebSocket Handshake
**Possible Causes:**
- Incorrect WebSocket URL
- Missing or incorrect CustomerId
- Wrong connection method
- Account not enabled for Streamer API

**Solution:**
- Use `/streaming/diagnostics` endpoint to verify configuration
- Check user preferences response structure
- Contact Schwab support with diagnostic information

### Issue 2: CustomerId is None
**Possible Causes:**
- CustomerId not in user preferences
- Different field name in API response
- Account not properly configured

**Solution:**
- Check accounts endpoint as fallback
- Verify account number format
- Contact Schwab support to verify account setup

### Issue 3: WebSocket URL Not Found
**Possible Causes:**
- User preferences structure changed
- Field name different than expected
- Using default URL instead of from preferences

**Solution:**
- Check full user preferences structure
- Verify field names match documentation
- Use diagnostic endpoint to see what's being extracted

## Testing Steps

1. **Authenticate:**
   ```
   GET /auth/login
   ```

2. **Run Diagnostics:**
   ```
   GET /streaming/diagnostics
   ```
   - Save the response for reference

3. **Check User Preferences:**
   ```
   GET /orders/user-preference
   ```
   - Review the full structure
   - Note the WebSocket URL and CustomerId fields

4. **Try Connection:**
   ```
   POST /streaming/connect
   ```
   - Check server logs for detailed error messages
   - Note the exact error format

5. **Contact Support:**
   - Include diagnostic endpoint response
   - Include user preferences structure
   - Include error logs
   - Ask specific questions from templates above

## Additional Resources

- Schwab Developer Portal: https://developer.schwab.com/
- API Documentation: Check "Market Data Production" section
- Support: Use the support form in the developer portal
