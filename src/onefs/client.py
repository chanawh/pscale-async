import base64
import logging
import re
import shlex
import socket
import os
import time
from urllib.parse import quote

import paramiko
import requests

from src.core.config import settings

logger = logging.getLogger(__name__)


class ReliableSSHConnection:
    """Reliable SSH connection with pooling, keepalive, and circuit breaker"""
    
    def __init__(self, host, port, username, password=None, key_path=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        
        # Connection pooling
        self._client = None
        self._last_used = 0
        self._connection_age = 300  # 5 minutes max connection age
        
        # Circuit breaker state
        self._circuit_state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._failure_count = 0
        self._success_count = 0
        self._failure_threshold = 5
        self._success_threshold = 3
        self._circuit_open_time = 0
        self._circuit_timeout = 60  # 60 seconds before trying again
        
        # Keepalive settings
        self._keepalive_interval = 30  # 30 seconds
        
    def _check_circuit(self):
        """Check if circuit breaker allows the request"""
        if self._circuit_state == 'CLOSED':
            return True
        elif self._circuit_state == 'OPEN':
            if time.time() - self._circuit_open_time > self._circuit_timeout:
                self._circuit_state = 'HALF_OPEN'
                self._success_count = 0
                logger.info("Circuit breaker: entering HALF_OPEN state")
                return True
            else:
                raise Exception(f"Circuit breaker OPEN - too many failures, retry after {self._circuit_timeout}s")
        elif self._circuit_state == 'HALF_OPEN':
            return True
        return False
    
    def _record_success(self):
        """Record successful operation"""
        self._failure_count = 0
        if self._circuit_state == 'HALF_OPEN':
            self._success_count += 1
            if self._success_count >= self._success_threshold:
                self._circuit_state = 'CLOSED'
                logger.info("Circuit breaker: CLOSED (recovered)")
    
    def _record_failure(self):
        """Record failed operation"""
        self._failure_count += 1
        if self._circuit_state == 'HALF_OPEN':
            self._circuit_state = 'OPEN'
            self._circuit_open_time = time.time()
            logger.warning("Circuit breaker: OPEN (failure in HALF_OPEN)")
        elif self._circuit_state == 'CLOSED' and self._failure_count >= self._failure_threshold:
            self._circuit_state = 'OPEN'
            self._circuit_open_time = time.time()
            logger.warning(f"Circuit breaker: OPEN after {self._failure_count} failures")
    
    def _is_connection_stale(self):
        """Check if connection is stale or too old"""
        if self._client is None:
            return True
        if time.time() - self._last_used > self._connection_age:
            return True
        # Test if connection is still alive
        try:
            transport = self._client.get_transport()
            if transport is None or not transport.is_active():
                return True
            # Send keepalive
            transport.send_ignore()
            return False
        except Exception:
            return True
    
    def _connect(self, timeout=30):
        """Create new SSH connection"""
        client = paramiko.SSHClient()
        # SECURITY: never silently trust unknown host keys. AutoAddPolicy
        # (the paramiko equivalent of StrictHostKeyChecking=no) makes the
        # connection trivially MITM-able. Trust sources, in order:
        #   1. ONEFS_HOST_KEY env var: base64-encoded raw host key blob
        #      (e.g. `ssh-keyscan -t ed25519 <host> | awk '{print $3}'`),
        #      with key type in ONEFS_HOST_KEY_TYPE (default ssh-ed25519).
        #   2. The local ~/.ssh/known_hosts file (load_system_host_keys).
        # Any host not covered by the above is rejected (RejectPolicy).
        client.load_system_host_keys()
        host_key_b64 = os.environ.get("ONEFS_HOST_KEY")
        if host_key_b64:
            key_type = os.environ.get("ONEFS_HOST_KEY_TYPE", "ssh-ed25519")
            key_cls = {
                "ssh-ed25519": paramiko.Ed25519Key,
                "ssh-rsa": paramiko.RSAKey,
                "ecdsa-sha2-nistp256": paramiko.ECDSAKey,
            }.get(key_type)
            if key_cls is None:
                raise ValueError(f"Unsupported ONEFS_HOST_KEY_TYPE: {key_type}")
            try:
                key = key_cls(data=base64.b64decode(host_key_b64))
            except Exception as e:
                raise ValueError(f"ONEFS_HOST_KEY is not valid base64 key material: {e}")
            client.get_host_keys().add(self.host, key_type, key)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        
        try:
            # Try key-based authentication first
            if self.key_path and os.path.exists(os.path.expanduser(self.key_path)):
                try:
                    client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.username,
                        key_filename=os.path.expanduser(self.key_path),
                        timeout=timeout,
                        banner_timeout=timeout,
                        auth_timeout=timeout,
                        look_for_keys=False,
                        allow_agent=False,
                    )
                    # Enable keepalive
                    transport = client.get_transport()
                    if transport:
                        transport.set_keepalive(self._keepalive_interval)
                    return client
                except paramiko.AuthenticationException:
                    logger.warning("Key auth failed, trying password")
            
            # Fallback to password authentication
            if self.password:
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=timeout,
                    banner_timeout=timeout,
                    auth_timeout=timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )
                # Enable keepalive
                transport = client.get_transport()
                if transport:
                    transport.set_keepalive(self._keepalive_interval)
                return client
            else:
                raise paramiko.AuthenticationException("No valid credentials provided")
                
        except Exception:
            client.close()
            raise
    
    def execute(self, command, timeout=30):
        """Execute SSH command with reliability features"""
        # Check circuit breaker
        self._check_circuit()
        
        # Check if connection is stale and reconnect if needed
        if self._is_connection_stale():
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            self._client = None
        
        # Get or create connection
        if self._client is None:
            self._client = self._connect(timeout)
        
        try:
            # Execute command
            stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            
            # Read output
            result = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            exit_code = stdout.channel.recv_exit_status()
            
            # Update last used time
            self._last_used = time.time()
            
            # Record success for circuit breaker
            self._record_success()
            
            if exit_code == 0:
                return result
            else:
                raise Exception(f"Command failed with exit code {exit_code}: {error}")
                
        except Exception as e:
            # Record failure for circuit breaker
            self._record_failure()
            
            # Close connection on error
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            self._client = None
            
            raise Exception(f"SSH execution failed: {str(e)}")
    
    def close(self):
        """Close the SSH connection"""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None


