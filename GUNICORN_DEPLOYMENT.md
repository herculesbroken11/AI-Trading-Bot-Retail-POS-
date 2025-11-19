# Gunicorn Deployment Guide

## 🚀 Moving from Development to Production

After testing with `python main.py`, deploy with gunicorn for production.

---

## 📋 Prerequisites

✅ All tests pass in development mode  
✅ System works correctly with `python main.py`  
✅ Environment variables configured  
✅ Authentication completed  

---

## 1. Install Gunicorn

```bash
# Activate virtual environment
source venv/bin/activate

# Install gunicorn
pip install gunicorn

# Add to requirements.txt (optional)
echo "gunicorn==21.2.0" >> requirements.txt
```

---

## 2. Create Gunicorn Configuration

Create `gunicorn_config.py`:

```python
# gunicorn_config.py
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5035"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "data/logs/gunicorn_access.log"
errorlog = "data/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "trading-system"

# Server mechanics
daemon = False
pidfile = "data/gunicorn.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if using HTTPS)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Preload app for better performance
preload_app = True

# Worker timeout
graceful_timeout = 30

# Max requests per worker (restart workers after this many requests)
max_requests = 1000
max_requests_jitter = 50
```

---

## 3. Test Gunicorn Locally

```bash
# Activate virtual environment
source venv/bin/activate

# Test gunicorn (foreground)
gunicorn -c gunicorn_config.py main:app

# Or with command line options
gunicorn --bind 0.0.0.0:5035 --workers 4 --timeout 30 main:app
```

**Expected:** Server starts and responds to requests

**Test it:**
```bash
curl http://localhost:5035/health
```

---

## 4. Update main.py for Gunicorn

Ensure `main.py` exports the Flask app:

```python
# main.py should end with:
if __name__ == '__main__':
    # Development mode
    port = int(os.getenv('FLASK_PORT', 5035))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Flask server on {host}:{port}")
    logger.info(f"Dashboard available at: http://{host}:{port}/dashboard")
    app.run(host=host, port=port, debug=debug)
else:
    # Production mode (gunicorn)
    # App is already created above
    pass
```

The `app` object should be accessible for gunicorn.

---

## 5. Create Systemd Service

Create `/etc/systemd/system/trading-system.service`:

```ini
[Unit]
Description=Oliver Vélez Trading System (Gunicorn)
After=network.target

[Service]
Type=notify
User=your_username
Group=your_username
WorkingDirectory=/path/to/AI-Trading-Bot-Retail-POS-
Environment="PATH=/path/to/AI-Trading-Bot-Retail-POS-/venv/bin"
EnvironmentFile=/path/to/AI-Trading-Bot-Retail-POS-/.env

# Gunicorn command
ExecStart=/path/to/AI-Trading-Bot-Retail-POS-/venv/bin/gunicorn \
    -c /path/to/AI-Trading-Bot-Retail-POS-/gunicorn_config.py \
    main:app

# Restart settings
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=trading-system

[Install]
WantedBy=multi-user.target
```

**Update paths:**
- Replace `your_username` with your actual user
- Replace `/path/to/AI-Trading-Bot-Retail-POS-` with actual path

---

## 6. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable trading-system

# Start service
sudo systemctl start trading-system

# Check status
sudo systemctl status trading-system

# View logs
sudo journalctl -u trading-system -f
```

---

## 7. Verify Gunicorn is Running

```bash
# Check if gunicorn process is running
ps aux | grep gunicorn

# Check if port is listening
sudo netstat -tulpn | grep 5035

# Test health endpoint
curl http://localhost:5035/health

# Test authentication
curl http://localhost:5035/auth/status
```

---

## 8. Nginx Configuration (Optional but Recommended)

If using Nginx as reverse proxy:

```nginx
# /etc/nginx/sites-available/trading-system
server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS (if using SSL)
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://127.0.0.1:5035;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/trading-system /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 9. Monitoring & Logs

### View Gunicorn Logs

```bash
# Access logs
tail -f data/logs/gunicorn_access.log

# Error logs
tail -f data/logs/gunicorn_error.log

# Systemd logs
sudo journalctl -u trading-system -f
```

### Monitor Gunicorn Workers

```bash
# Check worker processes
ps aux | grep gunicorn

# Should see:
# - 1 master process
# - N worker processes (based on workers config)
```

---

## 10. Performance Tuning

### Worker Count

```python
# In gunicorn_config.py
# Formula: (2 x CPU cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# For 4 CPU cores: 9 workers
# For 2 CPU cores: 5 workers
```

### Timeout Settings

```python
# Increase timeout for long-running AI analysis
timeout = 120  # 2 minutes
graceful_timeout = 30
```

### Memory Considerations

```python
# Limit max requests to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50
```

---

## 11. SSL/HTTPS Setup (Production)

### Using Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### Update Gunicorn Config for SSL

```python
# In gunicorn_config.py
keyfile = "/etc/letsencrypt/live/your-domain.com/privkey.pem"
certfile = "/etc/letsencrypt/live/your-domain.com/fullchain.pem"
```

---

## 12. Health Checks & Monitoring

### Health Check Script

Create `health_check.sh`:

```bash
#!/bin/bash
HEALTH_URL="http://localhost:5035/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "OK - Service is healthy"
    exit 0
else
    echo "CRITICAL - Service returned $RESPONSE"
    exit 2
fi
```

### Cron Job for Monitoring

```bash
# Add to crontab
*/5 * * * * /path/to/health_check.sh || systemctl restart trading-system
```

---

## 13. Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u trading-system -n 50

# Check gunicorn config
python3 -c "import gunicorn_config"

# Test gunicorn manually
gunicorn -c gunicorn_config.py main:app
```

### Workers Dying

```bash
# Check error logs
tail -f data/logs/gunicorn_error.log

# Increase timeout if needed
# timeout = 120
```

### High Memory Usage

```bash
# Reduce worker count
# workers = 2

# Enable max_requests to restart workers
# max_requests = 500
```

---

## 14. Deployment Checklist

- [ ] Gunicorn installed
- [ ] `gunicorn_config.py` created
- [ ] Tested gunicorn locally
- [ ] Systemd service created
- [ ] Service enabled and started
- [ ] Health endpoint works
- [ ] All API endpoints work
- [ ] Logs are being written
- [ ] Nginx configured (if using)
- [ ] SSL configured (if using)
- [ ] Monitoring set up
- [ ] Firewall configured

---

## 15. Quick Commands Reference

```bash
# Start service
sudo systemctl start trading-system

# Stop service
sudo systemctl stop trading-system

# Restart service
sudo systemctl restart trading-system

# Check status
sudo systemctl status trading-system

# View logs
sudo journalctl -u trading-system -f

# Reload config (after changes)
sudo systemctl daemon-reload
sudo systemctl restart trading-system
```

---

## 🎯 Summary

1. **Test in development** (`python main.py`) ✅
2. **Install gunicorn** ✅
3. **Create gunicorn config** ✅
4. **Test gunicorn locally** ✅
5. **Create systemd service** ✅
6. **Start service** ✅
7. **Verify everything works** ✅
8. **Configure Nginx (optional)** ✅
9. **Set up SSL (optional)** ✅
10. **Monitor and maintain** ✅

**Your system is now production-ready! 🚀**

