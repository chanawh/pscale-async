import pytest
from unittest.mock import Mock, patch, MagicMock
from src.onefs.client import OneFSClient, validate_log_path
from src.onefs.client import settings as onefs_settings


class TestOneFSClient:
    """Test OneFS client functionality"""

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'true'})
    def test_mock_mode_initialization(self):
        """Test client initializes in mock mode"""
        client = OneFSClient()
        assert client.mock_mode is True
        assert client.mock_server is not None

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'false',
                               'ONEFS_HOST': '203.0.113.10',
                               'ONEFS_USER': 'testuser',
                               'ONEFS_PASS': 'testpass'})
    @patch('src.onefs.client.socket.socket')
    @patch('src.onefs.client.paramiko.SSHClient')
    def test_real_mode_initialization(self, mock_ssh, mock_socket):
        """Test client initializes in real mode with env-configured host/user"""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.connect_ex.return_value = 0

        client = OneFSClient()
        assert client.mock_mode is False
        assert client.cluster_host == "203.0.113.10"
        assert client.username == "testuser"

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'false'})
    @patch.object(onefs_settings, 'onefs_host', None)
    @patch.object(onefs_settings, 'cluster_host', None)
    def test_real_mode_fails_fast_without_host(self):
        """Real mode refuses to start without ONEFS_HOST/CLUSTER_HOST configured"""
        with pytest.raises(RuntimeError, match="ONEFS_HOST"):
            OneFSClient()

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'false'})
    @patch.object(onefs_settings, 'onefs_host', '203.0.113.10')
    @patch.object(onefs_settings, 'onefs_user', None)
    @patch.object(onefs_settings, 'isilon_user', None)
    def test_real_mode_fails_fast_without_user(self):
        """Real mode refuses to start without ONEFS_USER/ISILON_USER configured"""
        with pytest.raises(RuntimeError, match="ONEFS_USER"):
            OneFSClient()

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'true'})
    def test_get_cluster_info_mock(self):
        """Test getting cluster info in mock mode"""
        client = OneFSClient()
        info = client.get_cluster_info()
        
        assert "name" in info
        assert "version" in info
        assert "nodes" in info
        assert info["name"] == "Demo OneFS Cluster"

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'true'})
    def test_list_log_files_mock(self):
        """Test listing log files in mock mode"""
        client = OneFSClient()
        files = client.list_log_files("/var/log")
        
        assert isinstance(files, list)
        assert "messages" in files
        assert "kern.log" in files

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'true'})
    def test_get_log_file_mock(self):
        """Test getting log file content in mock mode"""
        client = OneFSClient()
        content = client.get_log_file("/var/log/messages")
        
        assert isinstance(content, str)
        assert len(content) > 0
        assert "Mar 27" in content  # Mock log format

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'true'})
    def test_test_connection_mock(self):
        """Test connection test in mock mode"""
        client = OneFSClient()
        # Should not raise exception
        client.test_connection()

    @patch.dict('os.environ', {'ONEFS_MOCK_MODE': 'true'})
    def test_get_file_info_mock(self):
        """Test getting file info in mock mode"""
        client = OneFSClient()
        info = client.get_file_info("/var/log/messages")
        
        assert isinstance(info, dict)
        assert "size" in info
        assert "filename" in info


class TestValidateLogPath:
    """Command-injection guard tests for remote log paths"""

    def test_valid_path(self):
        assert validate_log_path("/var/log/messages") == "/var/log/messages"

    def test_valid_subdirectory(self):
        assert validate_log_path("/var/log/onefs/audit.log") == "/var/log/onefs/audit.log"

    def test_rejects_traversal(self):
        with pytest.raises(ValueError):
            validate_log_path("/var/log/../../etc/passwd")

    def test_rejects_encoded_traversal_parent(self):
        with pytest.raises(ValueError):
            validate_log_path("/var/log/..")

    def test_rejects_shell_metacharacters(self):
        for bad in [
            "/var/log/messages;id",
            "/var/log/$(id)",
            "/var/log/`id`",
            "/var/log/a|b",
            "/var/log/a&b",
            "/var/log/a\nb",
        ]:
            with pytest.raises(ValueError):
                validate_log_path(bad)

    def test_rejects_outside_base_dir(self):
        with pytest.raises(ValueError):
            validate_log_path("/etc/passwd")

    def test_rejects_relative_path(self):
        with pytest.raises(ValueError):
            validate_log_path("var/log/messages")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_log_path("")

    def test_custom_base_dir(self):
        assert validate_log_path("/ifs/logs/audit.log", base_dir="/ifs/logs") == "/ifs/logs/audit.log"
