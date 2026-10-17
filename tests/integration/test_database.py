"""Integration tests for database operations and migrations."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from src.db.database import Base, SessionLocal, get_db
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


class TestDatabaseConnection:
    """Test database connectivity and basic operations."""

    def test_database_connection(self, test_engine):
        """Test that database connection works."""
        # Try a simple query
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_tables_exist(self, test_engine):
        """Test that all expected tables exist."""
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()

        expected_tables = [
            "incidents",
            "nodes",
            "patterns",
            "jobs",
            "incident_activities",
        ]

        for table in expected_tables:
            assert table in tables, f"Table {table} does not exist"


class TestIncidentOperations:
    """Test incident CRUD operations."""

    def test_create_incident(self, test_db_session, test_node):
        """Test creating an incident."""
        # Create pattern
        pattern = Pattern(
            name="Test Pattern",
            regex_pattern=r"test",
            category="test",
            severity_level="HIGH",
        )
        test_db_session.add(pattern)
        test_db_session.commit()

        # Create job
        job = Job(id="test-job-db", filename="test.log", status=JobStatus.PENDING)
        test_db_session.add(job)
        test_db_session.commit()

        # Create incident
        incident = Incident(
            title="Database Test Incident",
            description="Test description",
            severity=Severity.CRITICAL,
            status=Status.OPEN,
            raw_log="Critical error in system",
            node_id=test_node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()
        test_db_session.refresh(incident)

        assert incident.id is not None
        assert incident.title == "Database Test Incident"
        assert incident.severity == Severity.CRITICAL

    def test_read_incident(self, test_db_session, test_node):
        """Test reading an incident."""
        pattern = Pattern(
            name="Read Test Pattern", regex_pattern=r"read", category="test"
        )
        test_db_session.add(pattern)
        test_db_session.commit()

        job = Job(id="read-job", filename="read.log", status=JobStatus.PENDING)
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Read Test",
            description="Read test",
            severity=Severity.HIGH,
            status=Status.OPEN,
            raw_log="Test log",
            node_id=test_node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()

        # Read back
        retrieved = (
            test_db_session.query(Incident)
            .filter(Incident.title == "Read Test")
            .first()
        )

        assert retrieved is not None
        assert retrieved.description == "Read test"

    def test_update_incident(self, test_db_session, test_node):
        """Test updating an incident."""
        pattern = Pattern(
            name="Update Test Pattern", regex_pattern=r"update", category="test"
        )
        test_db_session.add(pattern)
        test_db_session.commit()

        job = Job(id="update-job", filename="update.log", status=JobStatus.PENDING)
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Update Test",
            description="Original",
            severity=Severity.MEDIUM,
            status=Status.OPEN,
            raw_log="Test",
            node_id=test_node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()

        # Update
        incident.status = Status.IN_PROGRESS
        incident.description = "Updated description"
        test_db_session.commit()

        # Verify
        test_db_session.refresh(incident)
        assert incident.status == Status.IN_PROGRESS
        assert incident.description == "Updated description"

    def test_delete_incident(self, test_db_session, test_node):
        """Test deleting an incident."""
        pattern = Pattern(
            name="Delete Test Pattern", regex_pattern=r"delete", category="test"
        )
        test_db_session.add(pattern)
        test_db_session.commit()

        job = Job(id="delete-job", filename="delete.log", status=JobStatus.PENDING)
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Delete Test",
            description="To be deleted",
            severity=Severity.LOW,
            status=Status.OPEN,
            raw_log="Test",
            node_id=test_node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()

        incident_id = incident.id

        # Delete
        test_db_session.delete(incident)
        test_db_session.commit()

        # Verify deleted
        retrieved = (
            test_db_session.query(Incident).filter(Incident.id == incident_id).first()
        )
        assert retrieved is None


class TestNodeOperations:
    """Test node CRUD operations."""

    def test_create_node(self, test_db_session):
        """Test creating a node."""
        node = Node(
            hostname="test-node-create",
            ip_address="192.168.1.50",
            node_type="storage",
            version="9.5.0",
        )
        test_db_session.add(node)
        test_db_session.commit()
        test_db_session.refresh(node)

        assert node.id is not None
        assert node.hostname == "test-node-create"

    def test_node_hostname_unique(self, test_db_session):
        """Test that node hostnames must be unique."""
        node1 = Node(hostname="unique-host", ip_address="192.168.1.1")
        test_db_session.add(node1)
        test_db_session.commit()

        # Duplicate hostname should fail
        node2 = Node(hostname="unique-host", ip_address="192.168.1.2")
        test_db_session.add(node2)
        with pytest.raises(Exception):
            test_db_session.commit()


class TestPatternOperations:
    """Test pattern CRUD operations."""

    def test_create_pattern(self, test_db_session):
        """Test creating a pattern."""
        pattern = Pattern(
            name="Create Test Pattern",
            description="Test pattern",
            regex_pattern=r"create.*test",
            category="test",
            severity_level="MEDIUM",
            is_active=True,
        )
        test_db_session.add(pattern)
        test_db_session.commit()
        test_db_session.refresh(pattern)

        assert pattern.id is not None
        assert pattern.is_active is True

    def test_pattern_name_unique(self, test_db_session):
        """Test that pattern names must be unique."""
        pattern1 = Pattern(
            name="Unique Pattern Name", regex_pattern=r"test1", category="test"
        )
        test_db_session.add(pattern1)
        test_db_session.commit()

        # Duplicate name should fail
        pattern2 = Pattern(
            name="Unique Pattern Name", regex_pattern=r"test2", category="test"
        )
        test_db_session.add(pattern2)
        with pytest.raises(Exception):
            test_db_session.commit()

    def test_pattern_toggle_active(self, test_db_session):
        """Test toggling pattern active status."""
        pattern = Pattern(
            name="Toggle Test", regex_pattern=r"toggle", category="test", is_active=True
        )
        test_db_session.add(pattern)
        test_db_session.commit()

        # Toggle off
        pattern.is_active = False
        test_db_session.commit()
        test_db_session.refresh(pattern)

        assert pattern.is_active is False


class TestJobOperations:
    """Test job CRUD operations."""

    def test_create_job(self, test_db_session):
        """Test creating a job."""
        job = Job(
            id="create-job-test",
            filename="create.log",
            file_size=1024,
            status=JobStatus.PENDING,
            progress=0,
        )
        test_db_session.add(job)
        test_db_session.commit()
        test_db_session.refresh(job)

        assert job.id == "create-job-test"
        assert job.status == JobStatus.PENDING

    def test_job_progress_update(self, test_db_session):
        """Test updating job progress."""
        job = Job(
            id="progress-job",
            filename="progress.log",
            status=JobStatus.PROCESSING,
            progress=0,
        )
        test_db_session.add(job)
        test_db_session.commit()

        # Update progress
        job.progress = 50
        test_db_session.commit()
        test_db_session.refresh(job)

        assert job.progress == 50

    def test_job_status_transition(self, test_db_session):
        """Test job status transitions."""
        job = Job(id="status-job", filename="status.log", status=JobStatus.PENDING)
        test_db_session.add(job)
        test_db_session.commit()

        # Transition through statuses
        job.status = JobStatus.PROCESSING
        test_db_session.commit()
        assert job.status == JobStatus.PROCESSING

        job.status = JobStatus.COMPLETED
        test_db_session.commit()
        assert job.status == JobStatus.COMPLETED


class TestActivityOperations:
    """Test incident activity operations."""

    def test_create_activity(self, test_db_session, test_node):
        """Test creating an activity record."""
        pattern = Pattern(
            name="Activity Pattern", regex_pattern=r"activity", category="test"
        )
        test_db_session.add(pattern)
        test_db_session.commit()

        job = Job(id="activity-job", filename="activity.log", status=JobStatus.PENDING)
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Activity Test",
            description="Test",
            severity=Severity.MEDIUM,
            status=Status.OPEN,
            raw_log="Test",
            node_id=test_node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()
        test_db_session.refresh(incident)

        # Create activity
        activity = IncidentActivity(
            incident_id=incident.id,
            user_id="user-123",
            action_type=ActionType.COMMENT,
            description="Test activity",
        )
        test_db_session.add(activity)
        test_db_session.commit()
        test_db_session.refresh(activity)

        assert activity.id is not None
        assert activity.action_type == ActionType.COMMENT


class TestRelationships:
    """Test database relationships."""

    def test_incident_node_relationship(self, test_db_session, test_node):
        """Test incident-node relationship."""
        pattern = Pattern(name="Rel Pattern", regex_pattern=r"rel", category="test")
        test_db_session.add(pattern)
        test_db_session.commit()

        job = Job(id="rel-job", filename="rel.log", status=JobStatus.PENDING)
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Relationship Test",
            description="Test",
            severity=Severity.HIGH,
            status=Status.OPEN,
            raw_log="Test",
            node_id=test_node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()
        test_db_session.refresh(incident)

        # Verify relationship
        assert incident.node.hostname == test_node.hostname
        assert incident in test_node.incidents

    def test_incident_pattern_relationship(self, test_db_session, test_node):
        """Test incident-pattern relationship."""
        pattern = Pattern(name="Pattern Rel", regex_pattern=r"pattern", category="test")
        test_db_session.add(pattern)
        test_db_session.commit()

        job = Job(
            id="pattern-rel-job", filename="pattern.log", status=JobStatus.PENDING
        )
        test_db_session.add(job)
        test_db_session.commit()

        incident = Incident(
            title="Pattern Relationship Test",
            description="Test",
            severity=Severity.CRITICAL,
            status=Status.OPEN,
            raw_log="Test",
            node_id=test_node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()
        test_db_session.refresh(incident)

        # Verify relationship
        assert incident.pattern.name == "Pattern Rel"


class TestIndexes:
    """Test that indexes exist for performance."""

    def test_incident_indexes(self, test_engine):
        """Test incident table has indexes."""
        inspector = inspect(test_engine)
        indexes = inspector.get_indexes("incidents")
        index_names = [idx["name"] for idx in indexes]

        # Should have indexes on commonly queried columns
        assert any("severity" in name.lower() for name in index_names)
        assert any("status" in name.lower() for name in index_names)
        assert any("node" in name.lower() for name in index_names)

    def test_pattern_indexes(self, test_engine):
        """Test pattern table has indexes."""
        inspector = inspect(test_engine)
        indexes = inspector.get_indexes("patterns")
        index_names = [idx["name"] for idx in indexes]

        assert any("name" in name.lower() for name in index_names)
        assert any("category" in name.lower() for name in index_names)