# Characters that are never allowed in remote file paths. Every call site also
# shlex-quotes the path because paramiko's exec_command always goes through
# the remote shell — this regex is defense in depth, not the primary guard.
_SHELL_METACHAR_RE = re.compile(r"[;&|$`\\(){}\[\]!#*?~<>\n\r]")


def validate_log_path(log_path: str, base_dir: str = "/var/log") -> str:
    """Strict allowlist validation for remote log file paths.

    Returns the normalized path. Raises ValueError unless the path is a
    non-empty absolute path that resolves under ``base_dir`` (no ``..``
    segments, no shell metacharacters). Callers must still pass the result
    through ``shlex.quote`` before embedding it in a remote command.
    """
    if not isinstance(log_path, str) or not log_path.strip():
        raise ValueError("log_path must be a non-empty string")
    candidate = log_path.strip()
    if _SHELL_METACHAR_RE.search(candidate):
        raise ValueError("log_path contains forbidden shell metacharacters")
    normalized = os.path.normpath(candidate)
    if not normalized.startswith("/"):
        raise ValueError("log_path must be an absolute path")
    # normpath collapses "..", so any surviving ".." segment is an escape attempt
    if ".." in [p for p in normalized.split("/") if p]:
        raise ValueError("log_path must not contain '..' segments")
    base = "/" + base_dir.strip("/").strip()
    if base != "/" and normalized != base and not normalized.startswith(base + "/"):
        raise ValueError(f"log_path must resolve under {base}")
    return normalized


