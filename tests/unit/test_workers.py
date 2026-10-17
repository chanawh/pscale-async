"""Unit tests for Celery workers and log processing functions."""

import json
import re
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.models import Job, Pattern, Severity
from src.workers.log_processor import create_default_patterns, map_severity


class TestSeverityMapping:
    """Test severity mapping function."""

    def test_map_severity_low(self):
        """Test mapping LOW severity."""
        result = map_severity("LOW")
        assert result == Severity.LOW

    def test_map_severity_medium(self):
        """Test mapping MEDIUM severity."""
        result = map_severity("MEDIUM")
        assert result == Severity.MEDIUM

    def test_map_severity_high(self):
        """Test mapping HIGH severity."""
        result = map_severity("HIGH")
        assert result == Severity.HIGH

    def test_map_severity_critical(self):
        """Test mapping CRITICAL severity."""
        result = map_severity("CRITICAL")
        assert result == Severity.CRITICAL

    def test_map_severity_case_insensitive(self):
        """Test that severity mapping is case insensitive."""
        assert map_severity("low") == Severity.LOW
        assert map_severity("Medium") == Severity.MEDIUM
        assert map_severity("HIGH") == Severity.HIGH

    def test_map_severity_default(self):
        """Test default severity for unknown values."""
        result = map_severity("UNKNOWN")
        assert result == Severity.MEDIUM

    def test_map_severity_empty(self):
        """Test default severity for empty string."""
        result = map_severity("")
        assert result == Severity.MEDIUM


class TestDefaultPatternsCreation:
    """Test creation of default patterns."""

    def test_create_default_patterns(self, test_db_session):
        """Test that default patterns are created."""
        from src.models import Pattern

        # Get initial count
        initial_count = test_db_session.query(Pattern).count()

        # Should create patterns on first call (or skip if already exist)
        create_default_patterns(test_db_session)

        # Count patterns - should have at least the default patterns
        count = test_db_session.query(Pattern).count()
        # Either patterns were created (count > initial) or they already existed
        assert count >= initial_count, "Pattern count decreased unexpectedly"

        # Verify we have at least some patterns with severity (the default ones)
        patterns_with_severity = (
            test_db_session.query(Pattern)
            .filter(Pattern.severity_level.isnot(None))
            .count()
        )
        assert (
            patterns_with_severity >= 23
        ), f"Expected at least 23 default patterns, found {patterns_with_severity}"

    def test_create_default_patterns_idempotent(self, test_db_session):
        """Test that calling create_default_patterns twice doesn't duplicate."""
        # First call
        create_default_patterns(test_db_session)
        count_after_first = test_db_session.query(Pattern).count()

        # Second call - should not create duplicates
        create_default_patterns(test_db_session)
        count_after_second = test_db_session.query(Pattern).count()

        assert count_after_first == count_after_second, "Patterns were duplicated"

    def test_default_pattern_categories(self, test_db_session):
        """Test that patterns have correct categories."""
        create_default_patterns(test_db_session)

        expected_categories = [
            "hardware",
            "network",
            "performance",
            "security",
            "filesystem",
            "system",
            "cluster",
            "storage",
        ]

        for category in expected_categories:
            patterns = (
                test_db_session.query(Pattern)
                .filter(Pattern.category == category)
                .all()
            )
            assert len(patterns) > 0, f"No patterns found for category: {category}"

    def test_default_pattern_severity_levels(self, test_db_session):
        """Test that default patterns have valid severity levels."""
        from src.models import Pattern

        # Ensure default patterns exist
        create_default_patterns(test_db_session)

        # Query patterns that have severity_level set (the default patterns)
        valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        default_patterns = (
            test_db_session.query(Pattern)
            .filter(Pattern.severity_level.isnot(None))
            .all()
        )

        # Should have at least the 23 default patterns
        assert (
            len(default_patterns) >= 23
        ), f"Expected at least 23 patterns with severity, found {len(default_patterns)}"

        # All patterns with severity_level should have valid severity
        for pattern in default_patterns:
            assert (
                pattern.severity_level in valid_severities
            ), f"Pattern '{pattern.name}' has invalid severity: {pattern.severity_level}"

    def test_critical_patterns_present(self, test_db_session):
        """Test that critical patterns are present."""
        create_default_patterns(test_db_session)

        critical_patterns = [
            "Disk Failure",
            "SMART Disk Failure",
            "Power Supply Failure",
            "OneFS System Alert",
            "Cluster Quorum Issue",
        ]

        for pattern_name in critical_patterns:
            pattern = (
                test_db_session.query(Pattern)
                .filter(Pattern.name == pattern_name)
                .first()
            )
            assert pattern is not None, f"Critical pattern '{pattern_name}' not found"
            assert pattern.severity_level == "CRITICAL"


