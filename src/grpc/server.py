"""gRPC streaming server: typed alternative to SSE over the same event bus.

Consumes the domain event bus (``src/core/events.py``) -- the exact channel
SSE subscribes to -- and re-emits events as protobuf. No second event
system: if SSE sees it, this sees it.

Auth
----
Every RPC requires the same JWT bearer token the REST API uses, passed as
``authorization: Bearer <token>`` gRPC metadata. Validation reuses the
identical logic as ``get_current_user`` (``jwt.decode`` with
``settings.secret_key``/HS256 + the user must exist); it is done BEFORE any
DB or bus work, and failures abort with UNAUTHENTICATED. The ``get_user``
import is lazy so this module stays importable without the ADMIN_*
bootstrap env (unit tests).

Lifecycle
---------
Created by :func:`create_server` and driven by the FastAPI app's
startup/shutdown handlers (see ``src/app/main.py``). Runs on its own port
(``GRPC_PORT``, default 50051) in gRPC's thread pool -- never on the
FastAPI event loop.
"""

import logging
from concurrent import futures
from typing import Iterator, Optional

import grpc
import jwt

from src.core.config import settings
from src.core.events import get_event_bus, job_channel
from src.db.database import SessionLocal
from src.grpc import jobs_pb2, jobs_pb2_grpc
from src.models import Incident, Job, JobStatus

logger = logging.getLogger(__name__)

TERMINAL_TYPES = ("job.completed", "job.failed", "job.cancelled")
TERMINAL_STATUSES = (
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
)


def _bearer_token(context: grpc.ServicerContext) -> Optional[str]:
    """Extract the raw JWT from `authorization: Bearer <token>` metadata."""
    for key, value in context.invocation_metadata():
        if key.lower() == "authorization":
            scheme, _, token = value.partition(" ")
            if scheme.lower() == "bearer" and token:
                return token
            return None
    return None


def _authenticate(context: grpc.ServicerContext) -> dict:
    """Enforce the REST API's JWT auth on a gRPC call.

    Same verification as ``get_current_user``: HS256 decode with the app
    secret, ``sub`` claim present, and the user must exist. Aborts
    UNAUTHENTICATED on anything else -- including a missing header, so
    there is no unauthenticated path to a stream.
    """
    # Lazy: importing src.api.routers.auth at module import would run its
    # fail-fast ADMIN_* bootstrap check; the server only needs get_user.
    from src.api.routers.auth import get_user

    token = _bearer_token(context)
    user = None
    if token:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
            username = payload.get("sub")
            if username:
                user = get_user(username=username)
        except jwt.PyJWTError:
            user = None
    if user is None:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid or missing bearer token")
    return user


def _check_cluster(request_cluster: str, job: Job, context: grpc.ServicerContext) -> None:
    """The server picks the channel from the job row, never the client.

    A client-supplied cluster_name that disagrees with the job's own is
    rejected -- it would otherwise be a cross-cluster subscription
    attempt against a channel the caller may not be watching.
    """
    if request_cluster and request_cluster != (job.cluster_name or ""):
        context.abort(
            grpc.StatusCode.INVALID_ARGUMENT,
            f"cluster_name {request_cluster!r} does not match job's cluster "
            f"{job.cluster_name!r}",
        )


def _load_job(job_id: str, context: grpc.ServicerContext) -> Job:
    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if job is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"job {job_id!r} not found")
        # Detach the loaded attributes before the session closes; the
        # stream below only touches these scalars.
        session.expunge(job)
        return job
    finally:
        session.close()


def _job_summary(job: Job) -> jobs_pb2.JobSummary:
    # Fresh read for terminal state -- mirrors the SSE _full_snapshot.
    session = SessionLocal()
    try:
        j = session.query(Job).filter(Job.id == job.id).first()
        if j is None:
            return jobs_pb2.JobSummary(status="UNKNOWN")
        return jobs_pb2.JobSummary(
            status=j.status.value,
            progress=j.progress or 0,
            result_summary=j.result_summary or "",
            error_message=j.error_message or "",
        )
    finally:
        session.close()


