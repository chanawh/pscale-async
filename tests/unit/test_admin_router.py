import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.app.main import app
from src.models import User


class TestAdminRouter:
    """Test admin router endpoints"""

    def setup_method(self):
        """Setup test client and mock auth"""
        self.client = TestClient(app)
        # Mock admin user
        self.mock_user = User(
            id=1,
            username="admin",
            email="admin@test.com",
            is_active=True,
            is_superuser=True
        )

    @patch('src.api.routers.admin.get_current_user')
    def test_get_system_info(self, mock_auth):
        """Test getting system information"""
        mock_auth.return_value = self.mock_user
        
        response = self.client.get("/api/v1/admin/system/info")
        
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "environment" in data
        assert "database" in data

    @patch('src.api.routers.admin.get_current_user')
    @patch('src.api.routers.admin.SessionLocal')
    def test_get_database_stats(self, mock_session_local, mock_auth):
        """Test getting database statistics"""
        mock_auth.return_value = self.mock_user
        
        # Mock database session
        mock_session = Mock(spec=Session)
        mock_session_local.return_value = mock_session
        
        # Mock stats query results
        mock_session.query.return_value.count.return_value = 100
        mock_session.execute.return_value.fetchall.return_value = [
            ("incidents", 50),
            ("jobs", 25),
            ("nodes", 5),
            ("patterns", 20)
        ]

        response = self.client.get("/api/v1/admin/database/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_records" in data
        assert "table_counts" in data
        assert data["total_records"] == 100

    @patch('src.api.routers.admin.get_current_user')
    def test_get_health_check(self, mock_auth):
        """Test health check endpoint"""
        mock_auth.return_value = self.mock_user
        
        response = self.client.get("/api/v1/admin/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    @patch('src.api.routers.admin.get_current_user')
    def test_unauthorized_access(self, mock_auth):
        """Test that non-admin users cannot access admin endpoints"""
        # Mock non-admin user
        mock_user = User(
            id=2,
            username="user",
            email="user@test.com",
            is_active=True,
            is_superuser=False
        )
        mock_auth.return_value = mock_user
        
        response = self.client.get("/api/v1/admin/system/info")
        
        assert response.status_code == 403

    @patch('src.api.routers.admin.get_current_user')
    def test_cleanup_temp_files(self, mock_auth):
        """Test temporary files cleanup"""
        mock_auth.return_value = self.mock_user
        
        response = self.client.post("/api/v1/admin/cleanup/temp")
        
        assert response.status_code == 200
        data = response.json()
        assert "cleaned_files" in data
        assert "space_freed" in data
