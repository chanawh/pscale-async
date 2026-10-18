"""Unit tests for the domain event bus (``src.core.events``).

``src.core.events`` is stdlib-only at import on purpose, so these tests run
without Redis, Celery, SQLAlchemy, or pydantic installed.
"""

import json
import os
import threading

import pytest

os.environ.setdefault("EVENT_BUS", "memory")

import src.core.events as events
from src.core.events import (
    InMemoryEventBus,
    emit_incident_created,
    emit_job_completed,
    emit_job_failed,
    emit_job_progress,
    get_event_bus,
    job_channel,
    publish_event,
    reset_event_bus,
)


@pytest.fixture(autouse=True)
def _fresh_bus():
    """Every test starts with a clean bus singleton."""
    reset_event_bus()
    yield
    reset_event_bus()


class _RecordingBus(events.EventBus):
    """Captures published (channel, event) pairs for assertions."""

    def __init__(self):
        self.published = []

    def publish(self, channel, event):
        self.published.append((channel, event))

    def subscribe(self, channels):
        raise AssertionError("not needed in this test")


class _BrokenBus(events.EventBus):
    def publish(self, channel, event):
        raise RuntimeError("bus is down")

    def subscribe(self, channels):
        raise RuntimeError("bus is down")


def _install(bus):
    with events._bus_lock:
        events._bus = bus


def test_job_channel_naming():
    assert job_channel("abc-123") == "job:abc-123"


def test_inmemory_round_trip():
    bus = InMemoryEventBus()
    sub = bus.subscribe([job_channel("j1")])
    try:
        bus.publish(job_channel("j1"), {"type": "job.progress", "progress": 42})
        channel, event = sub.get(timeout=2.0)
        assert channel == job_channel("j1")
        assert event == {"type": "job.progress", "progress": 42}
    finally:
        sub.close()


def test_channel_isolation():
    """A subscriber on job A must not receive job B's events."""
    bus = InMemoryEventBus()
    sub_a = bus.subscribe([job_channel("a")])
    try:
        bus.publish(job_channel("b"), {"type": "job.progress"})
        assert sub_a.get(timeout=0.3) is None
        bus.publish(job_channel("a"), {"type": "job.progress"})
        channel, _ = sub_a.get(timeout=2.0)
        assert channel == job_channel("a")
    finally:
        sub_a.close()


def test_multiple_subscribers_each_get_copy():
    bus = InMemoryEventBus()
    sub1 = bus.subscribe([job_channel("j")])
    sub2 = bus.subscribe([job_channel("j")])
    try:
        bus.publish(job_channel("j"), {"type": "t", "n": 1})
        _, e1 = sub1.get(timeout=2.0)
        _, e2 = sub2.get(timeout=2.0)
        assert e1 == e2 == {"type": "t", "n": 1}
        # Independent copies: mutating one must not affect the other.
        e1["n"] = 999
        assert e2["n"] == 1
    finally:
        sub1.close()
        sub2.close()


def test_close_stops_delivery_and_is_idempotent():
    bus = InMemoryEventBus()
    sub = bus.subscribe([job_channel("j")])
    sub.close()
    sub.close()  # idempotent, never raises
    bus.publish(job_channel("j"), {"type": "t"})
    assert sub.get(timeout=0.3) is None


def test_publish_rejects_non_json_safe_payload():
    bus = InMemoryEventBus()
    with pytest.raises(TypeError):
        bus.publish(job_channel("j"), {"type": "t", "bad": object()})


def test_publish_event_never_raises_when_bus_is_down():
    """The DB is the source of truth; a dead bus must not break workers."""
    _install(_BrokenBus())
    assert publish_event(job_channel("j"), {"type": "t"}) is False


def test_emit_incident_created_payload():
    rec = _RecordingBus()
    _install(rec)
    assert (
        emit_incident_created(
            incident_id=7,
            job_id="job-1",
            chunk_index=2,
            pattern_id=11,
            pattern_name="Disk Failure",
            severity="CRITICAL",
        )
        is True
    )
    assert rec.published == [
        (
            job_channel("job-1"),
            {
                "type": "incident.created",
                "incident_id": 7,
                "job_id": "job-1",
                "chunk_index": 2,
                "pattern_id": 11,
                "pattern_name": "Disk Failure",
                "severity": "CRITICAL",
            },
        )
    ]


def test_emit_incident_created_legacy_path_chunk_index_none():
    rec = _RecordingBus()
    _install(rec)
    emit_incident_created(
        incident_id=1,
        job_id="job-1",
        chunk_index=None,
        pattern_id=3,
        pattern_name="P",
        severity="LOW",
    )
    _, event = rec.published[0]
    assert event["chunk_index"] is None
    # Payload must survive a JSON round-trip (what Redis actually sends).
    json.dumps(event)


def test_emit_job_progress_payload():
    rec = _RecordingBus()
    _install(rec)
    emit_job_progress(
        job_id="job-9", chunks_completed=3, total_chunks=10, progress=30
    )
    assert rec.published == [
        (
            job_channel("job-9"),
            {
                "type": "job.progress",
                "job_id": "job-9",
                "chunks_completed": 3,
                "total_chunks": 10,
                "progress": 30,
            },
        )
    ]


def test_emit_job_completed_and_failed_payloads():
    rec = _RecordingBus()
    _install(rec)
    emit_job_completed(job_id="job-1", summary={"incidents_created": 5})
    emit_job_failed(job_id="job-2", error="boom", summary=None)
    types = [e["type"] for _, e in rec.published]
    assert types == ["job.completed", "job.failed"]
    assert rec.published[0][1]["summary"] == {"incidents_created": 5}
    assert rec.published[1][1]["error"] == "boom"
    assert rec.published[1][1]["summary"] is None


def test_emit_helpers_survive_bus_outage():
    _install(_BrokenBus())
    assert (
        emit_incident_created(
            incident_id=1,
            job_id="j",
            chunk_index=0,
            pattern_id=1,
            pattern_name="p",
            severity="LOW",
        )
        is False
    )
    assert emit_job_progress(job_id="j", chunks_completed=0, total_chunks=0, progress=0) is False
    assert emit_job_completed(job_id="j", summary={}) is False
    assert emit_job_failed(job_id="j", error="x") is False


def test_get_event_bus_singleton_and_reset():
    reset_event_bus()
    first = get_event_bus()
    assert get_event_bus() is first
    reset_event_bus()
    assert get_event_bus() is not first


def test_concurrent_publishers_dont_lose_events():
    """Smoke test for the in-memory bus under threads."""
    bus = InMemoryEventBus()
    sub = bus.subscribe([job_channel("j")])
    try:
        def worker(n):
            for i in range(50):
                bus.publish(job_channel("j"), {"type": "t", "n": n * 50 + i})

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        seen = set()
        for _ in range(200):
            msg = sub.get(timeout=2.0)
            assert msg is not None
            seen.add(msg[1]["n"])
        assert seen == set(range(200))
    finally:
        sub.close()
