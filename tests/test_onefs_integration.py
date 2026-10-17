import os
import tempfile
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.app.main import app
from src.db.database import Base, SessionLocal, engine
from src.models import Incident, Job, JobStatus, Node, Pattern
from src.workers.log_processor import create_default_patterns, process_log_file

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_patterns(db_session: Session):
    """Create test patterns including OneFS-specific ones"""
    create_default_patterns(db_session)
    return db_session.query(Pattern).all()


@pytest.fixture
def sample_onefs_log_lines():
    """Sample OneFS log lines for testing"""
    return [
        "Mar 27 10:15:32 node-01 isilon_d[1234]: [CRITICAL] System temperature exceeds threshold: 85C",
        "Mar 27 10:16:45 node-01 kernel: [ Hardware Error ] CPU temperature critical",
        "Mar 27 10:18:22 node-02 smartd[5678]: SMART failure predicted on device /dev/sda",
        "Mar 27 10:20:11 node-02 isi_pools_d[9012]: ERROR: Storage pool 'data_pool' status: DEGRADED",
        "Mar 27 10:22:33 node-01 isi_mcp_d[3456]: Cluster quorum lost, reforming cluster",
        "Mar 27 10:25:17 node-03 nfsd[7890]: NFS request timed out for client 192.168.1.100",
        "Mar 27 10:27:44 node-01 smbd[2345]: CIFS connection failed for user 'admin'",
        "Mar 27 10:30:12 node-02 krb5kdc[6789]: Kerberos ticket expired for user 'user1'",
        "Mar 27 10:32:55 node-01 sssd[8901]: LDAP connection timeout to dc.company.com",
        "Mar 27 10:35:28 node-03 auditd[1234]: SECURITY: Permission denied for access to /ifs/data/secret",
        "Mar 27 10:38:01 node-01 psu_monitor[4567]: Power supply PS-1 failure detected",
        "Mar 27 10:40:33 node-02 isi_job_d[5678]: Backup job 'nightly_backup' failed: Connection timeout",
    ]


class TestOneFSPatternMatching:
    """Test OneFS-specific pattern matching"""

    def test_onefs_critical_alert_pattern(self, db_session: Session, test_patterns):
        """Test OneFS critical alert pattern matching"""
        critical_pattern = (
            db_session.query(Pattern)
            .filter(Pattern.name == "OneFS System Alert")
            .first()
        )

        assert critical_pattern is not None
        assert critical_pattern.severity_level == "CRITICAL"
        assert "isilon_d.*critical" in critical_pattern.regex_pattern

        # Test pattern matches
        import re

        test_line = "Mar 27 10:15:32 node-01 isilon_d[1234]: [CRITICAL] System temperature exceeds threshold: 85C"
        assert (
            re.search(critical_pattern.regex_pattern, test_line, re.IGNORECASE)
            is not None
        )

    def test_smart_disk_failure_pattern(self, db_session: Session, test_patterns):
        """Test SMART disk failure pattern matching"""
        smart_pattern = (
            db_session.query(Pattern)
            .filter(Pattern.name == "SMART Disk Failure")
            .first()
        )

        assert smart_pattern is not None
        assert smart_pattern.severity_level == "CRITICAL"

        import re

        test_line = "Mar 27 10:18:22 node-02 smartd[5678]: SMART failure predicted on device /dev/sda"
        assert (
            re.search(smart_pattern.regex_pattern, test_line, re.IGNORECASE) is not None
        )

    def test_cluster_quorum_pattern(self, db_session: Session, test_patterns):
        """Test cluster quorum issue pattern matching"""
        quorum_pattern = (
            db_session.query(Pattern)
            .filter(Pattern.name == "Cluster Quorum Issue")
            .first()
        )

        assert quorum_pattern is not None
        assert quorum_pattern.severity_level == "CRITICAL"

        import re

        test_line = "Mar 27 10:22:33 node-01 isi_mcp_d[3456]: Cluster quorum lost, reforming cluster"
        assert (
            re.search(quorum_pattern.regex_pattern, test_line, re.IGNORECASE)
            is not None
        )

    def test_storage_pool_pattern(self, db_session: Session, test_patterns):
        """Test storage pool degraded pattern matching"""
        pool_pattern = (
            db_session.query(Pattern)
            .filter(Pattern.name == "Storage Pool Degraded")
            .first()
        )

        assert pool_pattern is not None
        assert pool_pattern.severity_level == "HIGH"

        import re

        test_line = "Mar 27 10:20:11 node-02 isi_pools_d[9012]: ERROR: Storage pool 'data_pool' status: DEGRADED"
        assert (
            re.search(pool_pattern.regex_pattern, test_line, re.IGNORECASE) is not None
        )


