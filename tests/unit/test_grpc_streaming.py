"""gRPC streaming tests: proto round-trip, enforced auth, live streaming.

No live Redis/Celery needed: the in-memory event bus (EVENT_BUS=memory
semantics via direct bus injection) carries the events, and a file-based
SQLite DB stands in for Postgres. The servicer is driven directly (no
socket), with a fake grpc.ServicerContext.
"""
import os
import threading
import time

import pytest

# Set before any src import that could resolve the bus backend.
os.environ["ADMIN_USERNAME"] = "test-admin"
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    "$2b$12$X.m9BbKu7XC9SABo6YiDqOF4lxzqLFkja5AqjBnmL9RuWIc7Ocf8a.",
)

from src.core.events import (
    InMemoryEventBus,
    emit_incident_created,
    emit_job_cancelled,
    emit_job_completed,
    emit_job_progress,
    job_channel,
)
from src.grpc import jobs_pb2
from src.grpc.server import JobServiceServicer

import src.core.events as events_mod
import src.grpc.server as grpc_server_mod


class FakeAbort(Exception):
    def __init__(self, code, details):
        super().__init__(details)
        self.code = code
        self.details = details


class FakeContext:
    """Minimal grpc.ServicerContext stand-in."""

    def __init__(self, metadata=()):
        self._metadata = tuple(metadata)
        self._active = True

    def invocation_metadata(self):
        return self._metadata

    def is_active(self):
        return self._active

    def abort(self, code, details):
        raise FakeAbort(code, details)


def _valid_token():
    from src.api.routers.auth import create_access_token

    return create_access_token({"sub": "test-admin"})


def _auth_md(token=None):
    token = token if token is not None else _valid_token()
    return (("authorization", f"Bearer {token}"),)


