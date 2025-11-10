"""
Unit tests for token exchange and refresh
"""

import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
import requests

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.schwab_client import SchwabClient

class TestTokenExchange:
    """Test token exchange functionality"""
    
    @pytest.fixture
    def mock_token_response(self):
        """Mock successful token response"""
        return {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 1800,
            'token_type': 'Bearer'
        }
    
    @pytest.fixture
    def temp_token_file(self):
        """Create temporary token file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @patch('requests.Session.post')
    def test_exchange_code_for_tokens_success(self, mock_post, mock_token_response, temp_token_file):
        """Test successful token exchange"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_token_response
        mock_post.return_value = mock_response
        
        # Create client
        client = SchwabClient(
            client_id='test_client_id',
            client_secret='test_secret',
            token_file=temp_token_file
        )
        
        # Exchange code
        result = client.exchange_code_for_tokens(
            authorization_code='test_code',
            redirect_uri='https://127.0.0.1:5035'
        )
        
        # Verify
        assert result['access_token'] == 'test_access_token'
        assert result['refresh_token'] == 'test_refresh_token'
        assert client.access_token == 'test_access_token'
        assert client.refresh_token == 'test_refresh_token'
        
        # Verify tokens were saved
        assert os.path.exists(temp_token_file)
        with open(temp_token_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data['access_token'] == 'test_access_token'
    
    @patch('requests.Session.post')
    def test_exchange_code_for_tokens_failure(self, mock_post, temp_token_file):
        """Test token exchange failure"""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid code'
        mock_post.return_value = mock_response
        
        # Create client
        client = SchwabClient(
            client_id='test_client_id',
            client_secret='test_secret',
            token_file=temp_token_file
        )
        
        # Attempt exchange - should raise exception
        with pytest.raises(Exception) as exc_info:
            client.exchange_code_for_tokens(
                authorization_code='invalid_code',
                redirect_uri='https://127.0.0.1:5035'
            )
        
        assert 'Token exchange failed' in str(exc_info.value)
    
    @patch('requests.Session.post')
    def test_refresh_token_success(self, mock_post, mock_token_response, temp_token_file):
        """Test successful token refresh"""
        # Save initial tokens
        initial_tokens = {
            'access_token': 'old_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 1800,
            'issued_at': 1000
        }
        
        with open(temp_token_file, 'w') as f:
            json.dump(initial_tokens, f)
        
        # Mock refresh response
        new_tokens = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 1800
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = new_tokens
        mock_post.return_value = mock_response
        
        # Create client (should load existing tokens)
        client = SchwabClient(
            client_id='test_client_id',
            client_secret='test_secret',
            token_file=temp_token_file
        )
        
        # Refresh token
        result = client.refresh_access_token()
        
        # Verify
        assert result is True
        assert client.access_token == 'new_access_token'
        
        # Verify tokens were saved
        with open(temp_token_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data['access_token'] == 'new_access_token'
    
    @patch('requests.Session.post')
    def test_refresh_token_failure(self, mock_post, temp_token_file):
        """Test token refresh failure"""
        # Save tokens with refresh token
        initial_tokens = {
            'access_token': 'old_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 1800,
            'issued_at': 1000
        }
        
        with open(temp_token_file, 'w') as f:
            json.dump(initial_tokens, f)
        
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Invalid refresh token'
        mock_post.return_value = mock_response
        
        # Create client
        client = SchwabClient(
            client_id='test_client_id',
            client_secret='test_secret',
            token_file=temp_token_file
        )
        
        # Attempt refresh - should return False
        result = client.refresh_access_token()
        assert result is False
    
    def test_load_tokens_from_file(self, mock_token_response, temp_token_file):
        """Test loading tokens from file"""
        # Save tokens to file
        with open(temp_token_file, 'w') as f:
            json.dump(mock_token_response, f)
        
        # Create client - should load tokens
        client = SchwabClient(
            client_id='test_client_id',
            client_secret='test_secret',
            token_file=temp_token_file
        )
        
        # Verify tokens loaded
        assert client.access_token == 'test_access_token'
        assert client.refresh_token == 'test_refresh_token'
    
    def test_ensure_valid_token_with_valid_token(self, mock_token_response, temp_token_file):
        """Test ensuring valid token when token is already valid"""
        # Save tokens with future expiration
        import time
        tokens = mock_token_response.copy()
        tokens['issued_at'] = time.time()
        tokens['expires_in'] = 3600  # 1 hour
        
        with open(temp_token_file, 'w') as f:
            json.dump(tokens, f)
        
        # Create client
        client = SchwabClient(
            client_id='test_client_id',
            client_secret='test_secret',
            token_file=temp_token_file
        )
        
        # Token should be valid
        result = client._ensure_valid_token()
        assert result is True

if __name__ == '__main__':
    pytest.main([__file__, '-v'])