class OneFSClient:
    """OneFS client for accessing cluster resources through SSH tunnel"""

    def __init__(self):
        # Check if we should use mock mode (development/demo)
        self.mock_mode = os.environ.get('ONEFS_MOCK_MODE', 'false').lower() == 'true'
        
        if self.mock_mode:
            logger.info("OneFS client running in MOCK mode - no real cluster connection")
            self._init_mock_mode()
        else:
            logger.info("OneFS client running in REAL mode - attempting cluster connection")
            self._init_real_mode()
            
        # Override with environment variable if set
        if os.environ.get('ONEFS_MOCK_MODE', 'false').lower() == 'true':
            self.mock_mode = True
            logger.info("Overriding to MOCK mode via environment variable")
    
    def _init_mock_mode(self):
        """Initialize mock mode for development"""
        from src.onefs.mock_ssh_server import create_mock_ssh_responses
        self.mock_ssh_command, self.mock_server = create_mock_ssh_responses()
        
        # Set mock connection details
        self.cluster_host = "mock-cluster.local"
        self.cluster_port = 22
        self.cluster_api_port = 8080
        self.username = "mock-user"
        self.password = "mock-pass"
        self.ssh_key_path = None
        self.base_url = f"https://{self.cluster_host}:{self.cluster_api_port}/platform/1"
        
    def _init_real_mode(self):
        """Initialize real cluster connection mode"""
        # Fail fast: there are no default cluster credentials or addresses.
        # For local development without a cluster, set ONEFS_MOCK_MODE=true.
        cluster_host = settings.onefs_host or settings.cluster_host
        cluster_user = settings.onefs_user or settings.isilon_user
        if not cluster_host or not cluster_user:
            raise RuntimeError(
                "OneFS cluster access requires ONEFS_HOST and ONEFS_USER "
                "environment variables (legacy aliases: CLUSTER_HOST / "
                "ISILON_USER). Set ONEFS_MOCK_MODE=true for local development "
                "without a cluster."
            )

        # Use tunnel connection first (when running in Docker/Podman)
        self.host = settings.isilon_host  # isilon-tunnel
        self.port = settings.isilon_port  # 8080

        # Direct cluster connection (fallback for local dev)
        self.cluster_host = cluster_host
        self.cluster_port = settings.cluster_port
        self.cluster_api_port = settings.cluster_api_port

        self.username = cluster_user
        self.password = settings.isilon_pass or settings.onefs_pass
        self.ssh_key_path = settings.ssh_key_path

        # For local development, always use SSH (no HTTP API service on localhost:8080)
        if self.host and self.host != "isilon-tunnel" and self.host != "localhost":
            self.base_url = f"https://{self.host}:{self.port}/platform/1"
        else:
            # Local development - use SSH only
            self.base_url = None  # Disable HTTP API

        # Only create session if we have HTTP API available
        if self.base_url:
            self.session = requests.Session()
            self.session.auth = (self.username, self.password)
            self.session.verify = False  # For self-signed certs
            self.session.headers.update(
                {"Accept": "application/json", "Content-Type": "application/json"}
            )
        else:
            self.session = None  # SSH only mode
        
        # Initialize reliable SSH connection for connection pooling
        self._ssh_connection = ReliableSSHConnection(
            host=self.cluster_host,
            port=self.cluster_port,
            username=self.username,
            password=self.password,
            key_path=self.ssh_key_path
        )

    def test_connection(self, max_retries=3):
        """Test connectivity to OneFS with retry logic"""
        for attempt in range(max_retries):
            try:
                # Always try SSH (primary method)
                result = self._run_ssh_command(
                    "echo 'SSH connection successful'", timeout=15, connect_timeout=10
                )
                if result and result.strip() == "SSH connection successful":
                    logger.info(f"SSH connection successful on attempt {attempt + 1}")
                    return True
            except Exception as ssh_error:
                logger.warning(f"SSH connection attempt {attempt + 1} failed: {ssh_error}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception(
                        f"SSH connection failed after {max_retries} attempts: {str(ssh_error)}"
                    )
        
        raise Exception("OneFS connection failed: SSH authentication failed")

    def get_log_file(self, log_path="/var/log/messages"):
        """Fetch log file content from OneFS through SSH tunnel.

        SECURITY: log_path is strictly validated (must resolve under
        settings.onefs_log_dir, no shell metacharacters) and shell-quoted —
        user input never reaches the remote shell raw, even though
        paramiko's exec_command always goes through it.
        """
        safe_path = validate_log_path(log_path, settings.onefs_log_dir)
        try:
            # Use SSH to fetch log file directly
            command = f"cat {shlex.quote(safe_path)}"
            result = self._run_ssh_command(command, timeout=30)

            if not result:
                raise Exception(f"No content returned from {log_path}")

            return result

        except Exception as e:
            # No HTTP API fallback for local development - SSH only
            raise Exception(f"Failed to fetch log from OneFS: SSH error={str(e)}")

    def get_cluster_info(self):
        """Get basic cluster information"""
        if self.mock_mode:
            # Return mock cluster info
            return self.mock_server.cluster_info
            
        # Try HTTP API first (tunnel)
        try:
            response = self.session.get(f"{self.base_url}/cluster", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as http_error:
            logger.warning(f"HTTP API failed: {http_error}")

        # Fallback to SSH
        try:
            # Get basic cluster info via SSH
            result = self._run_ssh_command("isi_config", timeout=15)
            if result:
                # Parse basic info from isi_config output
                return {
                    "name": "Unknown",
                    "version": "Unknown",
                    "nodes": 1,
                    "status": "connected_via_ssh",
                    "raw_config": result
                }
        except Exception as ssh_error:
            logger.error(f"SSH fallback failed: {ssh_error}")

        raise Exception("Failed to get cluster information via HTTP or SSH")

    def list_log_files(self, directory="/var/log"):
        """List available log files in a directory"""
        try:
            # Use SSH to list files (directory is shell-quoted; only the
            # validated get_log_file path above accepts user input)
            command = f"ls -la {shlex.quote(directory)} | grep '^-' | awk '{{print $9}}'"
            result = self._run_ssh_command(command, timeout=15)

            if result:
                files = [line.strip() for line in result.split("\n") if line.strip()]
                return [
                    f
                    for f in files
                    if f.endswith(".log") or f in ["messages", "syslog"]
                ]

            return []

        except Exception as e:
            # Fallback to HTTP API
            try:
                encoded_path = quote(directory)
                response = self.session.get(
                    f"{self.base_url}/filesystem/files{encoded_path}?list=true",
                    timeout=15,
                )
                response.raise_for_status()

                data = response.json()
                if "files" in data:
                    return [f["name"] for f in data["files"] if f.get("type") == "file"]
                return []

            except Exception as api_error:
                raise Exception(
                    f"Failed to list log files: SSH error={str(e)}, API error={str(api_error)}"
                )

    def get_file_info(self, file_path):
        """Get file metadata (size, modification time, etc.)"""
        try:
            # Use SSH to get file info (file_path is shell-quoted; the remote
            # shell never sees it raw)
            command = f"ls -lh {shlex.quote(file_path)} | awk '{{print $5, $6, $7, $8, $9}}'"
            result = self._run_ssh_command(command, timeout=10)

            if result:
                parts = result.strip().split()
                if len(parts) >= 5:
                    return {
                        "size": parts[0],
                        "date": " ".join(parts[1:4]),
                        "filename": parts[4] if len(parts) > 4 else file_path,
                        "method": "SSH",
                    }

            return {}

        except Exception as e:
            # Fallback to HTTP API
            try:
                encoded_path = quote(file_path)
                response = self.session.get(
                    f"{self.base_url}/filesystem/files{encoded_path}?metadata=true",
                    timeout=10,
                )
                response.raise_for_status()
                return response.json()
            except Exception as api_error:
                raise Exception(
                    f"Failed to get file info: SSH error={str(e)}, API error={str(api_error)}"
                )

    def _run_ssh_command(self, command, timeout=30, connect_timeout=10):
        """Run SSH command using ReliableSSHConnection with pooling and keepalive"""
        if self.mock_mode:
            # Use mock responses for development
            return self.mock_ssh_command(command, timeout)
        
        # Use reliable connection with pooling, keepalive, and circuit breaker
        try:
            return self._ssh_connection.execute(command, timeout=timeout)
        except Exception as e:
            logger.error(f"SSH command failed: {e}")
            raise Exception(f"SSH execution failed: {str(e)}")
