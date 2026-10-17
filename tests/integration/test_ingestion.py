"""Integration tests for log ingestion endpoints."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.app.main import app
from src.db.database import get_db
from src.models import Incident, Job, JobStatus, Node, Pattern


@pytest.fixture
def client(override_get_db):
    """Create test client with DB override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_endpoint(self, client):
        """Test health check returns correct status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "database" in data


class TestFileIngestion:
    """Test file upload ingestion endpoint."""

    def test_upload_log_file(self, client, test_db_session, sample_log_file):
        """Test uploading a log file creates a job."""
        with open(sample_log_file, "rb") as f:
            response = client.post(
                "/api/v1/ingest",
                files={"file": ("test.log", f, "text/plain")},
                data={"node_hostname": "test-node-01", "description": "Test ingestion"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        # Status can be 'queued', 'completed', or 'failed' depending on Celery mode
        assert data["status"] in ["queued", "completed", "failed"]

        # Verify job was created in database
        job = test_db_session.query(Job).filter(Job.id == data["job_id"]).first()
        assert job is not None
        assert job.filename == "test.log"

    def test_upload_without_file(self, client):
        """Test upload without file returns error."""
        response = client.post("/api/v1/ingest", data={"node_hostname": "test-node"})
        assert response.status_code == 422

    def test_upload_invalid_file_type(self, client):
        """Test upload with invalid file type returns error."""
        response = client.post(
            "/api/v1/ingest",
            files={"file": ("test.exe", b"binary content", "application/octet-stream")},
        )
        # Should reject non-log files
        assert response.status_code in [400, 422, 500]


class TestStreamIngestion:
    """Test log stream ingestion endpoint."""

    def test_stream_log_lines(self, client, test_db_session):
        """Test streaming log lines creates a job."""
        log_lines = [
            "2024-01-01 10:00:00 INFO System started",
            "2024-01-01 10:01:00 ERROR Disk failure detected",
            "2024-01-01 10:02:00 WARNING Network timeout",
        ]

        response = client.post(
            "/api/v1/ingest/stream",
            json={
                "log_lines": log_lines,
                "node_hostname": "stream-test-node",
                "description": "Test stream ingestion",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        # Status can be 'queued', 'completed', or 'failed' depending on Celery mode
        assert data["status"] in ["queued", "completed", "failed"]

        # Verify job created
        job = test_db_session.query(Job).filter(Job.id == data["job_id"]).first()
        assert job is not None

        # Verify node was auto-created
        node = (
            test_db_session.query(Node)
            .filter(Node.hostname == "stream-test-node")
            .first()
        )
        assert node is not None

    def test_stream_empty_lines(self, client):
        """Test streaming empty log lines."""
        response = client.post(
            "/api/v1/ingest/stream",
            json={
                "log_lines": [],
                "node_hostname": "test-node",
                "description": "Empty test",
            },
        )

        # API correctly returns 400 for empty log lines
        assert response.status_code == 400


class TestJobManagement:
    """Test job management endpoints."""

    def test_list_jobs(self, client, test_db_session):
        """Test listing all jobs."""
        # Create a job first
        job = Job(
            id="test-job-list",
            filename="list-test.log",
            status=JobStatus.COMPLETED,
            progress=100,
        )
        test_db_session.add(job)
        test_db_session.commit()

        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "jobs" in data
        assert data["total"] >= 1

    def test_get_job_by_id(self, client, test_db_session):
        """Test getting a specific job."""
        job = Job(
            id="test-job-get",
            filename="get-test.log",
            status=JobStatus.PENDING,
            progress=0,
        )
        test_db_session.add(job)
        test_db_session.commit()

        response = client.get(f"/api/v1/jobs/{job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job.id
        assert data["filename"] == "get-test.log"

    def test_get_nonexistent_job(self, client):
        """Test getting a job that doesn't exist."""
        response = client.get("/api/v1/jobs/nonexistent-id")
        assert response.status_code == 404

    def test_cancel_job(self, client, test_db_session):
        """Test cancelling a pending job."""
        job = Job(
            id="test-job-cancel",
            filename="cancel-test.log",
            status=JobStatus.PENDING,
            progress=0,
        )
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/v1/jobs/{job.id}/cancel")
        assert response.status_code == 200

        # Verify job was cancelled
        test_db_session.refresh(job)
        assert job.status == JobStatus.FAILED


