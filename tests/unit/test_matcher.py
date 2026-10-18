"""Unit tests for the single-pass regex matching engine.

``src.workers.matcher`` is stdlib-only on purpose, so these tests run
without Celery, SQLAlchemy, or any infrastructure. Patterns are
duck-typed (SimpleNamespace) — the engine only needs .id, .name,
.regex_pattern and .severity_level.
"""

from types import SimpleNamespace

import pytest

from src.workers.matcher import (
    compile_matcher,
    match_line,
    sanitize_user_pattern,
    severity_rank,
)


def make_pattern(pid, name, regex, severity="MEDIUM"):
    return SimpleNamespace(
        id=pid, name=name, regex_pattern=regex, severity_level=severity
    )


@pytest.fixture
def library():
    # Mirrors the shape of the default OneFS pattern library: several
    # severities, overlapping patterns, one bad regex.
    return [
        make_pattern(1, "Disk Failure", r"(disk|drive).*fail", "CRITICAL"),
        make_pattern(2, "SMART Disk Failure", r"smart.*fail|drive.*fail", "CRITICAL"),
        make_pattern(3, "Network Timeout", r"network.*timeout", "HIGH"),
        make_pattern(4, "High CPU Usage", r"cpu.*high", "MEDIUM"),
        make_pattern(5, "Auth Failure", r"auth.*fail|login.*fail", "MEDIUM"),
        make_pattern(6, "NFS Timeout", r"nfs.*timeout", "MEDIUM"),
        make_pattern(7, "Broken Pattern", r"(unclosed[group", "LOW"),
    ]


class TestSeverityOrdering:
    def test_critical_beats_lower_severities(self, library):
        m = compile_matcher(library)
        # "drive fail" matches both CRITICAL patterns 1 and 2.
        winner = match_line(m, "disk drive fail on node 3")
        assert winner is not None
        assert winner.severity_level == "CRITICAL"

    def test_tie_broken_by_lowest_pattern_id(self, library):
        m = compile_matcher(library)
        # Matches patterns 1 and 2, both CRITICAL -> lowest id wins.
        winner = match_line(m, "drive fail detected by smartd")
        assert winner is not None
        assert winner.id == 1

    def test_high_beats_medium(self, library):
        m = compile_matcher(library)
        winner = match_line(m, "network timeout on nfs mount")
        # "network.*timeout" (HIGH) vs "nfs.*timeout" (MEDIUM)
        assert winner.name == "Network Timeout"

    def test_unknown_severity_sorts_after_low(self):
        p_weird = make_pattern(9, "Weird", r"weird.*thing", "BOGUS")
        p_low = make_pattern(10, "Low Thing", r"weird.*thing", "LOW")
        m = compile_matcher([p_weird, p_low])
        assert match_line(m, "weird thing happened").id == 10

    def test_severity_rank_values(self):
        assert severity_rank("CRITICAL") < severity_rank("HIGH")
        assert severity_rank("HIGH") < severity_rank("MEDIUM")
        assert severity_rank("MEDIUM") < severity_rank("LOW")
        assert severity_rank("low") == severity_rank("LOW")
        assert severity_rank("nonsense") > severity_rank("LOW")


class TestFirstMatchWins:
    def test_one_line_yields_one_winner(self, library):
        m = compile_matcher(library)
        # Old loop would create an incident per matching pattern;
        # the engine returns exactly one winner.
        winner = match_line(m, "drive fail")
        assert winner is not None
        assert isinstance(winner.name, str)

    def test_no_match_returns_none(self, library):
        m = compile_matcher(library)
        assert match_line(m, "totally benign log line about nothing") is None

    def test_matching_is_case_insensitive(self, library):
        m = compile_matcher(library)
        assert match_line(m, "CPU HIGH alert") is not None
        assert match_line(m, "CPU HIGH alert").name == "High CPU Usage"


