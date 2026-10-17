#!/bin/bash

# SSH Setup Script for OneFS Integration
# This script helps configure SSH keys and test connectivity

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SSH_DIR="$HOME/.ssh"
ONEFS_KEY_NAME="onefs_cluster"
ONEFS_KEY_PATH="$SSH_DIR/${ONEFS_KEY_NAME}"

# Functions
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_ssh_dir() {
    if [ ! -d "$SSH_DIR" ]; then
        print_status "Creating SSH directory..."
        mkdir -p "$SSH_DIR"
        chmod 700 "$SSH_DIR"
    fi
}

create_ssh_key() {
    if [ -f "$ONEFS_KEY_PATH" ]; then
        print_warning "SSH key already exists at $ONEFS_KEY_PATH"
        read -p "Do you want to generate a new key? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return
        fi
    fi

    print_status "Generating SSH key for OneFS cluster..."
    ssh-keygen -t ed25519 -a 100 -f "$ONEFS_KEY_NAME" -C "onefs-admin@$(hostname)"
    
    print_success "SSH key generated:"
    echo "  Private key: $ONEFS_KEY_PATH"
    echo "  Public key:  $ONEFS_KEY_PATH.pub"
}

show_public_key() {
    print_status "Your public key for OneFS cluster:"
    echo
    cat "$ONEFS_KEY_PATH.pub"
    echo
    print_status "Copy this key and add it to your OneFS cluster:"
    echo "  SSH into your OneFS cluster as root"
    echo "  Run: mkdir -p /root/.ssh"
    echo "  Run: echo '$(cat $ONEFS_KEY_PATH.pub)' >> /root/.ssh/authorized_keys"
    echo "  Run: chmod 600 /root/.ssh/authorized_keys"
    echo
}

test_ssh_connection() {
    read -p "Enter your OneFS cluster hostname/IP: " cluster_host
    read -p "Enter SSH port (default 50019): " ssh_port
    ssh_port=${ssh_port:-50019}

    print_status "Testing SSH connection to $cluster_host:$ssh_port..."
    
    if ssh -p "$ssh_port" -i "$ONEFS_KEY_PATH" -o ConnectTimeout=10 -o BatchMode=yes "${ONEFS_USER:-root}@$cluster_host" "echo 'Connection successful'" 2>/dev/null; then
        print_success "SSH connection successful!"
        
        print_status "Testing OneFS commands..."
        ssh -p "$ssh_port" -i "$ONEFS_KEY_PATH" "${ONEFS_USER:-root}@$cluster_host" "isi_config 2>/dev/null | head -5" || print_warning "isi_config command failed (may not be available)"
        
        return 0
    else
        print_error "SSH connection failed!"
        echo "Please check:"
        echo "  1. Cluster hostname/IP is correct"
        echo "  2. SSH port is correct (usually 50019)"
        echo "  3. SSH key is properly installed on cluster"
        echo "  4. Network connectivity is working"
        return 1
    fi
}

update_env_file() {
    local env_file=".env"
    read -p "Enter your OneFS cluster hostname/IP: " cluster_host
    read -p "Enter SSH port (default 50019): " ssh_port
    ssh_port=${ssh_port:-50019}
    read -p "Enter API port (default 8080): " api_port
    api_port=${api_port:-8080}

    print_status "Updating .env file..."
    
    # Backup existing .env
    if [ -f "$env_file" ]; then
        cp "$env_file" "${env_file}.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    # Update or create .env
    cat > "$env_file" << EOF
# Database
DATABASE_URL=${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/log_intelligence}

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Security (CHANGE THIS IN PRODUCTION)
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OneFS SSH Configuration
ONEFS_HOST=$cluster_host
ONEFS_SSH_PORT=$ssh_port
ONEFS_API_PORT=$api_port
ONEFS_USER=root
ONEFS_SSH_KEY_PATH=$ONEFS_KEY_PATH

# Mock mode (set to false for real cluster)
ONEFS_MOCK_MODE=false

# Log Processing
MAX_FILE_SIZE_MB=2048
CHUNK_SIZE=8192
PATTERN_LIBRARY_PATH=./patterns/
EOF

    print_success ".env file updated successfully!"
}

test_application() {
    print_status "Testing application SSH integration..."
    
    # Check if we can import the OneFS client
    if python -c "from src.onefs.client import OneFSClient; print('OneFS client import successful')" 2>/dev/null; then
        print_success "OneFS client imports correctly"
        
        # Test connection (this will show detailed logs)
        print_status "Running connection test..."
        python -c "
from src.onefs.client import OneFSClient
import os
os.environ['ONEFS_MOCK_MODE'] = 'false'
try:
    client = OneFSClient()
    client.test_connection()
    print('✓ Application connection successful')
    info = client.get_cluster_info()
    print(f'✓ Cluster info retrieved: {info.get(\"name\", \"Unknown\")}')
except Exception as e:
    print(f'✗ Application connection failed: {e}')
" 2>&1 | grep -E "(✓|✗|ERROR|WARNING|INFO)" || true
    else
        print_error "Failed to import OneFS client - check Python path"
    fi
}

main() {
    echo "=========================================="
    echo "OneFS SSH Setup Script"
    echo "=========================================="
    echo

    # Check if SSH directory exists
    check_ssh_dir

    # Menu
    while true; do
        echo "Choose an option:"
        echo "1) Generate SSH key"
        echo "2) Show public key"
        echo "3) Test SSH connection"
        echo "4) Update .env file"
        echo "5) Test application integration"
        echo "6) Exit"
        echo
        read -p "Enter your choice (1-6): " choice

        case $choice in
            1)
                create_ssh_key
                ;;
            2)
                show_public_key
                ;;
            3)
                test_ssh_connection
                ;;
            4)
                update_env_file
                ;;
            5)
                test_application
                ;;
            6)
                print_success "Setup complete!"
                exit 0
                ;;
            *)
                print_error "Invalid choice. Please enter 1-6."
                ;;
        esac
        echo
    done
}

# Run main function
main "$@"
