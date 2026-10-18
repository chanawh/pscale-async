from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from src.app.main import app
from src.api.routers.auth import get_current_user


def _admin_user():
    return {
        "id": 1,
        "username": "admin",
        "email": "admin@test.com",
        "is_active": True,
        "is_superuser": True,
    }


class TestClusterRouter:
    """Test cluster router endpoints.

    These target the live GET /api/v1/cluster/status handler in
    src/api/routers/cluster.py (the old duplicate in the ingest router
    was removed -- it was dead code returning fabricated demo data).
    """

    def setup_method(self):
        """Setup test client with auth overridden.

        Router-level Depends(get_current_user) captures the function
        object at import time, so @patch on the module attribute has no
        effect -- app.dependency_overrides is the only working mechanism.
        """
        app.dependency_overrides[get_current_user] = _admin_user
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch('src.api.routers.cluster.OneFSClient')
    def test_cluster_status_connected(self, mock_client_class):
        """Test cluster status when connected"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.test_connection.return_value = None
        mock_client.get_cluster_info.return_value = {
            "name": "Test Cluster",
            "version": "9.5.0",
            "nodes": 3
        }

        response = self.client.get("/api/v1/cluster/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert "cluster" in data
        assert "nodes" in data
        assert "metrics" in data
        assert data["cluster"]["version"] == "9.5.0"

    @patch('src.api.routers.cluster.OneFSClient')
    def test_cluster_status_connection_failure(self, mock_client_class):
        """Test cluster status returns 503 (not fabricated demo data) on error"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.test_connection.side_effect = Exception("Connection failed")

        response = self.client.get("/api/v1/cluster/status")

        # Honest failure, not demo_mode fabrications (removed with the
        # dead duplicate handler).
        assert response.status_code == 503

    @patch('src.api.routers.cluster.OneFSClient')
    def test_cluster_status_cluster_info(self, mock_client_class):
        """Test cluster info is reflected from the OneFS client"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.test_connection.return_value = None
        mock_client.get_cluster_info.return_value = {
            "name": "Production Cluster",
            "version": "9.7.0",
            "nodes": 5,
            "status": "healthy"
        }

        response = self.client.get("/api/v1/cluster/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["cluster"]["version"] == "9.7.0"