class TestOneFSLogProcessing:
    """Test OneFS log processing workflow"""

    def test_process_onefs_log_stream(
        self, db_session: Session, test_patterns, sample_onefs_log_lines
    ):
        """Test processing OneFS log lines via stream"""
        # Create test job
        job_id = "test-job-123"
        job = Job(
            id=job_id,
            filename="test_stream",
            file_size=len("\n".join(sample_onefs_log_lines)),
            status=JobStatus.PENDING,
        )
        db_session.add(job)
        db_session.commit()

        # Process log lines
        result = process_log_file(
            job_id=job_id,
            log_lines=sample_onefs_log_lines,
            node_hostname="node-01",
            description="OneFS test stream",
        )

        assert result["status"] == "completed"
        assert result["incidents_created"] > 0

        # Verify incidents created
        incidents = db_session.query(Incident).filter(Incident.job_id == job_id).all()
        assert len(incidents) > 0

        # Check for specific OneFS incidents
        critical_incidents = [i for i in incidents if i.severity.value == "CRITICAL"]
        assert len(critical_incidents) >= 3  # Temperature, SMART, cluster quorum

    def test_process_onefs_log_file(self, db_session: Session, test_patterns):
        """Test processing OneFS log file"""
        # Create temporary log file - use a proper directory
        import os
        temp_dir = os.path.expanduser("~")
        log_content = """Mar 27 10:15:32 node-01 isilon_d[1234]: [CRITICAL] System temperature exceeds threshold: 85C
Mar 27 10:18:22 node-02 smartd[5678]: SMART failure predicted on device /dev/sda
Mar 27 10:20:11 node-02 isi_pools_d[9012]: ERROR: Storage pool 'data_pool' status: DEGRADED
Mar 27 10:25:17 node-01 isi_mcp_d[3456]: Cluster quorum lost, reforming cluster"""

        temp_file = os.path.join(temp_dir, f"test_onefs_{os.getpid()}.log")
        try:
            with open(temp_file, "w") as f:
                f.write(log_content)

            # Create test job
            job_id = f"test-job-file-{os.getpid()}"
            job = Job(
                id=job_id,
                filename="test_onefs.txt",
                file_size=len(log_content),
                status=JobStatus.PENDING,
            )
            db_session.add(job)
            db_session.commit()

            # Process log file
            result = process_log_file(
                job_id=job_id,
                file_path=temp_file,
                node_hostname="node-01",
                description="OneFS test file",
            )

            assert result["status"] == "completed"
            assert result["incidents_created"] >= 4  # At least 4 lines should match patterns

        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


class TestOneFSAPIIntegration:
    """Test OneFS integration via API endpoints"""

    def test_ingest_onefs_log_stream(
        self, db_session: Session, test_patterns, sample_onefs_log_lines
    ):
        """Test ingesting OneFS log stream via API"""
        response = client.post(
            "/api/v1/ingest/stream",
            json={
                "log_lines": sample_onefs_log_lines,
                "node_hostname": "node-01",
                "description": "OneFS integration test",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

        # Verify job was created
        job = db_session.query(Job).filter(Job.id == data["job_id"]).first()
        assert job is not None
        assert job.filename == f"stream_{data['job_id']}"

    def test_get_onefs_incidents(self, db_session: Session, test_patterns):
        """Test retrieving OneFS-specific incidents"""
        # Create a test job
        job_id = "test-incidents-job"
        job = Job(
            id=job_id,
            filename="test_onefs.txt",
            file_size=100,
            status=JobStatus.COMPLETED,
        )
        db_session.add(job)
        db_session.commit()

        # Create some test incidents
        patterns = db_session.query(Pattern).all()
        node = Node(hostname="node-01", node_type="onefs")
        db_session.add(node)
        db_session.commit()

        # Create incidents with different categories
        for i, pattern in enumerate(patterns[:3]):
            incident = Incident(
                title=f"Test {pattern.name}",
                description=pattern.description,
                severity=pattern.severity_level,
                status="OPEN",
                raw_log=f"Test log line for {pattern.name}",
                node_id=node.id,
                pattern_id=pattern.id,
                job_id=job_id,  # Required foreign key
            )
            db_session.add(incident)

        db_session.commit()

        # Test filtering by category
        response = client.get("/api/v1/incidents?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "incidents" in data
        assert len(data["incidents"]) >= 3


class TestOneFSNodeHandling:
    """Test OneFS node-specific functionality"""

    def test_onefs_node_creation(self, db_session: Session, test_patterns):
        """Test automatic creation of OneFS nodes"""
        job_id = "test-node-job"
        job = Job(
            id=job_id, filename="test_node.txt", file_size=100, status=JobStatus.PENDING
        )
        db_session.add(job)
        db_session.commit()

        # Process with OneFS node hostname
        log_lines = [
            "Mar 27 10:15:32 onefs-node-01 isilon_d[1234]: [CRITICAL] System alert"
        ]

        result = process_log_file(
            job_id=job_id,
            log_lines=log_lines,
            node_hostname="onefs-node-01",
            description="OneFS node test",
        )

        # Verify node was created
        node = db_session.query(Node).filter(Node.hostname == "onefs-node-01").first()
        assert node is not None
        assert node.node_type == "unknown"  # Default type

        # Verify incident is linked to node
        incident = db_session.query(Incident).filter(Incident.job_id == job_id).first()
        assert incident is not None
        assert incident.node_id == node.id


class TestOneFSPerformance:
    """Test OneFS log processing performance"""

    def test_large_onefs_log_processing(self, db_session: Session, test_patterns):
        """Test processing large OneFS log files"""
        # Generate large log file
        log_lines = []
        base_timestamp = "Mar 27 10:"

        for i in range(1000):
            minute = f"{15 + (i % 45):02d}"
            log_lines.append(
                f"{base_timestamp}{minute}: node-{(i % 3) + 1:02d} isilon_d[{1234 + i}]: "
                f"[{'CRITICAL' if i % 10 == 0 else 'WARNING'}] System event {i}: "
                f"{'Temperature high' if i % 3 == 0 else 'Disk warning' if i % 3 == 1 else 'Network issue'}"
            )

        job_id = "test-large-job"
        job = Job(
            id=job_id,
            filename="large_onefs.txt",
            file_size=len("\n".join(log_lines)),
            status=JobStatus.PENDING,
        )
        db_session.add(job)
        db_session.commit()

        # Process large log
        result = process_log_file(
            job_id=job_id,
            log_lines=log_lines,
            node_hostname="node-cluster",
            description="Large OneFS log test",
        )

        assert result["status"] == "completed"
        assert result["total_lines"] == 1000
        assert result["incidents_created"] > 0
        assert result["processed_lines"] == 1000