def _incident_to_proto(
    incident_id: int, event: Optional[dict], job_id: str
) -> jobs_pb2.Incident:
    """Build the proto from the committed row; fall back to the bus event.

    incident.created is published commit-then-publish, so the row should
    exist. The event fallback keeps the stream lossless if it doesn't.
    """
    session = SessionLocal()
    try:
        row = session.query(Incident).filter(Incident.id == incident_id).first()
        if row is not None:
            return jobs_pb2.Incident(
                id=row.id,
                job_id=row.job_id,
                pattern_id=row.pattern_id or 0,
                pattern_name=(event or {}).get("pattern_name", ""),
                severity=row.severity.value if row.severity else "",
                title=row.title or "",
                description=row.description or "",
                chunk_index=(
                    row.chunk_index if row.chunk_index is not None else -1
                ),
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
    finally:
        session.close()
    e = event or {}
    return jobs_pb2.Incident(
        id=incident_id,
        job_id=job_id,
        pattern_id=e.get("pattern_id", 0),
        pattern_name=e.get("pattern_name", ""),
        severity=e.get("severity", ""),
        chunk_index=e.get("chunk_index", -1) if e.get("chunk_index") is not None else -1,
    )


class JobServiceServicer(jobs_pb2_grpc.JobServiceServicer):
    """Streams domain events for one job.

    Sequence numbers are per-stream, starting at 1. The bus has no replay
    log, so resume is snapshot + live; a reconnect to an already-terminal
    job gets snapshot + terminal immediately and the stream closes.
    """

    # -- StreamJobEvents ------------------------------------------------

    def StreamJobEvents(
        self, request: jobs_pb2.JobEventsRequest, context: grpc.ServicerContext
    ) -> Iterator[jobs_pb2.JobEvent]:
        _authenticate(context)
        if request.from_sequence < 0:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "from_sequence must be >= 0"
            )
        job = _load_job(request.job_id, context)
        _check_cluster(request.cluster_name, job, context)

        seq = 0

        def _next(**fields) -> jobs_pb2.JobEvent:
            nonlocal seq
            seq += 1
            return jobs_pb2.JobEvent(sequence=seq, job_id=job.id, **fields)

        # Snapshot first, always -- same contract as the SSE endpoint.
        yield _next(
            type="job.snapshot",
            summary=jobs_pb2.JobSummary(
                status=job.status.value, progress=job.progress or 0
            ),
        )

        if job.status in TERMINAL_STATUSES:
            # Terminal fast-path: the reconnecting client learns the final
            # state at once instead of hanging on a dead channel.
            yield _next(
                type=f"job.{job.status.value.lower()}",
                summary=_job_summary(job),
                error=job.error_message or "",
            )
            return

        channel = job_channel(job.id, job.cluster_name)
        try:
            sub = get_event_bus().subscribe([channel])
        except Exception as exc:  # bus unavailable: fail the RPC, don't hang
            context.abort(
                grpc.StatusCode.UNAVAILABLE, f"event bus unavailable: {exc}"
            )
            return

        try:
            while context.is_active():
                msg = sub.get(20.0)
                if msg is None:
                    continue  # heartbeat window; HTTP/2 pings keep it alive
                _channel, event = msg
                etype = event.get("type")
                if etype == "job.progress":
                    yield _next(
                        type=etype,
                        progress=event.get("progress", 0),
                        chunks_completed=event.get("chunks_completed", 0),
                        total_chunks=event.get("total_chunks", 0),
                    )
                elif etype == "incident.created":
                    yield _next(
                        type=etype,
                        incident=_incident_to_proto(
                            event.get("incident_id", 0), event, job.id
                        ),
                    )
                elif etype in TERMINAL_TYPES:
                    # Terminal event ends the stream cleanly -- including
                    # job.cancelled, so a cancelled job never leaves a
                    # client hanging.
                    yield _next(
                        type=etype,
                        summary=_job_summary(job),
                        error=event.get("error", ""),
                    )
                    return
                # Unknown types are ignored (forward-compatible), like SSE.
        finally:
            sub.close()

    # -- StreamIncidents --------------------------------------------------

    def StreamIncidents(
        self, request: jobs_pb2.IncidentStreamRequest, context: grpc.ServicerContext
    ) -> Iterator[jobs_pb2.Incident]:
        _authenticate(context)
        if request.from_incident_id < 0:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "from_incident_id must be >= 0"
            )
        job = _load_job(request.job_id, context)
        _check_cluster(request.cluster_name, job, context)

        # Genuine replay: incidents are persisted, so from_incident_id is a
        # real cursor, not a hint.
        session = SessionLocal()
        try:
            rows = (
                session.query(Incident)
                .filter(
                    Incident.job_id == job.id,
                    Incident.id > request.from_incident_id,
                )
                .order_by(Incident.id)
                .all()
            )
            replay = [
                _incident_to_proto(
                    r.id,
                    {"pattern_name": "", "severity": r.severity.value if r.severity else ""},
                    job.id,
                )
                for r in rows
            ]
            last_replayed = rows[-1].id if rows else request.from_incident_id
        finally:
            session.close()
        for inc in replay:
            if not context.is_active():
                return
            yield inc

        if job.status in TERMINAL_STATUSES:
            return  # nothing more will ever be created

        channel = job_channel(job.id, job.cluster_name)
        try:
            sub = get_event_bus().subscribe([channel])
        except Exception as exc:
            context.abort(
                grpc.StatusCode.UNAVAILABLE, f"event bus unavailable: {exc}"
            )
            return

        try:
            while context.is_active():
                msg = sub.get(20.0)
                if msg is None:
                    continue
                _channel, event = msg
                if event.get("type") == "incident.created":
                    incident_id = event.get("incident_id", 0)
                    if incident_id > last_replayed:
                        last_replayed = incident_id
                        yield _incident_to_proto(incident_id, event, job.id)
                elif event.get("type") in TERMINAL_TYPES:
                    return  # terminal: no more incidents will be created
        finally:
            sub.close()


def create_server(port: int, max_workers: int = 10) -> grpc.Server:
    """Build (but do not start) the gRPC server. The caller owns start/stop."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    jobs_pb2_grpc.add_JobServiceServicer_to_server(JobServiceServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    return server
