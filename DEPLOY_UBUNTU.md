# Ubuntu VPS Deployment Guide

## Step-by-Step Deployment to Ubuntu Server

### 1. Transfer Files to Server

```bash
# From your local machine
scp -r . user@31.220.54.199:/opt/trading-system/
```

### 2. SSH into Server

```bash
ssh user@31.220.54.199
cd /opt/trading-system
```

### 3. Initial Setup (One-Time)

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
nano .env  # Edit with your credentials
```

### 4. Configure .env File

Edit `.env` with your credentials:
```bash
nano .env
```

Required values:
- `SCHWAB_CLIENT_ID`
- `SCHWAB_CLIENT_SECRET`
- `OPENAI_API_KEY`
- `SCHWAB_REDIRECT_URI` (should be your server's public URL or localhost for testing)

### 5. Authenticate with Schwab (One-Time)

**Option A: Using callback script (if you have browser access)**
```bash
python3 callback.py
```

**Option B: Manual OAuth flow**
1. Start the main server temporarily:
   ```bash
   python3 main.py
   ```
2. In another terminal or from your local machine, visit:
   ```
   http://31.220.54.199:5035/auth/login
   ```
3. Complete authentication
4. Tokens will be saved to `data/tokens.json`

### 6. Run the Main Application

**Option A: Direct execution (for testing)**
```bash
source venv/bin/activate
python3 main.py
```

**Option B: Using systemd service (recommended for production)**

Create service file:
```bash
sudo nano /etc/systemd/system/trading-system.service
```

Add this content:
```ini
[Unit]
Description=Oliver Vélez Trading System
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/opt/trading-system
Environment="PATH=/opt/trading-system/venv/bin"
ExecStart=/opt/trading-system/venv/bin/python3 /opt/trading-system/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-system
sudo systemctl start trading-system
```

Check status:
```bash
sudo systemctl status trading-system
```

View logs:
```bash
sudo journalctl -u trading-system -f
```

### 7. Verify It's Running

```bash
# Check if service is running
sudo systemctl status trading-system

# Test health endpoint
curl http://localhost:5035/health

# Check auth status
curl http://localhost:5035/auth/status
```

### 8. Firewall Configuration (if needed)

```bash
# Allow port 5035
sudo ufw allow 5035/tcp
sudo ufw reload
```

## Quick Reference: What to Run

**First time setup:**
1. `python3 -m venv venv` - Create virtual environment
2. `source venv/bin/activate` - Activate venv
3. `pip install -r requirements.txt` - Install dependencies
4. `cp .env.example .env` - Create config file
5. `nano .env` - Configure credentials
6. `python3 callback.py` - Authenticate (one-time)
7. `python3 main.py` - Test run

**Production (after setup):**
- Use systemd service: `sudo systemctl start trading-system`
- Or run directly: `python3 main.py` (with screen/tmux/nohup)

## Troubleshooting

**Check if port is in use:**
```bash
sudo netstat -tulpn | grep 5035
```

**Kill process on port 5035:**
```bash
sudo lsof -ti:5035 | xargs kill -9
```

**View application logs:**
```bash
tail -f data/logs/trading_*.log
```

**Check token file:**
```bash
cat data/tokens.json
```

