import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from src.app.main import app


class TestClusterRouter:
    """Test cluster router endpoints"""

    def setup_method(self):
        """Setup test client"""
        self.client = TestClient(app)

    @patch('src.api.routers.cluster.OneFSClient')
    def test_cluster_status_connected(self, mock_client_class):
        """Test cluster status when connected"""
        # Mock successful connection
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.test_connection.return_value = None
        mock_client.get_cluster_info.return_value = {
            "name": "Test Cluster",
            "version": "9.5.0",
            "nodes": 3
        }
        mock_client.list_log_files.return_value = ["messages", "syslog"]

        response = self.client.get("/api/v1/cluster/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert "cluster" in data
        assert "available_log_files" in data

    @patch('src.api.routers.cluster.OneFSClient')
    def test_cluster_status_demo_mode(self, mock_client_class):
        """Test cluster status falls back to demo mode on error"""
        # Mock connection failure
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.test_connection.side_effect = Exception("Connection failed")

        response = self.client.get("/api/v1/cluster/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "demo_mode"
        assert "cluster" in data
        assert data["cluster"]["name"] == "Demo OneFS Cluster"

    @patch('src.api.routers.cluster.OneFSClient')
    def test_cluster_status_with_real_connection(self, mock_client_class):
        """Test cluster status with real OneFS connection"""
        # Mock real cluster data
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.test_connection.return_value = None
        mock_client.get_cluster_info.return_value = {
            "name": "Production Cluster",
            "version": "9.7.0",
            "nodes": 5,
            "status": "healthy"
        }
        mock_client.list_log_files.return_value = [
            "messages", "kern.log", "auth.log", "daemon.log"
        ]

        response = self.client.get("/api/v1/cluster/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["cluster"]["name"] == "Production Cluster"
        assert data["cluster"]["version"] == "9.7.0"
        assert len(data["available_log_files"]) == 4
