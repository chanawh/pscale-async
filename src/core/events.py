"""Domain event bus: Redis pub/sub with an in-memory fallback.

Workers publish small JSON-safe domain events on per-job channels
(``job:{job_id}``); the SSE endpoint subscribes to the channel instead of
polling the database every second per client.

Backends
--------
* ``redis`` (default): redis-py pub/sub against ``REDIS_URL`` — the same
  Redis the Celery broker uses. Works across processes and containers,
  which is what production (separate API/worker containers) needs.
* ``memory``: process-local fan-out for tests and single-process dev.
  Does NOT cross process boundaries.

Publishing is best-effort: the database remains the source of truth.
Workers must use :func:`publish_event` (or the ``emit_*`` helpers), which
never raise, rather than touching a bus directly.

This module is stdlib-only at import time: ``redis`` is imported lazily
inside :class:`RedisEventBus`, and settings are resolved lazily (with an
environment fallback) so unit tests can import this module without
pydantic or any app dependencies installed.
"""

import json
import logging
import os
import queue
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def job_channel(job_id: str, cluster_name: Optional[str] = None) -> str:
    """Channel carrying all domain events for one job.

    Cluster-scoped as ``job:{cluster}:{job_id}`` so subscribers to one
    cluster never see another's events. The bare ``job:{job_id}`` form is
    kept for jobs with no cluster (uploads, streams, pre-multi-cluster
    jobs) -- backwards compatible.
    """
    if cluster_name:
        return f"job:{cluster_name}:{job_id}"
    return f"job:{job_id}"


class Subscription(ABC):
    """A live subscription to one or more channels."""

    @abstractmethod
    def get(self, timeout: float) -> Optional[Tuple[str, dict]]:
        """Return ``(channel, event)`` or ``None`` on timeout."""

    @abstractmethod
    def close(self) -> None:
        """Release the subscription. Idempotent; never raises."""


class EventBus(ABC):
    """Publish/subscribe transport for JSON-safe domain events."""

    @abstractmethod
    def publish(self, channel: str, event: dict) -> None:
        """Publish one event. ``event`` must be JSON-serializable."""

    @abstractmethod
    def subscribe(self, channels: List[str]) -> Subscription:
        """Subscribe to channels; the caller owns the Subscription."""


class InMemoryEventBus(EventBus):
    """Process-local fan-out. Tests and single-process dev only.

    Does not cross process boundaries: with the API and Celery workers in
    separate containers, events published by a worker are invisible to the
    API. Use the ``redis`` backend there.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: Dict[str, List["queue.Queue[Tuple[str, dict]]"]] = {}

    def publish(self, channel: str, event: dict) -> None:
        # Serialize once to validate JSON-safety up front; each subscriber
        # gets an independent copy so consumers can't mutate each other's
        # events through a shared dict.
        wire = json.dumps(event)
        with self._lock:
            targets = list(self._subs.get(channel, ()))
        for q in targets:
            q.put((channel, json.loads(wire)))

    def subscribe(self, channels: List[str]) -> Subscription:
        q: "queue.Queue[Tuple[str, dict]]" = queue.Queue()
        with self._lock:
            for ch in channels:
                self._subs.setdefault(ch, []).append(q)
        return _InMemorySubscription(self, list(channels), q)


class _InMemorySubscription(Subscription):
    def __init__(
        self,
        bus: InMemoryEventBus,
        channels: List[str],
        q: "queue.Queue[Tuple[str, dict]]",
    ) -> None:
        self._bus = bus
        self._channels = channels
        self._q = q
        self._closed = False

    def get(self, timeout: float) -> Optional[Tuple[str, dict]]:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._bus._lock:
            for ch in self._channels:
                subs = self._bus._subs.get(ch, [])
                try:
                    subs.remove(self._q)
                except ValueError:
                    pass


class RedisEventBus(EventBus):
    """Redis pub/sub transport. ``redis`` is imported lazily so the app
    and unit tests don't hard-require it."""

    def __init__(self, redis_url: str) -> None:
        try:
            import redis
        except ImportError as e:
            raise RuntimeError(
                "EVENT_BUS=redis requires the 'redis' package"
            ) from e
        self._client = redis.Redis.from_url(redis_url, socket_timeout=5)

    def publish(self, channel: str, event: dict) -> None:
        self._client.publish(channel, json.dumps(event))

    def subscribe(self, channels: List[str]) -> Subscription:
        pubsub = self._client.pubsub()
        pubsub.subscribe(channels)
        return _RedisSubscription(pubsub)


