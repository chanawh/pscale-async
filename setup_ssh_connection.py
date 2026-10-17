#!/usr/bin/env python3
"""
Setup script for OneFS SSH connection
This script helps configure SSH access to a real OneFS cluster
"""

import os
import sys
from pathlib import Path

def setup_ssh_connection():
    """Guide user through SSH connection setup"""
    
    print("OneFS SSH Connection Setup")
    print("=" * 40)
    print()
    
    print("This script will help you configure SSH access to your OneFS cluster.")
    print("For development, mock mode is enabled by default.")
    print()
    
    # Get cluster configuration
    cluster_host = input("Enter OneFS cluster IP or hostname (default: localhost): ").strip()
    if not cluster_host:
        cluster_host = "localhost"
    
    ssh_port = input("Enter SSH port (default: 50019): ").strip()
    if not ssh_port:
        ssh_port = "50019"
    else:
        ssh_port = int(ssh_port)
    
    username = input("Enter SSH username (default: root): ").strip()
    if not username:
        username = "root"
    
    # Check for SSH key
    ssh_key_path = input("Enter SSH key path (default: ~/.ssh/id_ed25519): ").strip()
    if not ssh_key_path:
        ssh_key_path = str(Path.home() / ".ssh" / "id_ed25519")
    
    # Verify SSH key exists
    if not os.path.exists(os.path.expanduser(ssh_key_path)):
        print(f"Warning: SSH key not found at {ssh_key_path}")
        use_password = input("Use password authentication instead? (y/n): ").strip().lower()
        if use_password != 'y':
            print("Please generate an SSH key or provide the correct path.")
            return False
    
    # Create .env file
    env_content = f"""# OneFS Cluster Configuration
ONEFS_MOCK_MODE=false
ONEFS_HOST={cluster_host}
ONEFS_SSH_PORT={ssh_port}
ONEFS_API_PORT=8080
ONEFS_USER={username}
ONEFS_SSH_KEY_PATH={ssh_key_path}

# Optional: Set password if using password auth
# ONEFS_PASS=your_password_here
"""
    
    env_file = Path(".env")
    if env_file.exists():
        backup = env_file.with_suffix(".env.backup")
        env_file.rename(backup)
        print(f"Existing .env backed up to {backup}")
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"\nConfiguration saved to {env_file}")
    print("\nTo test the connection:")
    print("1. Restart the application")
    print("2. Check the cluster endpoints in the dashboard")
    print()
    
    # Test connection
    test_connection = input("Test SSH connection now? (y/n): ").strip().lower()
    if test_connection == 'y':
        try:
            from src.onefs.client import OneFSClient
            
            # Temporarily set environment variables
            os.environ['ONEFS_MOCK_MODE'] = 'false'
            os.environ['ONEFS_HOST'] = cluster_host
            os.environ['ONEFS_SSH_PORT'] = str(ssh_port)
            os.environ['ONEFS_USER'] = username
            os.environ['ONEFS_SSH_KEY_PATH'] = ssh_key_path
            
            client = OneFSClient()
            print(f"\nTesting connection to {cluster_host}:{ssh_port}...")
            
            result = client.test_connection()
            print("✅ Connection successful!")
            
            # Test a command
            status = client._run_ssh_command("echo 'SSH test successful'")
            print(f"Test command result: {status}")
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("\nTroubleshooting:")
            print("1. Verify the cluster IP/hostname is correct")
            print("2. Check that SSH port is accessible (firewall, network)")
            print("3. Verify SSH key permissions and user access")
            print("4. Ensure the OneFS user has SSH access")
    
    return True

if __name__ == "__main__":
    success = setup_ssh_connection()
    sys.exit(0 if success else 1)