@pytest.fixture()
def bus(monkeypatch):
    """In-memory bus wired into both the emitters and the servicer."""
    b = InMemoryEventBus()
    monkeypatch.setattr(events_mod, "_bus", b)
    return b


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    """SQLite-backed SessionLocal for the servicer (no Docker)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from src.db.database import Base

    engine = create_engine(
        f"sqlite:///{tmp_path}/grpc_test.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    monkeypatch.setattr(grpc_server_mod, "SessionLocal", maker)
    s = maker()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


def _make_job(db_session, job_id, status, cluster_name=None):
    from src.models import Job

    job = Job(id=job_id, filename="t.log", file_size=0, status=status)
    if cluster_name:
        job.cluster_name = cluster_name
    db_session.add(job)
    db_session.commit()
    return job


def _make_incident(db_session, job_id, title="disk failed"):
    from src.models import Incident, Node, Pattern, Severity

    node = Node(hostname=f"n-{time.time_ns()}")
    db_session.add(node)
    db_session.flush()
    pat = Pattern(
        name=f"p-{time.time_ns()}", regex_pattern="disk", severity_level="HIGH"
    )
    db_session.add(pat)
    db_session.flush()
    inc = Incident(
        title=title,
        description="desc",
        severity=Severity.HIGH,
        node_id=node.id,
        pattern_id=pat.id,
        job_id=job_id,
        chunk_index=0,
    )
    db_session.add(inc)
    db_session.commit()
    return inc, pat


# -- proto round-trips ------------------------------------------------------


def test_proto_job_event_roundtrip():
    e = jobs_pb2.JobEvent(
        sequence=7,
        type="job.progress",
        job_id="j1",
        progress=42,
        chunks_completed=3,
        total_chunks=8,
    )
    e2 = jobs_pb2.JobEvent()
    e2.ParseFromString(e.SerializeToString())
    assert (e2.sequence, e2.type, e2.job_id, e2.progress) == (7, "job.progress", "j1", 42)
    assert (e2.chunks_completed, e2.total_chunks) == (3, 8)


def test_proto_incident_roundtrip():
    inc = jobs_pb2.Incident(
        id=9, job_id="j1", pattern_id=3, pattern_name="disk",
        severity="HIGH", title="t", chunk_index=-1,
    )
    inc2 = jobs_pb2.Incident()
    inc2.ParseFromString(inc.SerializeToString())
    assert inc2.id == 9 and inc2.chunk_index == -1 and inc2.pattern_name == "disk"


def test_proto_requests_roundtrip():
    r = jobs_pb2.JobEventsRequest(job_id="j", cluster_name="c", from_sequence=5)
    r2 = jobs_pb2.JobEventsRequest()
    r2.ParseFromString(r.SerializeToString())
    assert (r2.job_id, r2.cluster_name, r2.from_sequence) == ("j", "c", 5)


# -- auth: every RPC rejects before doing anything ---------------------------


def test_stream_job_events_rejects_missing_token(db_session, bus):
    from src.models import JobStatus

    _make_job(db_session, "j-auth-1", JobStatus.PENDING)
    with pytest.raises(FakeAbort) as exc:
        list(
            JobServiceServicer().StreamJobEvents(
                jobs_pb2.JobEventsRequest(job_id="j-auth-1"), FakeContext()
            )
        )
    import grpc

    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED


def test_stream_job_events_rejects_bad_token(db_session, bus):
    from src.models import JobStatus

    _make_job(db_session, "j-auth-2", JobStatus.PENDING)
    ctx = FakeContext(_auth_md("not-a-jwt"))
    with pytest.raises(FakeAbort) as exc:
        list(
            JobServiceServicer().StreamJobEvents(
                jobs_pb2.JobEventsRequest(job_id="j-auth-2"), ctx
            )
        )
    import grpc

    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED


def test_stream_rejects_valid_signature_unknown_user(db_session, bus):
    """Signature alone is not enough -- the user must exist (REST parity)."""
    from src.api.routers.auth import create_access_token
    from src.models import JobStatus

    _make_job(db_session, "j-auth-3", JobStatus.PENDING)
    token = create_access_token({"sub": "no-such-user"})
    ctx = FakeContext(_auth_md(token))
    with pytest.raises(FakeAbort) as exc:
        list(
            JobServiceServicer().StreamJobEvents(
                jobs_pb2.JobEventsRequest(job_id="j-auth-3"), ctx
            )
        )
    import grpc

    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED


def test_stream_incidents_rejects_missing_token(db_session, bus):
    from src.models import JobStatus

    _make_job(db_session, "j-auth-4", JobStatus.PENDING)
    with pytest.raises(FakeAbort) as exc:
        list(
            JobServiceServicer().StreamIncidents(
                jobs_pb2.IncidentStreamRequest(job_id="j-auth-4"), FakeContext()
            )
        )
    import grpc

    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED


# -- validation ---------------------------------------------------------------


def test_cluster_mismatch_rejected(db_session, bus):
    from src.models import JobStatus

    _make_job(db_session, "j-cl", JobStatus.PENDING, cluster_name="alpha")
    ctx = FakeContext(_auth_md())
    with pytest.raises(FakeAbort) as exc:
        list(
            JobServiceServicer().StreamJobEvents(
                jobs_pb2.JobEventsRequest(job_id="j-cl", cluster_name="beta"), ctx
            )
        )
    import grpc

    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


def test_negative_from_sequence_rejected(db_session, bus):
    from src.models import JobStatus

    _make_job(db_session, "j-seq", JobStatus.PENDING)
    ctx = FakeContext(_auth_md())
    with pytest.raises(FakeAbort) as exc:
        list(
            JobServiceServicer().StreamJobEvents(
                jobs_pb2.JobEventsRequest(job_id="j-seq", from_sequence=-1), ctx
            )
        )
    import grpc

    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


def test_unknown_job_not_found(db_session, bus):
    ctx = FakeContext(_auth_md())
    with pytest.raises(FakeAbort) as exc:
        list(
            JobServiceServicer().StreamJobEvents(
                jobs_pb2.JobEventsRequest(job_id="nope"), ctx
            )
        )
    import grpc

    assert exc.value.code == grpc.StatusCode.NOT_FOUND


# -- streaming -----------------------------------------------------------------


def test_terminal_job_fast_path(db_session, bus):
    """Reconnect to a finished job: snapshot + terminal, stream closes."""
    from src.models import JobStatus

    _make_job(db_session, "j-term", JobStatus.COMPLETED)
    ctx = FakeContext(_auth_md())
    out = list(
        JobServiceServicer().StreamJobEvents(
            jobs_pb2.JobEventsRequest(job_id="j-term"), ctx
        )
    )
    assert [e.type for e in out] == ["job.snapshot", "job.completed"]
    assert [e.sequence for e in out] == [1, 2]
    assert out[1].summary.status == "COMPLETED"


def test_live_stream_ends_cleanly_on_cancel(db_session, bus):
    """job.cancelled is a terminal event: the client sees the stream end."""
    from src.models import JobStatus

    _make_job(db_session, "j-live", JobStatus.PENDING)
    inc, pat = _make_incident(db_session, "j-live")

    servicer = JobServiceServicer()
    ctx = FakeContext(_auth_md())
    gen = servicer.StreamJobEvents(jobs_pb2.JobEventsRequest(job_id="j-live"), ctx)
    received = []

    def drive():
        for ev in gen:
            received.append(ev)

    t = threading.Thread(target=drive)
    t.start()
    time.sleep(0.5)  # let the consumer subscribe first
    emit_job_progress(
        job_id="j-live", chunks_completed=1, total_chunks=4, progress=25
    )
    time.sleep(0.2)
    emit_incident_created(
        incident_id=inc.id,
        job_id="j-live",
        chunk_index=0,
        pattern_id=pat.id,
        pattern_name=pat.name,
        severity="HIGH",
    )
    time.sleep(0.2)
    emit_job_cancelled(job_id="j-live")
    t.join(timeout=15)

    assert not t.is_alive(), "stream did not end after job.cancelled"
    types = [e.type for e in received]
    assert types[0] == "job.snapshot"
    assert "job.progress" in types
    assert "incident.created" in types
    assert types[-1] == "job.cancelled"
    seqs = [e.sequence for e in received]
    assert seqs == list(range(1, len(seqs) + 1))  # monotonic from 1, no gaps/dupes

    prog = next(e for e in received if e.type == "job.progress")
    assert prog.progress == 25 and prog.chunks_completed == 1

    incev = next(e for e in received if e.type == "incident.created")
    assert incev.incident.id == inc.id
    assert incev.incident.title == "disk failed"
    assert incev.incident.pattern_name == pat.name

    assert job_channel("j-live")  # channel naming helper still intact


def test_stream_incidents_replay_cursor(db_session, bus):
    """from_incident_id is a genuine DB-backed cursor (terminal job)."""
    from src.models import JobStatus

    _make_job(db_session, "j-inc2", JobStatus.COMPLETED)
    inc1, _ = _make_incident(db_session, "j-inc2", title="first")
    inc2, _ = _make_incident(db_session, "j-inc2", title="second")
    inc3, _ = _make_incident(db_session, "j-inc2", title="third")

    servicer = JobServiceServicer()

    all_inc = list(
        servicer.StreamIncidents(
            jobs_pb2.IncidentStreamRequest(job_id="j-inc2", from_incident_id=0),
            FakeContext(_auth_md()),
        )
    )
    assert [i.id for i in all_inc] == [inc1.id, inc2.id, inc3.id]
    assert [i.title for i in all_inc] == ["first", "second", "third"]

    tail = list(
        servicer.StreamIncidents(
            jobs_pb2.IncidentStreamRequest(
                job_id="j-inc2", from_incident_id=inc2.id
            ),
            FakeContext(_auth_md()),
        )
    )
    assert [i.id for i in tail] == [inc3.id]


def test_stream_incidents_live_then_terminal(db_session, bus):
    from src.models import JobStatus

    _make_job(db_session, "j-inc3", JobStatus.PENDING)
    inc, pat = _make_incident(db_session, "j-inc3", title="live-one")

    servicer = JobServiceServicer()
    ctx = FakeContext(_auth_md())
    gen = servicer.StreamIncidents(
        jobs_pb2.IncidentStreamRequest(job_id="j-inc3", from_incident_id=inc.id),
        ctx,
    )
    received = []

    def drive():
        for ev in gen:
            received.append(ev)

    t = threading.Thread(target=drive)
    t.start()
    time.sleep(0.5)
    inc2, pat2 = _make_incident(db_session, "j-inc3", title="live-two")
    emit_incident_created(
        incident_id=inc2.id,
        job_id="j-inc3",
        chunk_index=0,
        pattern_id=pat2.id,
        pattern_name=pat2.name,
        severity="HIGH",
    )
    time.sleep(0.3)
    emit_job_completed(job_id="j-inc3", summary={})
    t.join(timeout=15)

    assert not t.is_alive(), "incident stream did not end on job.completed"
    assert [i.id for i in received] == [inc2.id]
    assert received[0].title == "live-two"


# -- structural guard: auth is not decorative -----------------------------------


def test_grpc_methods_authenticate_first():
    """AST guard: every public RPC must call _authenticate as its first
    statement. The repo's history is decorative auth; this must not regress."""
    import ast

    with open("src/grpc/server.py") as f:
        tree = ast.parse(f.read())
    checked = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "JobServiceServicer":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith(
                    "Stream"
                ):
                    checked += 1
                    first = item.body[0]
                    assert isinstance(first, ast.Expr), item.name
                    call = first.value
                    assert isinstance(call, ast.Call), item.name
                    func = call.func
                    name = func.id if isinstance(func, ast.Name) else ""
                    assert name == "_authenticate", (
                        f"{item.name} does not call _authenticate first"
                    )
    assert checked == 2, f"expected 2 RPC methods, found {checked}"
