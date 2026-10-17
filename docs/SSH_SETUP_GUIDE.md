# SSH Setup Guide for OneFS Integration

This guide covers the proper way to configure SSH connections to Dell EMC Isilon OneFS clusters in this project.

## Overview

The project supports multiple SSH connection methods:
1. **Direct SSH Connection** - Direct connection to OneFS cluster
2. **SSH Tunnel Mode** - Through Docker container tunnel
3. **Mock Mode** - Development/testing without real cluster

## Configuration Methods

### Method 1: Direct SSH Connection (Recommended for Production)

Set these environment variables in your `.env` file:

```bash
# OneFS Cluster Direct Connection
ONEFS_HOST=your-cluster.example.com
ONEFS_SSH_PORT=50019
ONEFS_API_PORT=8080
ONEFS_USER=root
ONEFS_PASS=your-password
ONEFS_SSH_KEY_PATH=~/.ssh/id_ed25519

# Disable mock mode
ONEFS_MOCK_MODE=false
```

### Method 2: SSH Key Authentication (More Secure)

1. Generate SSH key pair:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/onefs_cluster -C "onefs-admin"
```

2. Copy public key to OneFS cluster:
```bash
ssh-copy-id -i ~/.ssh/onefs_cluster.pub root@your-cluster.example.com -p 50019
```

3. Configure environment:
```bash
ONEFS_HOST=your-cluster.example.com
ONEFS_SSH_PORT=50019
ONEFS_USER=root
ONEFS_SSH_KEY_PATH=~/.ssh/onefs_cluster
# Leave ONEFS_PASS empty for key auth
```

### Method 3: Docker SSH Tunnel (Development)

The project includes an SSH tunnel service in Docker Compose:

```yaml
# From docker-compose.yml
isilon-tunnel:
  image: alpine:3.20
  environment:
    MGMT_IP: "${ONEFS_HOST}"     # Set ONEFS_HOST in your .env — never commit a real IP
    MGMT_PORT: "8080"            # OneFS Platform API port
    JUMPHOST: "${ONEFS_HOST}"    # SSH target (set ONEFS_HOST in your .env)
    JUMPPORT: "50019"            # SSH port
    SSH_KEY: "/root/.ssh/id_ed25519"
```

To use tunnel mode:
```bash
# Set environment for tunnel mode
ISILON_HOST=isilon-tunnel
ISILON_PORT=8080
ISILON_USER=root
ISILON_PASS=your-password

# Mount your SSH key
SSH_KEY_PATH=~/.ssh
```

## SSH Key Setup

### 1. Create SSH Key

```bash
# Create ed25519 key (recommended)
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/onefs_ed25519

# Or RSA key if needed
ssh-keygen -t rsa -b 4096 -a 100 -f ~/.ssh/onefs_rsa
```

### 2. Set Proper Permissions

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/onefs_ed25519
chmod 644 ~/.ssh/onefs_ed25519.pub
```

### 3. Add to OneFS Cluster

```bash
# Method 1: ssh-copy-id
ssh-copy-id -i ~/.ssh/onefs_ed25519.pub root@cluster.example.com -p 50019

# Method 2: Manual copy
scp -P 50019 ~/.ssh/onefs_ed25519.pub root@cluster.example.com:/tmp/
ssh -p 50019 root@cluster.example.com
mkdir -p /root/.ssh
cat /tmp/onefs_ed25519.pub >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

## Environment Configuration

### Development (.env.example)

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/log_intelligence

# Redis
REDIS_URL=redis://localhost:6379/0

# OneFS SSH Configuration
ONEFS_HOST=your-cluster.example.com
ONEFS_SSH_PORT=50019
ONEFS_API_PORT=8080
ONEFS_USER=root
ONEFS_PASS=
ONEFS_SSH_KEY_PATH=~/.ssh/onefs_ed25519

# Mock mode for development
ONEFS_MOCK_MODE=true

# Security
SECRET_KEY=your-secret-key-here
```

### Production (.env)

