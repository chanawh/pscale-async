"""Unit tests for database models."""

from datetime import datetime

import pytest

from src.models import (
    ActionType,
    Incident,
    IncidentActivity,
    Job,
    JobStatus,
    Node,
    Pattern,
    Severity,
    Status,
)


class TestIncidentModel:
    """Test Incident model creation and attributes."""

    def test_incident_creation(self, test_db_session):
        """Test creating an incident with all required fields."""
        # Create dependencies first with unique identifiers
        import time

        node = Node(
            hostname=f"incident-test-node-{time.time()}", ip_address="192.168.1.50"
        )
        test_db_session.add(node)
        test_db_session.commit()
        test_db_session.refresh(node)

        pattern = Pattern(
            name=f"Incident Test Pattern {time.time()}",
            regex_pattern=r"test",
            category="test",
        )
        test_db_session.add(pattern)
        test_db_session.commit()
        test_db_session.refresh(pattern)

        job = Job(
            id=f"incident-test-job-{time.time()}",
            filename="test.log",
            status=JobStatus.PENDING,
        )
        test_db_session.add(job)
        test_db_session.commit()

        # Now create incident with valid foreign keys
        incident = Incident(
            title="Test Incident",
            description="Test description",
            severity=Severity.CRITICAL,
            status=Status.OPEN,
            raw_log="Test log line",
            node_id=node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()
        test_db_session.refresh(incident)

        assert incident.id is not None
        assert incident.title == "Test Incident"
        assert incident.severity == Severity.CRITICAL
        assert incident.status == Status.OPEN
        assert incident.created_at is not None

    def test_incident_severity_enum(self):
        """Test Severity enum values."""
        assert Severity.LOW.value == "LOW"
        assert Severity.MEDIUM.value == "MEDIUM"
        assert Severity.HIGH.value == "HIGH"
        assert Severity.CRITICAL.value == "CRITICAL"

    def test_incident_status_enum(self):
        """Test Status enum values."""
        assert Status.OPEN.value == "OPEN"
        assert Status.IN_PROGRESS.value == "IN_PROGRESS"
        assert Status.RESOLVED.value == "RESOLVED"
        assert Status.ESCALATED.value == "ESCALATED"

    def test_incident_repr(self):
        """Test incident string representation."""
        incident = Incident(id=1, title="Test", severity=Severity.HIGH)
        assert "Incident" in repr(incident)
        assert "Test" in repr(incident)


class TestNodeModel:
    """Test Node model creation and attributes."""

    def test_node_creation(self, test_db_session):
        """Test creating a node."""
        import time

        node = Node(
            hostname=f"test-node-{time.time()}",
            ip_address="192.168.1.100",
            node_type="storage",
            version="9.5.0",
        )
        test_db_session.add(node)
        test_db_session.commit()
        test_db_session.refresh(node)

        assert node.id is not None
        assert node.hostname.startswith("test-node-")
        assert node.ip_address == "192.168.1.100"
        assert node.node_type == "storage"

    def test_node_repr(self):
        """Test node string representation."""
        node = Node(id=1, hostname="test-node")
        assert "Node" in repr(node)
        assert "test-node" in repr(node)


class TestPatternModel:
    """Test Pattern model creation and attributes."""

    def test_pattern_creation(self, test_db_session):
        """Test creating a pattern."""
        import time

        pattern = Pattern(
            name=f"Test Pattern {time.time()}",
            description="Test pattern description",
            regex_pattern=r"test.*pattern",
            category="test",
            severity_level="HIGH",
            is_active=True,
        )
        test_db_session.add(pattern)
        test_db_session.commit()
        test_db_session.refresh(pattern)

        assert pattern.id is not None
        assert pattern.name.startswith("Test Pattern")
        assert pattern.regex_pattern == r"test.*pattern"
        assert pattern.is_active is True

    def test_pattern_unique_name(self, test_db_session):
        """Test that pattern names must be unique."""
        pattern1 = Pattern(
            name="Unique Pattern", regex_pattern=r"test1", category="test"
        )
        test_db_session.add(pattern1)
        test_db_session.commit()

        # Attempting to add duplicate should fail at DB level
        # This test documents the constraint
        duplicate = Pattern(
            name="Unique Pattern", regex_pattern=r"test2", category="test"
        )
        test_db_session.add(duplicate)
        with pytest.raises(Exception):
            test_db_session.commit()

    def test_pattern_repr(self):
        """Test pattern string representation."""
        pattern = Pattern(id=1, name="TestPattern", category="test")
        assert "Pattern" in repr(pattern)
        assert "TestPattern" in repr(pattern)


class TestJobModel:
    """Test Job model creation and attributes."""

    def test_job_creation(self, test_db_session):
        """Test creating a job."""
        job = Job(
            id="test-job-uuid",
            filename="test.log",
            file_size=1024,
            status=JobStatus.PENDING,
            progress=0,
        )
        test_db_session.add(job)
        test_db_session.commit()
        test_db_session.refresh(job)

        assert job.id == "test-job-uuid"
        assert job.filename == "test.log"
        assert job.status == JobStatus.PENDING
        assert job.progress == 0

    def test_job_status_enum(self):
        """Test JobStatus enum values."""
        assert JobStatus.PENDING.value == "PENDING"
        assert JobStatus.PROCESSING.value == "PROCESSING"
        assert JobStatus.COMPLETED.value == "COMPLETED"
        assert JobStatus.FAILED.value == "FAILED"

    def test_job_repr(self):
        """Test job string representation."""
        job = Job(id="test-123", status=JobStatus.PROCESSING, progress=50)
        assert "Job" in repr(job)
        assert "test-123" in repr(job)


class TestIncidentActivityModel:
    """Test IncidentActivity model creation and attributes."""

    def test_activity_creation(self, test_db_session):
        """Test creating an activity record."""
        # Create incident first with unique identifiers
        import time

        node = Node(hostname=f"activity-node-{time.time()}", ip_address="192.168.1.50")
        test_db_session.add(node)
        test_db_session.commit()

        pattern = Pattern(
            name=f"Activity Pattern {time.time()}",
            regex_pattern=r"activity",
            category="test",
        )
        test_db_session.add(pattern)
        test_db_session.commit()

        job = Job(
            id=f"activity-job-{time.time()}",
            filename="activity.log",
            status=JobStatus.PENDING,
        )
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Activity Test Incident",
            description="Test",
            severity=Severity.HIGH,
            status=Status.OPEN,
            raw_log="Test log",
            node_id=node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()
        test_db_session.refresh(incident)

        # Now create activity with valid incident_id
        activity = IncidentActivity(
            incident_id=incident.id,
            user_id="user-123",
            action_type=ActionType.COMMENT,
            description="Test comment",
            details='{"key": "value"}',
        )
        test_db_session.add(activity)
        test_db_session.commit()
        test_db_session.refresh(activity)

        assert activity.id is not None
        assert activity.action_type == ActionType.COMMENT
        assert activity.description == "Test comment"
        assert activity.created_at is not None

    def test_action_type_enum(self):
        """Test ActionType enum values."""
        assert ActionType.START_WORK.value == "START_WORK"
        assert ActionType.ESCALATE.value == "ESCALATE"
        assert ActionType.RESOLVE.value == "RESOLVE"
        assert ActionType.COMMENT.value == "COMMENT"
        assert ActionType.ASSIGN.value == "ASSIGN"

    def test_activity_repr(self):
        """Test activity string representation."""
        activity = IncidentActivity(
            id=1, incident_id=5, action_type=ActionType.ESCALATE
        )
        assert "IncidentActivity" in repr(activity)
        assert "5" in repr(activity)