class _RedisSubscription(Subscription):
    def __init__(self, pubsub) -> None:
        self._pubsub = pubsub
        self._closed = False

    def get(self, timeout: float) -> Optional[Tuple[str, dict]]:
        msg = self._pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
        if not msg or msg.get("type") != "message":
            return None
        channel = msg.get("channel")
        if isinstance(channel, bytes):
            channel = channel.decode("utf-8", "ignore")
        data = msg.get("data")
        if isinstance(data, bytes):
            data = data.decode("utf-8", "ignore")
        try:
            return channel, json.loads(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("dropping undecodable event on %s: %s", channel, e)
            return None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._pubsub.unsubscribe()
            self._pubsub.close()
        except Exception:
            pass


_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def _resolve_backend() -> Tuple[str, str]:
    """Return ``(backend, redis_url)``.

    Prefers the app settings when importable; falls back to the
    environment so this module stays importable (and testable) without
    pydantic installed.
    """
    try:
        from src.core.config import settings

        return settings.event_bus, settings.redis_url
    except Exception:
        return (
            os.environ.get("EVENT_BUS", "redis"),
            os.environ.get("REDIS_URL", DEFAULT_REDIS_URL),
        )


def get_event_bus() -> EventBus:
    """Process-wide bus singleton, built from settings on first use."""
    global _bus
    with _bus_lock:
        if _bus is None:
            backend, redis_url = _resolve_backend()
            backend = (backend or "redis").lower()
            if backend == "memory":
                _bus = InMemoryEventBus()
            elif backend == "redis":
                _bus = RedisEventBus(redis_url)
            else:
                raise ValueError(
                    f"unknown EVENT_BUS backend {backend!r} "
                    "(expected 'redis' or 'memory')"
                )
        return _bus


def reset_event_bus() -> None:
    """Drop the cached bus. Tests use this to switch backends mid-run."""
    global _bus
    with _bus_lock:
        _bus = None


def publish_event(channel: str, event: dict) -> bool:
    """Best-effort publish. Never raises — the database is the source of
    truth, and a down event bus must not break log processing."""
    try:
        get_event_bus().publish(channel, event)
        return True
    except Exception as e:
        logger.warning("event publish failed on %s: %s", channel, e)
        return False


# ---------------------------------------------------------------------------
# Domain event emitters. Payloads are small, flat, and JSON-safe by
# construction. Callers pass plain values (no ORM objects) so these stay
# trivially testable.
# ---------------------------------------------------------------------------


def emit_incident_created(
    *,
    incident_id: int,
    job_id: str,
    chunk_index: Optional[int],
    pattern_id: int,
    pattern_name: str,
    severity: str,
    cluster_name: Optional[str] = None,
) -> bool:
    """An incident row was committed. ``chunk_index`` is None for the
    legacy monolithic path."""
    return publish_event(
        job_channel(job_id, cluster_name),
        {
            "type": "incident.created",
            "incident_id": incident_id,
            "job_id": job_id,
            "chunk_index": chunk_index,
            "pattern_id": pattern_id,
            "pattern_name": pattern_name,
            "severity": severity,
        },
    )


def emit_job_progress(
    *,
    job_id: str,
    chunks_completed: int,
    total_chunks: int,
    progress: int,
    cluster_name: Optional[str] = None,
) -> bool:
    """A chunk finished (or the legacy path hit a progress checkpoint).
    ``chunks_completed``/``total_chunks`` are 0 for the legacy path, which
    reports ``progress`` directly."""
    return publish_event(
        job_channel(job_id, cluster_name),
        {
            "type": "job.progress",
            "job_id": job_id,
            "chunks_completed": chunks_completed,
            "total_chunks": total_chunks,
            "progress": progress,
        },
    )


def emit_job_completed(
    *, job_id: str, summary: dict, cluster_name: Optional[str] = None
) -> bool:
    return publish_event(
        job_channel(job_id, cluster_name),
        {"type": "job.completed", "job_id": job_id, "summary": summary},
    )


def emit_job_failed(
    *,
    job_id: str,
    error: str,
    summary: Optional[dict] = None,
    cluster_name: Optional[str] = None,
) -> bool:
    return publish_event(
        job_channel(job_id, cluster_name),
        {
            "type": "job.failed",
            "job_id": job_id,
            "error": error,
            "summary": summary,
        },
    )