class TestIncidentEndpoints:
    """Test incident management endpoints."""

    def test_list_incidents(self, client, test_db_session, test_node, test_patterns):
        """Test listing incidents."""
        # Create a job and incident
        job = Job(
            id="incident-test-job",
            filename="incident-test.log",
            status=JobStatus.COMPLETED,
        )
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Test Incident",
            description="Test description",
            severity=test_patterns[0].severity_level,
            status="OPEN",
            raw_log="Test log line",
            node_id=test_node.id,
            pattern_id=test_patterns[0].id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()

        response = client.get("/api/v1/incidents")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "incidents" in data

    def test_filter_incidents_by_severity(
        self, client, test_db_session, test_node, test_patterns
    ):
        """Test filtering incidents by severity."""
        job = Job(
            id="severity-test-job",
            filename="severity-test.log",
            status=JobStatus.COMPLETED,
        )
        test_db_session.add(job)
        test_db_session.commit()

        # Create CRITICAL incident
        incident = Incident(
            title="Critical Test",
            description="Critical test",
            severity="CRITICAL",
            status="OPEN",
            raw_log="Critical error",
            node_id=test_node.id,
            pattern_id=test_patterns[0].id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()

        response = client.get("/api/v1/incidents?severity=CRITICAL")
        assert response.status_code == 200
        data = response.json()
        # Should only return critical incidents
        for inc in data["incidents"]:
            assert inc["severity"] == "CRITICAL"

    def test_get_incident_activity(
        self, client, test_db_session, test_node, test_patterns
    ):
        """Test getting incident activity history."""
        from src.models import ActionType, IncidentActivity

        job = Job(
            id="activity-test-job",
            filename="activity-test.log",
            status=JobStatus.COMPLETED,
        )
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Activity Test",
            description="Activity test",
            severity="HIGH",
            status="OPEN",
            raw_log="Test log",
            node_id=test_node.id,
            pattern_id=test_patterns[0].id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()
        test_db_session.refresh(incident)

        # Add activity
        activity = IncidentActivity(
            incident_id=incident.id,
            action_type=ActionType.COMMENT,
            description="Test comment",
        )
        test_db_session.add(activity)
        test_db_session.commit()

        response = client.get(f"/api/v1/incidents/{incident.id}/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["incident_id"] == incident.id
        assert len(data["activities"]) >= 1


class TestSummaryAndEscalations:
    """Test summary and escalations endpoints."""

    def test_get_summary(self, client, test_db_session, test_node, test_patterns):
        """Test getting system summary."""
        job = Job(
            id="summary-test-job",
            filename="summary-test.log",
            status=JobStatus.COMPLETED,
        )
        test_db_session.add(job)
        test_db_session.commit()

        # Create some incidents
        for i in range(3):
            incident = Incident(
                title=f"Summary Test {i}",
                description="Test",
                severity="HIGH" if i % 2 == 0 else "CRITICAL",
                status="OPEN",
                raw_log=f"Test {i}",
                node_id=test_node.id,
                pattern_id=test_patterns[0].id,
                job_id=job.id,
            )
            test_db_session.add(incident)
        test_db_session.commit()

        response = client.get("/api/v1/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_incidents" in data
        assert "by_severity" in data
        assert "by_status" in data

    def test_get_escalations(self, client, test_db_session, test_node, test_patterns):
        """Test getting escalations (critical open incidents)."""
        job = Job(
            id="escalation-test-job",
            filename="escalation-test.log",
            status=JobStatus.COMPLETED,
        )
        test_db_session.add(job)
        test_db_session.commit()

        # Create critical open incident
        incident = Incident(
            title="Critical Escalation Test",
            description="Critical test",
            severity="CRITICAL",
            status="OPEN",
            raw_log="Critical error",
            node_id=test_node.id,
            pattern_id=test_patterns[0].id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()

        response = client.get("/api/v1/escalations")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "escalations" in data
        # Should include our critical incident
        assert any(
            e["title"] == "Critical Escalation Test" for e in data["escalations"]
        )
