# Troubleshooting Guide

## 401 Unauthorized Error During Token Exchange

### Issue
Getting `401 Client Error: Unauthorized` when exchanging authorization code for tokens.

### Common Causes & Solutions

#### 1. **Basic Authentication Required**
✅ **FIXED**: The code now uses Basic Auth (client_id:client_secret in Authorization header) instead of sending credentials in the body.

#### 2. **Redirect URI Mismatch**
The `redirect_uri` used in the token exchange **MUST EXACTLY MATCH** the one used in the authorization request and registered in Schwab Developer Portal.

**Check:**
- Schwab Developer Portal: `https://traidingov.cloud` (no trailing slash)
- `.env` file: `SCHWAB_REDIRECT_URI=https://traidingov.cloud` (must match exactly)
- Authorization request uses the same URI

**Common mistakes:**
- ❌ `https://traidingov.cloud/` (trailing slash)
- ❌ `http://traidingov.cloud` (http vs https)
- ❌ `https://www.traidingov.cloud` (www vs non-www)

#### 3. **Client Credentials**
Verify your credentials are correct:
```bash
# Check .env file
cat .env | grep SCHWAB

# Should show:
# SCHWAB_CLIENT_ID=your_actual_client_id
# SCHWAB_CLIENT_SECRET=your_actual_client_secret
```

#### 4. **Authorization Code Issues**
- Codes expire quickly (usually within 1-2 minutes)
- Codes can only be used once
- If code is used twice, you'll get 401

**Solution:** Get a fresh code by re-authenticating.

#### 5. **URL Encoding**
✅ **FIXED**: The code now properly URL-decodes the authorization code.

### Verification Steps

1. **Check logs for detailed error:**
   ```bash
   tail -f data/logs/trading_*.log
   ```
   Look for:
   - "Exchanging code for tokens (redirect_uri: ...)"
   - "Token exchange failed: ..."
   - "Response: ..."

2. **Verify redirect_uri matches:**
   ```bash
   # In your .env file
   grep SCHWAB_REDIRECT_URI .env
   
   # Should match exactly what's in Schwab Developer Portal
   ```

3. **Test with curl (for debugging):**
   ```bash
   # Get a fresh authorization code first
   # Then test token exchange manually:
   curl -X POST https://api.schwabapi.com/v1/oauth/token \
     -H "Authorization: Basic $(echo -n 'CLIENT_ID:CLIENT_SECRET' | base64)" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code" \
     -d "code=YOUR_CODE" \
     -d "redirect_uri=https://traidingov.cloud"
   ```

### After Fixing

1. **Restart the Flask application:**
   ```bash
   # If using systemd
   sudo systemctl restart trading-system
   
   # Or if running directly
   pkill -f "python.*main.py"
   python3 main.py
   ```

2. **Have client re-authenticate:**
   - Visit: `https://traidingov.cloud/auth/login`
   - Complete login
   - Should now work!

### Additional Debugging

Enable more verbose logging by setting in `.env`:
```
FLASK_DEBUG=True
```

Check Nginx logs if issues persist:
```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