class TestSanitization:
    def test_user_named_group_neutralized(self):
        p = make_pattern(20, "Named", r"(?P<disk>disk) (?P<state>\w+)", "HIGH")
        assert sanitize_user_pattern(p.regex_pattern) == r"(?:disk) (?:\w+)"
        m = compile_matcher([p])
        assert m.skipped == []
        winner = match_line(m, "disk failed")
        assert winner is not None and winner.id == 20

    def test_engine_group_names_survive_user_groups(self):
        p1 = make_pattern(21, "A", r"(?P<x>alpha) beta", "MEDIUM")
        p2 = make_pattern(22, "B", r"(?P<x>gamma) delta", "MEDIUM")
        # Both users chose group name "x" — must not collide.
        m = compile_matcher([p1, p2])
        assert m.skipped == []
        assert match_line(m, "alpha beta").id == 21
        assert match_line(m, "gamma delta").id == 22

    def test_named_group_inside_character_class_untouched(self):
        # "[(?P<x>]" is a literal character class, not a group.
        assert sanitize_user_pattern(r"[(?P<x>]") == r"[(?P<x>]"

    def test_escaped_paren_untouched(self):
        assert sanitize_user_pattern(r"\(literal\) (?P<g>x)") == r"\(literal\) (?:x)"

    def test_named_backref_to_neutralized_group_skips_pattern(self):
        p = make_pattern(23, "Backref", r"(?P<w>\w+) (?P=w)", "HIGH")
        m = compile_matcher([p])
        # (?P=w) can no longer resolve after neutralization -> skipped loudly.
        assert m.skipped == ["Backref"]
        assert len(m) == 0


class TestInvalidPatterns:
    def test_bad_regex_skipped_with_warning(self, library, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            m = compile_matcher(library)
        assert "Broken Pattern" in m.skipped
        assert len(m) == 6
        assert any("Broken Pattern" in r.getMessage() for r in caplog.records)

    def test_bad_pattern_does_not_poison_others(self, library):
        m = compile_matcher(library)
        assert match_line(m, "network timeout").name == "Network Timeout"

    def test_empty_pattern_list_never_matches(self):
        m = compile_matcher([])
        assert len(m) == 0
        assert match_line(m, "disk fail") is None


class TestOldLoopEquivalence:
    """The engine's winner must match regex-alternation semantics: among
    everything the old per-pattern loop matched, the winner is the
    leftmost match; ties at the same start position go to the lowest
    branch order (severity rank, then pattern id).

    Note this is NOT "globally highest severity wins regardless of
    position" — e.g. on "smartd reports drive fail predicted", SMART
    Disk Failure wins because "smart" matches at position 0, before
    "drive" at position 15, even though both are CRITICAL.
    """

    def _old_loop_hits(self, patterns, line):
        import re

        hits = []
        for p in patterns:
            try:
                m = re.search(p.regex_pattern, line, re.IGNORECASE)
            except re.error:
                continue
            if m:
                hits.append((m.start(), severity_rank(p.severity_level), p.id, p))
        return hits

    def _expected(self, patterns, line):
        hits = self._old_loop_hits(patterns, line)
        if not hits:
            return None
        return min(hits)[3]

    def test_winner_is_best_of_old_matches(self, library):
        import random

        rng = random.Random(20261017)
        valid = [p for p in library if p.name != "Broken Pattern"]
        corpus = [
            "disk drive fail on node 3",
            "smartd reports drive fail predicted",
            "network timeout after 30s",
            "cpu high load average 95",
            "auth fail for user root",
            "nfs timeout on export /data",
            "login fail from 10.0.0.5",
            "routine heartbeat ok",
            "",
            "DISK FAIL IN CAPS",
        ]
        m = compile_matcher(library)
        for line in corpus:
            expected = self._expected(valid, line)
            winner = match_line(m, line)
            if expected is None:
                assert winner is None, line
            else:
                assert winner is not None, line
                assert winner.id == expected.id, line
        # Fuzz with synthetic lines.
        words = ["disk", "drive", "fail", "smart", "network", "timeout",
                 "cpu", "high", "auth", "login", "nfs", "ok", "node"]
        for _ in range(500):
            line = " ".join(rng.choice(words) for _ in range(rng.randint(1, 8)))
            expected = self._expected(valid, line)
            winner = match_line(m, line)
            if expected is None:
                assert winner is None, line
            else:
                assert winner.id == expected.id, line
