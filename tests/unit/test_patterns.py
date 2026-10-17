"""Unit tests for pattern matching and pattern-related logic."""

import re
from datetime import datetime

import pytest

from src.models import Incident, Job, JobStatus, Node, Pattern, Severity, Status
from src.workers.log_processor import create_default_patterns


class TestPatternRegexMatching:
    """Test pattern regex matching functionality."""

    def test_disk_failure_pattern(self):
        """Test disk failure pattern matches."""
        pattern = r"(disk|drive).*fail|(error|critical).*disk"

        test_cases = [
            ("Disk failure detected on /dev/sda", True),
            ("Drive failed after power outage", True),
            ("Critical disk error in sector 5", True),
            ("System is running normally", False),
        ]

        for log_line, should_match in test_cases:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if should_match:
                assert match is not None, f"Expected match for: {log_line}"
            else:
                assert match is None, f"Expected no match for: {log_line}"

    def test_network_timeout_pattern(self):
        """Test network timeout pattern matches."""
        pattern = r"network.*timeout|connection.*timeout"

        test_cases = [
            ("Network timeout occurred during backup", True),
            ("Connection timeout to 192.168.1.1", True),
            ("TCP connection established", False),
        ]

        for log_line, should_match in test_cases:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if should_match:
                assert match is not None, f"Expected match for: {log_line}"
            else:
                assert match is None, f"Expected no match for: {log_line}"

    def test_onefs_system_alert_pattern(self):
        """Test OneFS system alert pattern."""
        pattern = r"isilon_d.*critical|isi.*critical|system.*alert"

        test_cases = [
            ("Mar 27 10:15:32 node-01 isilon_d[1234]: [CRITICAL] System failure", True),
            ("isi_daemon critical error detected", True),
            ("System alert: Temperature threshold exceeded", True),
            ("Normal system operation", False),
        ]

        for log_line, should_match in test_cases:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if should_match:
                assert match is not None, f"Expected match for: {log_line}"
            else:
                assert match is None, f"Expected no match for: {log_line}"

    def test_cluster_quorum_pattern(self):
        """Test cluster quorum issue pattern."""
        pattern = r"cluster.*quorum|node.*disconnect|cluster.*reform|gmp.*fail"

        test_cases = [
            ("Cluster quorum lost, node-02 disconnected", True),
            ("GMP failure detected in cluster", True),
            ("Cluster reform initiated", True),
            ("Node connected successfully", False),
        ]

        for log_line, should_match in test_cases:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if should_match:
                assert match is not None, f"Expected match for: {log_line}"
            else:
                assert match is None, f"Expected no match for: {log_line}"

    def test_smart_disk_failure_pattern(self):
        """Test SMART disk failure pattern."""
        pattern = r"smartd.*fail|smart.*error|disk.*predict.*fail|drive.*fail"

        test_cases = [
            ("smartd reported disk failure on /dev/sda", True),
            ("SMART error detected in self-test", True),
            ("Disk predicted to fail within 24 hours", True),
            ("Drive failed and taken offline", True),
            ("Normal disk operation", False),
        ]

        for log_line, should_match in test_cases:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if should_match:
                assert match is not None, f"Expected match for: {log_line}"
            else:
                assert match is None, f"Expected no match for: {log_line}"

    def test_authentication_failure_pattern(self):
        """Test authentication failure pattern."""
        pattern = r"auth.*fail|login.*fail|authentication.*error"

        test_cases = [
            ("Authentication failed for user admin", True),
            ("Login failed: invalid credentials", True),
            ("Authentication error in kerberos", True),
            ("User logged in successfully", False),
        ]

        for log_line, should_match in test_cases:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if should_match:
                assert match is not None, f"Expected match for: {log_line}"
            else:
                assert match is None, f"Expected no match for: {log_line}"