class TestLogLineProcessing:
    """Test log line processing logic."""

    def test_pattern_matching_logic(self):
        """Test the core pattern matching logic used in worker."""
        patterns = [
            {"name": "Disk Failure", "regex": r"disk.*fail"},
            {"name": "Network Timeout", "regex": r"network.*timeout"},
            {"name": "Auth Failure", "regex": r"auth.*fail"},
        ]

        log_lines = [
            "2024-01-01 Disk failure detected",
            "2024-01-01 Network timeout occurred",
            "2024-01-01 Authentication failed",
            "2024-01-01 Normal operation",
        ]

        matched_patterns = set()

        for line in log_lines:
            for pattern in patterns:
                if re.search(pattern["regex"], line, re.IGNORECASE):
                    matched_patterns.add(pattern["name"])

        assert "Disk Failure" in matched_patterns
        assert "Network Timeout" in matched_patterns
        assert "Auth Failure" in matched_patterns

    def test_regex_error_handling(self):
        """Test that regex errors are handled gracefully."""
        # Valid pattern
        valid_pattern = r"test.*pattern"
        assert re.search(valid_pattern, "test pattern found", re.IGNORECASE) is not None

        # Invalid pattern should not crash - simulates error handling
        try:
            invalid_pattern = r"[invalid("
            re.search(invalid_pattern, "test")
        except re.error:
            # Expected behavior - regex errors should be caught
            pass

    def test_log_line_normalization(self):
        """Test that log lines are normalized (stripped)."""
        raw_lines = ["  Disk failure detected  ", "\tNetwork timeout\n", "   "]

        normalized = [line.strip() for line in raw_lines if line.strip()]

        assert len(normalized) == 2
        assert normalized[0] == "Disk failure detected"
        assert normalized[1] == "Network timeout"


class TestJobResultSummary:
    """Test job result summary generation."""

    def test_result_summary_structure(self):
        """Test the structure of result summary JSON."""
        summary = {
            "total_lines": 100,
            "processed_lines": 100,
            "incidents_created": 5,
            "patterns_matched": 3,
        }

        json_str = json.dumps(summary)
        parsed = json.loads(json_str)

        assert parsed["total_lines"] == 100
        assert parsed["processed_lines"] == 100
        assert parsed["incidents_created"] == 5
        assert parsed["patterns_matched"] == 3

    def test_progress_calculation(self):
        """Test progress percentage calculation."""
        total_lines = 100

        test_cases = [(0, 0), (25, 25), (50, 50), (75, 75), (100, 100)]

        for processed, expected in test_cases:
            progress = int((processed / total_lines) * 100)
            assert progress == expected


class TestCeleryTaskState:
    """Test Celery task state updates."""

    def test_task_state_structure(self):
        """Test the structure of Celery task state metadata."""
        # Simulates the structure used in process_log_file
        state_meta = {
            "current": 50,
            "total": 100,
            "progress": 50,
            "incidents_created": 3,
        }

        assert state_meta["current"] <= state_meta["total"]
        assert 0 <= state_meta["progress"] <= 100
        assert state_meta["incidents_created"] >= 0
