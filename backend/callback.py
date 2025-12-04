"""
OAuth callback helper script.
Opens browser for authentication and waits for callback.
"""
import webbrowser
import requests
from flask import Flask, request
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

@app.route('/')
def callback():
    """Handle OAuth callback."""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        print(f"❌ OAuth Error: {error}")
        return f"<h1>Authentication Failed</h1><p>Error: {error}</p>", 400
    
    if code:
        print(f"✅ Authorization code received: {code[:20]}...")
        print("\nYou can now close this window and use the main application.")
        return f"""
        <h1> Authentication Successful!</h1>
        <p>Authorization code received.</p>
        <p>You can now close this window.</p>
        <p>Code: {code[:20]}...</p>
        """
    
    return "<h1>Waiting for authorization...</h1>", 200

if __name__ == '__main__':
    client_id = os.getenv("SCHWAB_CLIENT_ID")
    redirect_uri = os.getenv("SCHWAB_REDIRECT_URI", "http://localhost:5035")
    
    if not client_id:
        print("❌ SCHWAB_CLIENT_ID not found in .env file")
        exit(1)
    
    # Build auth URL
    from urllib.parse import urlencode
    auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?{urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'api'
    })}"
    
    print("🔐 Opening browser for Schwab authentication...")
    print(f"URL: {auth_url}\n")
    
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f"⚠️  Could not open browser automatically: {e}")
        print(f"Please open this URL manually: {auth_url}")
    
    print("🌐 Starting callback server on http://localhost:5035")
    print("Waiting for OAuth callback...\n")
    
    app.run(host='0.0.0.0', port=5035, debug=False)