```bash
# Production settings
DATABASE_URL=postgresql://user:pass@prod-db:5432/log_intelligence
REDIS_URL=redis://prod-redis:6379/0

# OneFS Production Configuration
ONEFS_HOST=prod-cluster.company.com
ONEFS_SSH_PORT=50019
ONEFS_API_PORT=8080
ONEFS_USER=onefs-admin
ONEFS_SSH_KEY_PATH=/app/keys/onefs_prod
ONEFS_PASS=

# Disable mock mode in production
ONEFS_MOCK_MODE=false

# Security
SECRET_KEY=super-secure-random-string
```

## Connection Testing

### 1. Test SSH Connection

```bash
# Direct SSH test
ssh -p 50019 -i ~/.ssh/onefs_ed25519 root@your-cluster.example.com

# Test command execution
ssh -p 50019 -i ~/.ssh/onefs_ed25519 root@your-cluster.example.com "isi_config"
```

### 2. Test API Connection

```bash
# Test HTTP API
curl -k -u root:password https://your-cluster.example.com:8080/platform/1/cluster

# Test log file access
curl -k -u root:password "https://your-cluster.example.com:8080/platform/1/filesystem/files/var/log/messages"
```

### 3. Test Application Connection

```python
# Test connection in Python
from src.onefs.client import OneFSClient

client = OneFSClient()
try:
    client.test_connection()
    print("Connection successful!")
    print("Cluster info:", client.get_cluster_info())
except Exception as e:
    print(f"Connection failed: {e}")
```

## Docker Setup

### 1. Build with SSH Keys

```bash
# Mount your SSH directory when running
docker-compose up --build -d

# Or specify custom SSH key path
SSH_KEY_PATH=/path/to/your/ssh docker-compose up --build -d
```

### 2. Docker Environment

```yaml
# docker-compose.override.yml for development
version: "3.9"
services:
  api:
    environment:
      - ONEFS_HOST=host.docker.internal
      - ONEFS_SSH_PORT=50019
      - ONEFS_USER=root
      - ONEFS_SSH_KEY_PATH=/root/.ssh/id_ed25519
      - ONEFS_MOCK_MODE=false
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Check SSH key permissions (600 for private key)
   - Verify public key is in `~root/.ssh/authorized_keys` on cluster
   - Ensure SSH service is running on cluster

2. **Connection Timeout**
   - Verify cluster IP and port are correct
   - Check firewall rules
   - Ensure SSH port (50019) is open

3. **Authentication Failed**
   - Try password auth as fallback
   - Check SSH key format (OpenSSH format required)
   - Verify username (usually root)

4. **Host Key Verification**
   - Use `-o StrictHostKeyChecking=accept-new` (pins the key on first use) —
     never `no`, which disables MITM protection entirely
   - Or add the host key to `known_hosts` (or set ONEFS_HOST_KEY) for strict checking

### Debug Commands

```bash
# Verbose SSH connection
ssh -v -p 50019 -i ~/.ssh/onefs_ed25519 root@cluster.example.com

# Test connectivity
telnet cluster.example.com 50019
nc -zv cluster.example.com 50019

# Check Docker logs
docker-compose logs isilon-tunnel
docker-compose logs api
```

## Security Best Practices

1. **Use SSH Keys Instead of Passwords**
   - Ed25519 keys are preferred over RSA
   - Use strong passphrases for keys
   - Rotate keys regularly

2. **Limit Access**
   - Use dedicated service accounts
   - Implement IP whitelisting
   - Use bastion hosts when possible

3. **Key Management**
   - Never commit private keys to version control
   - Use vault systems for production keys
   - Implement key rotation policies

4. **Network Security**
   - Use VPNs for remote access
   - Implement network segmentation
   - Monitor SSH access logs

## Mock Mode Development

For development without a real cluster:

```bash
# Enable mock mode
export ONEFS_MOCK_MODE=true

# The application will use mock responses
# No real SSH connection attempted
```

Mock mode provides:
- Simulated cluster information
- Sample log files
- Fake authentication responses
- No external dependencies

This mode is ideal for:
- Feature development
- UI testing
- CI/CD pipelines
- Demo environments
