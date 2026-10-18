from fastapi.testclient import TestClient
from src.app.main import app
from src.api.routers.auth import get_current_user
from src.db.database import get_db


def _admin_user():
    # get_current_user returns a dict in production; the router-level
    # dependency discards the return value (it only needs to not raise),
    # so shape just needs to be truthy.
    return {
        "id": 1,
        "username": "admin",
        "email": "admin@test.com",
        "is_active": True,
        "is_superuser": True,
    }


class TestAdminRouter:
    """Test admin router endpoints (the real ones, not imagined ones).

    Router-level Depends(get_current_user) captures the function object
    at import time, so @patch on the module attribute has no effect --
    app.dependency_overrides is the only working mechanism.
    """

    def setup_method(self):
        """Setup test client with auth overridden."""
        app.dependency_overrides[get_current_user] = _admin_user
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_get_quick_queries(self):
        """Test the predefined query catalog endpoint (no DB needed)."""
        response = self.client.get("/api/v1/admin/quick-queries")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(q["name"] == "Recent Incidents" for q in data)

    def test_list_tables(self, override_get_db):
        """Test table listing against the test database."""
        app.dependency_overrides[get_db] = override_get_db

        response = self.client.get("/api/v1/admin/tables")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        names = {t["name"] for t in data}
        assert {"incidents", "jobs", "nodes", "patterns"} <= names
        assert all("column_count" in t for t in data)

    def test_execute_select_query(self, override_get_db):
        """Test a read-only SELECT through the query endpoint."""
        app.dependency_overrides[get_db] = override_get_db

        response = self.client.post(
            "/api/v1/admin/query", json={"query": "SELECT 1", "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["row_count"] == 1
        assert data["rows"][0] == {"?column?": 1} or len(data["rows"][0]) == 1

    def test_execute_forbidden_query_rejected(self, override_get_db):
        """Test that non-SELECT queries are rejected with 400."""
        app.dependency_overrides[get_db] = override_get_db

        response = self.client.post(
            "/api/v1/admin/query", json={"query": "DROP TABLE incidents"}
        )

        assert response.status_code == 400

    def test_unauthorized_access(self):
        """Documents current behavior for non-admin users.

        SECURITY NOTE: the admin router enforces authentication only --
        there is no superuser check, so any authenticated user currently
        receives 200 here, not 403. This test pins the actual behavior;
        tightening admin endpoints to superuser-only is a queued
        hardening item, at which point this assertion becomes 403.
        """
        app.dependency_overrides[get_current_user] = lambda: {
            "id": 2,
            "username": "user",
            "email": "user@test.com",
            "is_active": True,
            "is_superuser": False,
        }

        response = self.client.get("/api/v1/admin/quick-queries")

        assert response.status_code == 200
