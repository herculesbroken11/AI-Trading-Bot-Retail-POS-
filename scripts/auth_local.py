#!/usr/bin/env python3
"""
Local OAuth Authentication Script
Opens browser, captures OAuth redirect, and exchanges code for tokens
"""

import os
import sys
import webbrowser
import http.server
import socketserver
import urllib.parse
import threading
import time
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config
from core.auth import generate_authorization_url, validate_redirect_uri
from core.schwab_client import SchwabClient

# Global variables for OAuth callback
received_code: Optional[str] = None
received_state: Optional[str] = None
server_error: Optional[str] = None

class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler for OAuth callback"""
    
    def do_GET(self):
        """Handle GET request (OAuth redirect)"""
        global received_code, received_state, server_error
        
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            
            if 'code' in params:
                received_code = params['code'][0]
                received_state = params.get('state', [None])[0]
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                    <html>
                    <head><title>Authentication Successful</title></head>
                    <body>
                        <h1>Authentication Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </body>
                    </html>
                """)
            elif 'error' in params:
                error = params['error'][0]
                error_description = params.get('error_description', ['Unknown error'])[0]
                server_error = f"{error}: {error_description}"
                
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f"""
                    <html>
                    <head><title>Authentication Failed</title></head>
                    <body>
                        <h1>Authentication Failed</h1>
                        <p>Error: {error}</p>
                        <p>Description: {error_description}</p>
                    </body>
                    </html>
                """.encode())
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Invalid request</h1></body></html>")
                
        except Exception as e:
            server_error = str(e)
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"<html><body><h1>Error: {e}</h1></body></html>".encode())
    
    def log_message(self, format, *args):
        """Suppress server logs"""
        pass

def run_local_server(port: int, timeout: int = 300) -> Optional[str]:
    """
    Run local HTTP server to capture OAuth callback
    
    Args:
        port: Port number to listen on
        timeout: Timeout in seconds
        
    Returns:
        Authorization code if received, None otherwise
    """
    global received_code, server_error
    
    try:
        # Parse redirect URI to get port
        parsed = urllib.parse.urlparse(Config.SCHWAB_REDIRECT_URI)
        if parsed.port:
            port = parsed.port
        
        # Create server
        with socketserver.TCPServer(("127.0.0.1", port), OAuthCallbackHandler) as httpd:
            print(f"Starting local server on http://127.0.0.1:{port}")
            print(f"Waiting for OAuth callback (timeout: {timeout}s)...")
            
            # Set timeout
            httpd.timeout = 1
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                httpd.handle_request()
                
                if received_code:
                    print("Authorization code received!")
                    return received_code
                
                if server_error:
                    print(f"Error: {server_error}")
                    return None
                
                time.sleep(0.1)
            
            print("Timeout waiting for OAuth callback")
            return None
            
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"Error: Port {port} is already in use")
            print("Please close any other applications using this port or change SCHWAB_REDIRECT_URI")
        else:
            print(f"Error starting server: {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    """Main authentication function"""
    print("=" * 60)
    print("Schwab OAuth Local Authentication")
    print("=" * 60)
    
    # Validate configuration
    is_valid, missing = Config.validate_schwab_config()
    if not is_valid:
        print(f"\nError: Missing required configuration: {', '.join(missing)}")
        print("Please check your .env file")
        return 1
    
    # Validate redirect URI
    if not validate_redirect_uri(Config.SCHWAB_REDIRECT_URI):
        print(f"\nError: Invalid redirect URI: {Config.SCHWAB_REDIRECT_URI}")
        print("Redirect URI must be https://127.0.0.1:PORT or https://localhost:PORT")
        return 1
    
    # Check if tokens already exist
    token_file = "./data/schwab_tokens.json"
    if os.path.exists(token_file):
        response = input(f"\nTokens file already exists at {token_file}\nOverwrite? (y/N): ")
        if response.lower() != 'y':
            print("Authentication cancelled")
            return 0
    
    # Generate authorization URL
    print("\nGenerating authorization URL...")
    auth_url, state = generate_authorization_url(
        Config.SCHWAB_REDIRECT_URI,
        Config.SCHWAB_CLIENT_ID,
        scope="api"
    )
    
    print(f"\nAuthorization URL generated:")
    print(f"State: {state}")
    print(f"\n{auth_url}")
    
    # Start local server in background thread
    print("\nStarting local server to capture OAuth callback...")
    server_thread = threading.Thread(target=run_local_server, args=(5035, 300), daemon=True)
    server_thread.start()
    
    # Wait a moment for server to start
    time.sleep(1)
    
    # Open browser
    print("\nOpening browser for authentication...")
    print("Please log in and approve the application.")
    print("After approval, you'll be redirected back automatically.")
    
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f"Warning: Could not open browser automatically: {e}")
        print(f"Please manually open this URL in your browser:\n{auth_url}")
    
    # Wait for callback
    print("\nWaiting for OAuth callback...")
    code = None
    start_time = time.time()
    timeout = 300  # 5 minutes
    
    while time.time() - start_time < timeout:
        if received_code:
            code = received_code
            break
        if server_error:
            print(f"Error: {server_error}")
            return 1
        time.sleep(0.5)
    
    if not code:
        print("\nTimeout: No authorization code received")
        print("Please check:")
        print("1. Did you complete the login in the browser?")
        print("2. Is your callback URL correct in Schwab Developer Portal?")
        print("3. Did you approve the application?")
        return 1
    
    # Exchange code for tokens
    print("\nExchanging authorization code for tokens...")
    try:
        client = SchwabClient(
            Config.SCHWAB_CLIENT_ID,
            Config.SCHWAB_CLIENT_SECRET
        )
        
        client.exchange_code_for_tokens(code, Config.SCHWAB_REDIRECT_URI)
        
        print(f"\n[OK] Authentication successful!")
        print(f"Tokens saved to: {token_file}")
        print("\nNext steps:")
        print("1. Run: python scripts/test_connection.py (to verify tokens)")
        print("2. Run: python scripts/init_db.py (to initialize database)")
        print("3. Run: uvicorn api.main:app --host 0.0.0.0 --port 8000 (to start API server)")
        
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Failed to exchange code for tokens: {e}")
        print("\nTroubleshooting:")
        print("1. Verify your SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET in .env")
        print("2. Check that the callback URL matches in Schwab Developer Portal")
        print("3. Make sure the authorization code hasn't expired")
        return 1

if __name__ == "__main__":
    sys.exit(main())

