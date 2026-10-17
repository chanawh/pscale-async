# SSH Setup - Quick Reference

**Status: CONFIGURED** ✅

## Summary

SSH passwordless authentication has been successfully configured for the OneFS cluster connection.

## Configuration Details

| Setting | Value |
|---------|-------|
| Cluster Host | `<ONEFS_HOST>` |
| SSH Port | `50019` |
| Username | `root` |
| SSH Key | `C:\Users\chana13\.ssh\id_ed25519` |
| API Port | `8080` |

## Setup Commands Used

```bash
# Copy SSH public key to cluster (Git Bash)
ssh-copy-id -p 50019 -i ~/.ssh/id_ed25519.pub root@<ONEFS_HOST>

# Test passwordless connection
ssh -p 50019 -i ~/.ssh/id_ed25519 root@<ONEFS_HOST> "echo connected"
```

## Backend Configuration

Located in `C:\Users\chana13\Documents\test2\.env`:

```bash
ONEFS_HOST=<ONEFS_HOST>
ONEFS_SSH_PORT=50019
ONEFS_API_PORT=8080
ONEFS_USER=root
ONEFS_PASS=
ONEFS_SSH_KEY_PATH=C:\Users\chana13\.ssh\id_ed25519
```

## Verification

### 1. SSH Direct Connection
```bash
ssh -p 50019 -i ~/.ssh/id_ed25519 root@<ONEFS_HOST>
# Should connect without password prompt
```

### 2. Backend API Test
```bash
# Test cluster connection via API
curl http://127.0.0.1:8001/api/v1/cluster/status

# Expected response:
{
  "status": "connected",
  "cluster": {
    "hostname": "<ONEFS_HOST>",
    "version": "Unknown",
    "nodes": 0,
    "status": "connected"
  },
  "metrics": {
    "uptime": "10:09PM  up 14 days, 14:17...",
    "connection_type": "SSH"
  }
}
```

### 3. Health Check
```bash
curl http://127.0.0.1:8001/health
# Response: {"status":"healthy","database":"connected","celery":"connected"}
```

## Current System Status

| Component | Status | Details |
|-----------|--------|---------|
| Backend API | ✅ Running | `http://127.0.0.1:8001` |
| PostgreSQL | ✅ Connected | `localhost:5432/log_intelligence` |
| Redis | ✅ Connected | `localhost:6379` |
| SSH Key Auth | ✅ Configured | Passwordless to `<ONEFS_HOST>:50019` |
| OneFS Cluster | ✅ Connected | SSH connection active |
| Log Patterns | ✅ Loaded | 23 default patterns |

## Troubleshooting

### If SSH fails:
```bash
# Check key permissions (should be 600)
chmod 600 ~/.ssh/id_ed25519

# Test verbose connection
ssh -v -p 50019 -i ~/.ssh/id_ed25519 root@<ONEFS_HOST>

# Check network connectivity
telnet <ONEFS_HOST> 50019
```

### If backend can't connect:
1. Verify `.env` file has correct paths
2. Ensure PostgreSQL is running: `pg_isready -h localhost`
3. Ensure Redis is running: `redis-cli ping`
4. Check backend logs for connection errors

## File Locations

| File | Path |
|------|------|
| SSH Private Key | `C:\Users\chana13\.ssh\id_ed25519` |
| SSH Public Key | `C:\Users\chana13\.ssh\id_ed25519.pub` |
| Environment Config | `C:\Users\chana13\Documents\test2\.env` |
| SSH Guide | `C:\Users\chana13\Documents\test2\docs\SSH_SETUP_GUIDE.md` |

## Next Steps

1. **Start Celery Worker** (if processing logs):
   ```bash
   celery -A src.core.celery worker --loglevel=info
   ```

2. **Test Log Ingestion**:
   ```bash
   # Via API endpoint
   curl -X POST http://127.0.0.1:8001/api/v1/ingest/jobs \
     -F "file=@/path/to/logfile.log"
   ```

3. **Access Swagger Docs**:
   - Open: `http://127.0.0.1:8001/docs`

---
*Setup completed on: April 2, 2026*
*Git Bash version: 2.47.0.windows.2*
*OpenSSH version: 9.9p1*