class TestPatternModelBehavior:
    """Test Pattern model behavior and relationships."""

    def test_pattern_is_active_default(self, test_db_session):
        """Test that patterns are active by default."""
        pattern = Pattern(
            name="Default Active Pattern", regex_pattern=r"test", category="test"
        )
        test_db_session.add(pattern)
        test_db_session.commit()
        test_db_session.refresh(pattern)

        assert pattern.is_active is True

    def test_pattern_category_assignment(self, test_db_session):
        """Test pattern category field."""
        categories = ["system", "hardware", "network", "security", "storage"]

        for i, category in enumerate(categories):
            pattern = Pattern(
                name=f"Category Test {i}",
                regex_pattern=r"test",
                category=category,
                severity_level="MEDIUM",
            )
            test_db_session.add(pattern)

        test_db_session.commit()

        # Verify all categories stored correctly
        for category in categories:
            found = (
                test_db_session.query(Pattern)
                .filter(Pattern.category == category)
                .first()
            )
            assert found is not None

    def test_default_pattern_severity_levels(self, test_db_session):
        """Test that default patterns have valid severity levels."""
        create_default_patterns(test_db_session)

        # Query only patterns created by create_default_patterns (those with non-null severity_level)
        valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        default_patterns = (
            test_db_session.query(Pattern)
            .filter(Pattern.severity_level.isnot(None))
            .all()
        )

        assert len(default_patterns) > 0, "No default patterns found"

        for pattern in default_patterns:
            assert (
                pattern.severity_level in valid_severities
            ), f"Pattern '{pattern.name}' has invalid severity: {pattern.severity_level}"

    def test_pattern_severity_levels(self, test_db_session):
        """Test pattern severity levels."""
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        for i, severity in enumerate(severities):
            pattern = Pattern(
                name=f"Severity Test {i} {datetime.now().timestamp()}",
                regex_pattern=r"test",
                category="test",
                severity_level=severity,
            )
            test_db_session.add(pattern)

        test_db_session.commit()

        # Verify each severity exists
        for severity in severities:
            count = (
                test_db_session.query(Pattern)
                .filter(Pattern.severity_level == severity)
                .count()
            )
            assert count >= 1, f"No patterns found with severity {severity}"


class TestPatternIncidentRelationship:
    """Test relationship between patterns and incidents."""

    def test_pattern_incidents_relationship(self, test_db_session):
        """Test that patterns can be linked to incidents."""
        from datetime import datetime

        from src.models import Job

        # Create unique node
        node = Node(
            hostname=f"rel-test-node-{datetime.now().timestamp()}",
            ip_address="192.168.1.100",
        )
        test_db_session.add(node)
        test_db_session.commit()
        test_db_session.refresh(node)

        # Create a pattern with unique name
        pattern = Pattern(
            name=f"Test Pattern {datetime.now().timestamp()}",
            regex_pattern=r"error",
            category="test",
            severity_level="HIGH",
        )
        test_db_session.add(pattern)
        test_db_session.commit()
        test_db_session.refresh(pattern)

        # Create a job with unique ID
        job = Job(
            id=f"test-job-{datetime.now().timestamp()}",
            filename="test.log",
            status=JobStatus.PENDING,
        )
        test_db_session.add(job)
        test_db_session.commit()

        # Create an incident linked to the pattern
        incident = Incident(
            title="Pattern Match: Test Pattern",
            description="Test incident",
            severity=Severity.HIGH,
            status=Status.OPEN,
            raw_log="Error detected",
            node_id=node.id,
            pattern_id=pattern.id,
            job_id=job.id,
        )
        test_db_session.add(incident)
        test_db_session.commit()
        test_db_session.refresh(incident)

        # Verify relationship
        assert incident.pattern_id == pattern.id
        assert pattern.name in incident.pattern.name

    def test_incident_count_per_pattern(self, test_db_session):
        """Test counting incidents per pattern."""
        from datetime import datetime

        from src.models import Job

        # Create unique node
        node = Node(
            hostname=f"count-test-node-{datetime.now().timestamp()}",
            ip_address="192.168.1.100",
        )
        test_db_session.add(node)
        test_db_session.commit()
        test_db_session.refresh(node)

        # Create pattern with unique name
        pattern = Pattern(
            name=f"Count Test Pattern {datetime.now().timestamp()}",
            regex_pattern=r"error",
            category="test",
            severity_level="HIGH",
        )
        test_db_session.add(pattern)
        test_db_session.commit()
        test_db_session.refresh(pattern)

        # Create job with unique ID
        job = Job(
            id=f"count-test-job-{datetime.now().timestamp()}",
            filename="test.log",
            status=JobStatus.PENDING,
        )
        test_db_session.add(job)
        test_db_session.commit()

        # Create multiple incidents
        for i in range(5):
            incident = Incident(
                title=f"Incident {i}",
                description="Test",
                severity=Severity.HIGH,
                status=Status.OPEN,
                raw_log=f"Error {i}",
                node_id=node.id,
                pattern_id=pattern.id,
                job_id=job.id,
            )
            test_db_session.add(incident)

        test_db_session.commit()

        # Count incidents
        from sqlalchemy import func

        count = (
            test_db_session.query(func.count(Incident.id))
            .filter(Incident.pattern_id == pattern.id)
            .scalar()
        )

        assert count == 5
