"""Chunked fan-out/fan-in log processing pipeline.

The original monolithic ``process_log_file`` god-task is decomposed for
object-storage uploads while keeping its exact behavior for the legacy
``file_path`` / ``log_lines`` inputs (kept verbatim at the bottom of this
module behind the backwards-compatible entrypoint).

Topology
--------
``process_log_file`` (backwards-compatible entrypoint)
  └─ ``storage_ref`` given → ``fanout_process_log``
       ├─ streams the object once to count lines (O(1) memory)
       ├─ resolves/creates the Node row a single time
       └─ ``chord(group(process_chunk × N), finalize_job)``

Design notes (the trade-offs, stated plainly):

* Chunks are addressed by *line ranges* ``[start, end)`` computed up
  front. Each chunk re-streams the object and skips to its slice, so a
  job costs N+1 object reads for N chunks. This is deliberately
  stateless — no shared offset index to build, store, or keep consistent
  across workers — and acceptable because chunks are large
  (``CHUNK_LINES``, default 10k), so N stays small. Byte-offset chunking
  would halve the reads but needs a distributed offset ledger; not worth
  it here.

* Retry safety is delete-then-recreate keyed on ``(job_id, chunk_index)``:
  a chunk wipes its own previous output before reprocessing, so a
  redelivery after a successful commit (at-least-once: commit landed,
  ack lost) cannot duplicate incidents. Mid-task crashes need no
  cleanup — the single commit at the end of the chunk rolls back with
  the transaction, leaving nothing behind. Incidents from the legacy
  monolithic path have ``chunk_index IS NULL`` and never match the
  delete predicate.

* Idempotency is a second, complementary layer: a content fingerprint
  (``sha256(pattern_id, node_id, line)``, see
  ``src/workers/fingerprint.py``) with a UNIQUE constraint. The delete
  runs FIRST because it also covers the changed-output case — if the
  pattern library was edited between attempts, the same line may now
  match a different pattern (different fingerprint), and only the delete
  wipes the stale output. The fingerprint then handles what the delete
  cannot: cross-job idempotency (re-ingesting the same file as a new
  job inserts zero new incidents). Two layers, each covering what the
  other cannot.

* Partial failure: a chunk that exhausts its retries returns a failure
  *result dict* instead of raising, so the chord always fires and
  ``finalize_job`` can report honestly. (If a header task raised, the
  chord callback would never run and the job would sit in PROCESSING
  forever.) Any failed chunk marks the job FAILED with a per-chunk
  error summary — ``JobStatus`` has no PARTIAL state, and adding one
  would churn the API and frontend for little value. Incidents written
  by succeeded chunks remain in the database either way.

* Progress: each chunk atomically increments ``jobs.chunks_completed``
  (``UPDATE ... SET chunks_completed = chunks_completed + 1``, safe
  under concurrent workers) and ``job.progress`` tracks
  completed/total chunks. Chunk tasks also report their own Celery
  PROGRESS state, replacing the old per-100-lines updates.

* Patterns are read per chunk from the database, not snapshotted by the
  fan-out: the pattern library is CRUD-edited at runtime, and passing
  pattern snapshots through the broker would bloat task messages and
  freeze the set a job sees.
"""

import io
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import chord, current_task, group
from sqlalchemy import create_engine, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.celery import celery_app
from src.core.config import settings
from src.core.events import (
    emit_incident_created,
    emit_job_completed,
    emit_job_failed,
    emit_job_progress,
)
from src.core.storage import (
    StorageReference,
    backend_from_settings,
    stream_to_text_lines,
)
from src.db.database import Base, SessionLocal
from src.models import Incident, Job, JobStatus, Node, Pattern, Severity, Status
from src.workers.chunking import compute_chunk_ranges, count_stream_lines
from src.workers.fingerprint import compute_fingerprint
from src.workers.matcher import compile_matcher, match_line

# Setup logging
logger = logging.getLogger(__name__)


def _get_job_or_raise(db, job_id):
    """Return ``(job, db)`` for the job row.

    Tolerates the eager-mode commit-visibility race the original god-task
    handled inline: on the retry path the passed session is closed and
    replaced, so callers must use the returned session afterwards.
    """
    retry_count = 0
    while retry_count < 3:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            return job, db
        retry_count += 1
        import time

        time.sleep(0.1)  # Short delay to allow transaction to propagate
        db.close()
        db = SessionLocal()
    raise Exception(f"Job {job_id} not found after 3 retries")


def _get_or_create_node(db, node_hostname, description):
    """Resolve the node exactly once per job and return its id (or None).

    ``Node.hostname`` is unique: letting N chunk workers get-or-create
    concurrently would race on the constraint, so the fan-out does it once
    and hands every chunk the id. Mirrors the god-task's fallback logic.
    """
    if not node_hostname:
        return None
    node = db.query(Node).filter(Node.hostname == node_hostname).first()
    if node:
        return node.id
    node = Node(
        hostname=node_hostname,
        node_type="unknown",
        description=f"Auto-created from log processing: {description or 'No description'}",
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node.id


@celery_app.task(bind=True)
def fanout_process_log(self, job_id, storage_ref, node_hostname=None, description=None):
    """Fan-out entrypoint for object-storage uploads.

    Counts the object's lines in one streaming pass, computes chunk
    ranges, then dispatches ``chord(group(process_chunk × N),
    finalize_job)``. Owns the job's transition to PROCESSING; the chord's
    finalizer owns the terminal state.
    """
    db = SessionLocal()
    try:
        job, db = _get_job_or_raise(db, job_id)
        ref = StorageReference.from_dict(storage_ref)
        backend = backend_from_settings(settings)

        # One streaming pass to count lines — O(1) memory. Chunk tasks
        # re-stream to reach their own slices (see module docstring).
        with backend.open_stream(ref) as stream:
            total_lines = count_stream_lines(stream)

        chunk_lines = settings.chunk_lines
        ranges = compute_chunk_ranges(total_lines, chunk_lines)

        # Single node resolution (see _get_or_create_node).
        node_id = _get_or_create_node(db, node_hostname, description)

        if not ranges:
            # Empty file: complete directly. A zero-task chord has
            # backend-dependent semantics, so never dispatch one.
            summary = {
                "total_lines": 0,
                "processed_lines": 0,
                "incidents_created": 0,
                "patterns_matched": [],
                "total_chunks": 0,
                "failed_chunks": [],
            }
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress = 100
            job.total_chunks = 0
            job.chunks_completed = 0
            job.result_summary = json.dumps(summary)
            db.commit()
            # Terminal event so SSE subscribers see completion even though
            # no chord finalizer runs for this path.
            emit_job_completed(job_id=job_id, summary=summary)
            logger.info(f"Job {job_id}: empty upload, completed with 0 chunks")
            return {
                "status": "completed",
                "job_id": job_id,
                "total_chunks": 0,
                "total_lines": 0,
            }

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.total_chunks = len(ranges)
        job.chunks_completed = 0
        db.commit()

        header = group(
            process_chunk.s(
                job_id=job_id,
                chunk_index=i,
                storage_ref=ref.to_dict(),
                start_line=start,
                end_line=end,
                node_id=node_id,
            )
            for i, (start, end) in enumerate(ranges)
        )
        # The chord body is invoked as finalize_job(group_results, job_id).
        chord(header, finalize_job.s(job_id=job_id)).apply_async()

        logger.info(
            f"Job {job_id}: fanned out into {len(ranges)} chunks "
            f"({total_lines} lines, {chunk_lines} lines/chunk)"
        )
        return {
            "status": "fanned_out",
            "job_id": job_id,
            "total_chunks": len(ranges),
            "total_lines": total_lines,
        }
    except Exception as e:
        logger.error(f"Job {job_id} fan-out failed: {str(e)}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = f"fan-out failed: {str(e)}"
                job.completed_at = datetime.utcnow()
                db.commit()
                emit_job_failed(
                    job_id=job_id, error=job.error_message, summary=None
                )
        except Exception as db_error:
            logger.error(f"Could not mark job {job_id} failed: {db_error}")
        # Re-raise: in eager/dev mode the API's fallback then processes the
        # upload synchronously via the legacy path instead of failing open.
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def ingest_cluster_log(self, job_id, log_path, node_hostname=None, description=None):
    """Fetch a log file from the OneFS cluster over SSH and queue it.

    Request handlers never do this work: the API validates ``log_path``,
    creates the job row, and enqueues this task with a 202 response. The
    worker fetches the file, streams it into the storage backend, records
    the content reference on the job, and delegates to
    ``fanout_process_log`` -- the same chunked pipeline uploads go through.
    """
    from src.core.storage import build_object_key
    from src.onefs.client import OneFSClient, validate_log_path

    db = SessionLocal()
    try:
        job, db = _get_job_or_raise(db, job_id)

        # Defense in depth: the endpoint validated this, but task args can
        # originate anywhere. Never let an unvalidated path reach SSH.
        try:
            safe_path = validate_log_path(log_path, settings.onefs_log_dir)
        except ValueError as e:
            raise Exception(f"Invalid log_path rejected: {e}")

        job.status = JobStatus.PROCESSING
        db.commit()

        client = OneFSClient()
        try:
            log_content = client.get_log_file(safe_path)
        except Exception as e:
            raise Exception(f"SSH fetch of {safe_path} failed: {e}")

        if not log_content or not log_content.strip():
            raise Exception(f"No log content returned from {safe_path}")

        # Into the storage backend -- never a local path across the
        # process boundary (see 673f96e).
        backend = backend_from_settings(settings)
        object_key = build_object_key(
            job_id, f"cluster_{safe_path.strip('/').replace('/', '_')}.log"
        )
        payload = log_content.encode("utf-8", errors="ignore")
        ref = backend.put_stream(object_key, io.BytesIO(payload))

        job.storage_backend = ref.backend
        job.storage_bucket = ref.bucket
        job.storage_key = ref.key
        job.file_size = len(payload)
        db.commit()

        logger.info(f"Cluster job {job_id}: fetched {safe_path} -> {ref}")

        # Hand off to the standard pipeline; the chord finalizer owns the
        # terminal job state from here.
        fanout_process_log.delay(
            job_id=job_id,
            storage_ref=ref.to_dict(),
            node_hostname=node_hostname or "onefs-cluster",
            description=description or f"OneFS cluster log: {safe_path}",
        )
        return {"status": "queued", "job_id": job_id, "storage_ref": ref.to_dict()}
    except Exception as e:
        logger.error(f"Cluster ingest job {job_id} failed before fan-out: {e}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
                emit_job_failed(job_id=job_id, error=job.error_message, summary=None)
        except Exception as db_error:
            logger.error(f"Could not mark job {job_id} failed: {db_error}")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def process_chunk(
    self, job_id, chunk_index, storage_ref, start_line, end_line, node_id=None
):
    """Process one line slice ``[start_line, end_line)`` of the stored object.

    Owns its DB session, streams only its slice (O(1) memory), and runs the
    per-line pattern-matching loop unchanged from the monolithic task.
    Returns a result dict for the chord finalizer — including a failure
    result when retries are exhausted, so the chord always fires.
    """
    db = SessionLocal()
    try:
        # --- Retry safety, layer 1: delete-then-recreate on
        # (job_id, chunk_index). Guards the at-least-once window (commit
        # landed, ack lost → redelivery) AND the changed-output case (see
        # module docstring). Runs BEFORE the fingerprint filter below so a
        # retry's own stale rows can never self-dedup.
        db.query(Incident).filter(
            Incident.job_id == job_id,
            Incident.chunk_index == chunk_index,
        ).delete(synchronize_session=False)

        ref = StorageReference.from_dict(storage_ref)
        backend = backend_from_settings(settings)

        patterns = db.query(Pattern).filter(Pattern.is_active == True).all()
        logger.info(
            f"Job {job_id} chunk {chunk_index}: {len(patterns)} active patterns, "
            f"lines [{start_line}, {end_line})"
        )

        # Single-pass engine, compiled from the fresh pattern read above:
        # patterns are CRUD-edited at runtime, so never cache across chunks.
        matcher = compile_matcher(patterns)
        if matcher.skipped:
            logger.warning(
                f"Job {job_id} chunk {chunk_index}: skipped invalid patterns: "
                f"{matcher.skipped}"
            )

        lines_in_slice = 0
        # Candidate incident column-mappings in match order, plus the
        # pattern name each came from (for events/summary). Fingerprints
        # are computed here; the dedup filter + bulk insert happen after
        # the streaming pass: one SELECT and one INSERT per chunk.
        # "pattern_name" is metadata, not an Incident column — it is
        # stripped before insert.
        candidates = []

        with backend.open_stream(ref) as stream:
            text = io.TextIOWrapper(stream, encoding="utf-8", errors="ignore")
            for lineno, raw in enumerate(text):
                if lineno < start_line:
                    continue
                if lineno >= end_line:
                    break
                lines_in_slice += 1
                line = raw.strip()
                if not line:
                    continue

                # --- Pattern matching: single-pass engine, one search per
                # line. First match wins by severity rank (CRITICAL first);
                # invalid patterns were skipped at compile time with a
                # warning (see compile_matcher).
                winner = match_line(matcher, line)
                if winner is not None:
                    candidates.append(
                        {
                            "title": f"Pattern Match: {winner.name}",
                            "description": winner.description
                            or f"Log line matched pattern: {winner.name}",
                            "severity": map_severity(winner.severity_level),
                            "status": Status.OPEN,
                            "raw_log": line,
                            "node_id": node_id,
                            "pattern_id": winner.id,
                            "job_id": job_id,
                            "chunk_index": chunk_index,
                            "fingerprint": compute_fingerprint(
                                winner.id, node_id, line
                            ),
                            "pattern_name": winner.name,
                        }
                    )

        # --- Idempotency, layer 2: fingerprint dedup + bulk insert.
        # Intra-chunk first (the same line twice in one slice), then
        # against the table. SELECT-then-INSERT is portable across
        # PostgreSQL and SQLite (no ON CONFLICT dialect games); the UNIQUE
        # constraint on fingerprint is the backstop, and the savepoint
        # retry below handles the concurrent-chunk race — duplicate lines
        # landing in different slices of the same file.
        seen = set()
        unique_candidates = []
        for cand in candidates:
            if cand["fingerprint"] not in seen:
                seen.add(cand["fingerprint"])
                unique_candidates.append(cand)

        inserted_fps = []
        if unique_candidates:
            all_fps = [c["fingerprint"] for c in unique_candidates]
            existing = {
                row[0]
                for row in db.query(Incident.fingerprint).filter(
                    Incident.fingerprint.in_(all_fps)
                )
            }
            mappings = [
                {k: v for k, v in c.items() if k != "pattern_name"}
                for c in unique_candidates
                if c["fingerprint"] not in existing
            ]
            if mappings:
                savepoint = db.begin_nested()
                try:
                    db.bulk_insert_mappings(Incident, mappings)
                    db.flush()
                except IntegrityError:
                    # Lost the race: a concurrent chunk inserted one of
                    # these fingerprints first. Roll back to the savepoint
                    # — the delete above stays intact — re-read, and insert
                    # only what's still missing.
                    savepoint.rollback()
                    existing = {
                        row[0]
                        for row in db.query(Incident.fingerprint).filter(
                            Incident.fingerprint.in_(all_fps)
                        )
                    }
                    mappings = [
                        m for m in mappings if m["fingerprint"] not in existing
                    ]
                    if mappings:
                        db.bulk_insert_mappings(Incident, mappings)
                        db.flush()
            inserted_fps = [m["fingerprint"] for m in mappings]

        incidents_created = len(inserted_fps)
        dedup_skipped = len(candidates) - incidents_created
        inserted_set = set(inserted_fps)
        meta_by_fp = {
            c["fingerprint"]: c
            for c in unique_candidates
            if c["fingerprint"] in inserted_set
        }
        matched_patterns = sorted({c["pattern_name"] for c in meta_by_fp.values()})

        # bulk_insert_mappings does not populate ORM ids, and the commit
        # below expires state anyway: re-select ids for the event
        # payloads. Fingerprints are globally unique, so these rows are
        # unambiguously the ones this chunk just inserted.
        id_by_fp = {}
        if inserted_fps:
            id_by_fp = {
                fp: inc_id
                for inc_id, fp in db.query(
                    Incident.id, Incident.fingerprint
                ).filter(Incident.fingerprint.in_(inserted_fps))
            }
        # One commit covers the delete + the bulk insert atomically, as
        # before. Events publish only after it lands, so they never
        # describe rolled-back rows — and only for actually-inserted
        # incidents, never dedup-skipped ones. Publishing is best-effort
        # (see events.py).
        db.commit()
        for fp in inserted_fps:
            cand = meta_by_fp[fp]
            emit_incident_created(
                job_id=job_id,
                chunk_index=chunk_index,
                incident_id=id_by_fp[fp],
                pattern_id=cand["pattern_id"],
                pattern_name=cand["pattern_name"],
                severity=cand["severity"].value,
            )

        # --- Progress: atomic increment, safe under concurrent chunks. ---
        db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(chunks_completed=Job.chunks_completed + 1)
        )
        db.commit()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            if job.total_chunks:
                job.progress = int((job.chunks_completed or 0) / job.total_chunks * 100)
                db.commit()
            emit_job_progress(
                job_id=job_id,
                chunks_completed=job.chunks_completed or 0,
                total_chunks=job.total_chunks or 0,
                progress=job.progress or 0,
            )

        # Per-chunk Celery state replaces the old per-100-lines updates.
        try:
            self.update_state(
                state="PROGRESS",
                meta={
                    "chunk_index": chunk_index,
                    "start_line": start_line,
                    "end_line": end_line,
                    "lines": lines_in_slice,
                    "incidents_created": incidents_created,
                },
            )
        except Exception as celery_error:
            logger.warning(f"Could not update Celery state: {celery_error}")

        logger.info(
            f"Job {job_id} chunk {chunk_index} done: "
            f"{incidents_created} incidents from {lines_in_slice} lines "
            f"({dedup_skipped} duplicates skipped)"
        )
        return {
            "chunk_index": chunk_index,
            "status": "completed",
            "lines": lines_in_slice,
            "incidents_created": incidents_created,
            "dedup_skipped": dedup_skipped,
            "patterns_matched": matched_patterns,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Job {job_id} chunk {chunk_index} failed: {str(e)}")
        # Transient errors retry with backoff. Once retries are exhausted,
        # return a failure RESULT instead of raising: the chord callback
        # only fires when no header task raises, so raising here would
        # leave the job stuck in PROCESSING with no honest final state.
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        return {
            "chunk_index": chunk_index,
            "status": "failed",
            "error": str(e),
            "lines": 0,
            "incidents_created": 0,
            "patterns_matched": [],
        }
    finally:
        db.close()


@celery_app.task(bind=True)
def finalize_job(self, chunk_results, job_id):
    """Chord callback: aggregate chunk results into the job's terminal state.

    Celery invokes this as ``finalize_job(group_results, job_id)``.
    """
    db = SessionLocal()
    try:
        job, db = _get_job_or_raise(db, job_id)
        results = list(chunk_results or [])
        failed = [
            r for r in results if isinstance(r, dict) and r.get("status") == "failed"
        ]
        succeeded = [r for r in results if r not in failed]

        total_lines = sum(r.get("lines", 0) for r in succeeded)
        incidents_created = sum(r.get("incidents_created", 0) for r in succeeded)
        dedup_skipped = sum(r.get("dedup_skipped", 0) for r in succeeded)
        patterns_matched = sorted(
            {p for r in succeeded for p in r.get("patterns_matched", [])}
        )

        summary = {
            "total_lines": total_lines,
            "processed_lines": total_lines,
            "incidents_created": incidents_created,
            "dedup_skipped": dedup_skipped,
            "patterns_matched": patterns_matched,
            "total_chunks": len(results),
            "failed_chunks": [r.get("chunk_index") for r in failed],
        }
        job.result_summary = json.dumps(summary)
        job.progress = 100
        job.completed_at = datetime.utcnow()

        if failed:
            # Honest partial failure. JobStatus has no PARTIAL state —
            # adding one would churn the API and frontend for little value —
            # so any failed chunk marks the job FAILED, with per-chunk
            # errors preserved. Incidents written by succeeded chunks stay
            # in the database.
            job.status = JobStatus.FAILED
            job.error_message = (
                f"{len(failed)}/{len(results)} chunks failed "
                f"(indexes {[r.get('chunk_index') for r in failed]}): "
                + "; ".join(
                    f"chunk {r.get('chunk_index')}: {r.get('error')}" for r in failed
                )
            )
            logger.error(f"Job {job_id} partially failed: {job.error_message}")
        else:
            job.status = JobStatus.COMPLETED
            job.error_message = None
            logger.info(
                f"Job {job_id} completed: {incidents_created} incidents from "
                f"{total_lines} lines across {len(results)} chunks"
            )

        db.commit()
        # Terminal domain event for SSE subscribers. Best-effort: a down
        # event bus must not break finalization.
        if failed:
            emit_job_failed(
                job_id=job_id, error=job.error_message or "", summary=summary
            )
        else:
            emit_job_completed(job_id=job_id, summary=summary)
        return {"job_id": job_id, "status": job.status.value, **summary}
    except Exception as e:
        logger.error(f"Job {job_id} finalize failed: {str(e)}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = f"finalize failed: {str(e)}"
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Could not mark job {job_id} failed: {db_error}")
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def process_log_file(
    self,
    job_id: str,
    file_path: Optional[str] = None,
    log_lines: Optional[List[str]] = None,
    storage_ref: Optional[Dict[str, str]] = None,
    node_hostname: Optional[str] = None,
    description: Optional[str] = None,
):
    """Backwards-compatible entrypoint for log processing.

    When ``storage_ref`` (an object-storage content reference) is given,
    the upload is fanned out into the chunked Celery group + chord
    pipeline (:func:`fanout_process_log`), which owns the job's terminal
    state. The legacy ``file_path`` and ``log_lines`` inputs keep the
    original monolithic behavior below — the stream and cluster ingest
    paths depend on it, so that body is preserved verbatim.
    """
    if storage_ref is not None:
        # Object-storage upload: hand off to the chunked pipeline. Returns
        # a JSON-safe dict carrying the fan-out task id (returning the raw
        # AsyncResult would break the json result serializer); the chord's
        # finalizer owns the job's terminal state.
        fanout_task = fanout_process_log.delay(
            job_id=job_id,
            storage_ref=storage_ref,
            node_hostname=node_hostname,
            description=description,
        )
        return {
            "status": "fanned_out",
            "job_id": job_id,
            "fanout_task_id": fanout_task.id,
        }

    # Get database session
    db = SessionLocal()

    try:
        # Update job status to processing
        # Retry logic for race condition in eager mode
        job = None
        retry_count = 0
        max_retries = 3
        while not job and retry_count < max_retries:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    time.sleep(0.1)  # Short delay to allow transaction to propagate
                    db.close()
                    db = SessionLocal()
        
        if not job:
            raise Exception(f"Job {job_id} not found after {max_retries} retries")

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        db.commit()

        # Get log lines — prefer the object-storage content reference (the
        # cross-container handoff); fall back to the legacy inputs.
        if storage_ref is not None:
            ref = StorageReference.from_dict(storage_ref)
            backend = backend_from_settings(settings)
            logger.info(
                f"Processing job {job_id}: streaming object "
                f"{ref.bucket}/{ref.key} via {ref.backend} backend"
            )
            with backend.open_stream(ref) as stream:
                lines = stream_to_text_lines(stream)
        elif file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        elif log_lines:
            lines = log_lines
        else:
            raise Exception("No storage reference, file path, or log lines provided")

        total_lines = len(lines)
        processed_lines = 0
        incidents_created = 0
        dedup_skipped = 0
        # (incident, pattern_name) pairs; published at each commit point so
        # SSE subscribers see incidents as the legacy path progresses.
        created_incidents = []
        published_incidents = 0

        # Get or create node
        node = None
        if node_hostname:
            node = db.query(Node).filter(Node.hostname == node_hostname).first()
            if not node:
                node = Node(
                    hostname=node_hostname,
                    node_type="unknown",
                    description=f"Auto-created from log processing: {description or 'No description'}",
                )
                db.add(node)
                db.commit()
                db.refresh(node)

        # Get all active patterns
        patterns = db.query(Pattern).filter(Pattern.is_active == True).all()
        logger.info(f"Processing job {job_id}: Found {len(patterns)} active patterns")
        logger.info(f"Processing job {job_id}: File has {total_lines} lines")

        # Single-pass engine, compiled from the fresh pattern read above.
        matcher = compile_matcher(patterns)
        if matcher.skipped:
            logger.warning(
                f"Processing job {job_id}: skipped invalid patterns: "
                f"{matcher.skipped}"
            )
        matched_pattern_names = set()

        # Process each line
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Single-pass match: first win by severity rank (CRITICAL first).
            winner = match_line(matcher, line)
            if winner is not None:
                # Create incident. The fingerprint is set here so legacy
                # rows carry the same identity scheme as chunked rows (see
                # src/workers/fingerprint.py); the dedup filter at each
                # commit point below decides whether it is inserted.
                # Counts (incidents_created / matched_pattern_names) are
                # updated there too, over inserted rows only.
                incident = Incident(
                    title=f"Pattern Match: {winner.name}",
                    description=winner.description
                    or f"Log line matched pattern: {winner.name}",
                    severity=map_severity(winner.severity_level),
                    status=Status.OPEN,
                    raw_log=line,
                    node_id=node.id if node else None,
                    pattern_id=winner.id,
                    job_id=job_id,
                    fingerprint=compute_fingerprint(
                        winner.id, node.id if node else None, line
                    ),
                )
                db.add(incident)
                created_incidents.append((incident, winner.name))

            processed_lines += 1

            # Update progress
            if processed_lines % 100 == 0 or processed_lines == total_lines:
                progress = int((processed_lines / total_lines) * 100)
                job.progress = progress

                # Update Celery task state (handle Windows Celery issues)
                try:
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": processed_lines,
                            "total": total_lines,
                            "progress": progress,
                            "incidents_created": incidents_created,
                        },
                    )
                except Exception as celery_error:
                    logger.warning(f"Could not update Celery state: {celery_error}")

                # Idempotency for the legacy path: drop candidates whose
                # fingerprint already exists (re-ingest of the same file).
                # Pending objects are expunged before flush, so they are
                # never inserted and never emit events. Without this, the
                # UNIQUE constraint on fingerprint would turn a re-run into
                # an IntegrityError instead of a clean no-op. The `existing`
                # set absorbs each batch's own fingerprints as it goes, so
                # duplicate lines within one batch dedup too.
                # chunk_index=None: this is the legacy monolithic path.
                batch = created_incidents[published_incidents:]
                fresh = []
                if batch:
                    existing = {
                        row[0]
                        for row in db.query(Incident.fingerprint).filter(
                            Incident.fingerprint.in_(
                                [inc.fingerprint for inc, _ in batch]
                            )
                        )
                    }
                    for inc, name in batch:
                        if inc.fingerprint in existing:
                            db.expunge(inc)
                            dedup_skipped += 1
                        else:
                            existing.add(inc.fingerprint)
                            fresh.append((inc, name))
                    incidents_created += len(fresh)
                    matched_pattern_names.update(name for _, name in fresh)
                # Flush to assign ids, then publish incident events only
                # after the commit lands (never describe rolled-back rows).
                db.flush()
                pending = [
                    {
                        "incident_id": inc.id,
                        "pattern_id": inc.pattern_id,
                        "pattern_name": name,
                        "severity": inc.severity.value,
                    }
                    for inc, name in fresh
                ]
                published_incidents = len(created_incidents)
                db.commit()
                for payload in pending:
                    emit_incident_created(
                        job_id=job_id, chunk_index=None, **payload
                    )
                emit_job_progress(
                    job_id=job_id,
                    chunks_completed=0,
                    total_chunks=0,
                    progress=progress,
                )

        # Update job status
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 100
        summary = {
            "total_lines": total_lines,
            "processed_lines": processed_lines,
            "incidents_created": incidents_created,
            "dedup_skipped": dedup_skipped,
            # Winners tracked during the single pass above; the old code
            # re-scanned every pattern over every line here (O(P*L)).
            # Shape unchanged (int); semantics now count patterns that
            # won at least one line under first-match-wins, over
            # inserted incidents only.
            "patterns_matched": len(matched_pattern_names),
        }
        job.result_summary = json.dumps(summary)

        logger.info(
            f"Job {job_id} completed: Created {incidents_created} incidents from {total_lines} lines"
        )

        db.commit()
        emit_job_completed(job_id=job_id, summary=summary)

        # Clean up the legacy local temp file. Objects fetched via a
        # storage reference are intentionally kept: the stored object is the
        # durable upload artifact the job record points at (lifecycle/
        # retention policy is a separate concern).
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return {
            "status": "completed",
            "job_id": job_id,
            "total_lines": total_lines,
            "processed_lines": processed_lines,
            "incidents_created": incidents_created,
            "result": job.result_summary,
        }

    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
            emit_job_failed(job_id=job_id, error=str(e), summary=None)

        # Clean up the legacy local temp file. Objects fetched via a
        # storage reference are intentionally kept: the stored object is the
        # durable upload artifact the job record points at (lifecycle/
        # retention policy is a separate concern).
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        # Retry with error handling for Windows Celery issues
        try:
            raise self.retry(exc=e, countdown=60, max_retries=3)
        except Exception as retry_error:
            logger.error(f"Job {job_id} failed and could not retry: {str(e)}")
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
            raise

    finally:
        db.close()


def map_severity(pattern_severity: str) -> Severity:
    """Map pattern severity level to Incident severity enum"""
    severity_mapping = {
        "LOW": Severity.LOW,
        "MEDIUM": Severity.MEDIUM,
        "HIGH": Severity.HIGH,
        "CRITICAL": Severity.CRITICAL,
    }

    return severity_mapping.get(pattern_severity.upper(), Severity.MEDIUM)


def create_default_patterns(db: Session):
    """Create default patterns for common OneFS log events"""

    default_patterns = [
        {
            "name": "Disk Failure",
            "description": "Critical disk failure detected",
            "regex_pattern": r"(disk|drive).*fail|(error|critical).*disk",
            "category": "hardware",
            "severity_level": "CRITICAL",
        },
        {
            "name": "Network Timeout",
            "description": "Network communication timeout",
            "regex_pattern": r"network.*timeout|connection.*timeout",
            "category": "network",
            "severity_level": "HIGH",
        },
        {
            "name": "High CPU Usage",
            "description": "CPU usage exceeds threshold",
            "regex_pattern": r"cpu.*high|processor.*load",
            "category": "performance",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Memory Pressure",
            "description": "System memory under pressure",
            "regex_pattern": r"memory.*pressure|out.*of.*memory",
            "category": "performance",
            "severity_level": "HIGH",
        },
        {
            "name": "Authentication Failure",
            "description": "User authentication failed",
            "regex_pattern": r"auth.*fail|login.*fail|authentication.*error",
            "category": "security",
            "severity_level": "MEDIUM",
        },
        {
            "name": "File System Error",
            "description": "File system operation error",
            "regex_pattern": r"filesystem.*error|fs.*error|inode.*error",
            "category": "filesystem",
            "severity_level": "HIGH",
        },
        # OneFS-specific patterns for /var/log/messages
        {
            "name": "OneFS System Alert",
            "description": "Critical OneFS system alert or daemon failure",
            "regex_pattern": r"isilon_d.*critical|isi.*critical|system.*alert",
            "category": "system",
            "severity_level": "CRITICAL",
        },
        {
            "name": "OneFS Service Failure",
            "description": "OneFS service or daemon failure/restart",
            "regex_pattern": r"isilon_d.*fail|daemon.*restart|service.*stop|isi_.*_d.*error",
            "category": "system",
            "severity_level": "HIGH",
        },
        {
            "name": "Cluster Quorum Issue",
            "description": "OneFS cluster quorum or connectivity problems",
            "regex_pattern": r"cluster.*quorum|node.*disconnect|cluster.*reform|gmp.*fail",
            "category": "cluster",
            "severity_level": "CRITICAL",
        },
        {
            "name": "SMART Disk Failure",
            "description": "SMART disk monitoring failure or prediction",
            "regex_pattern": r"smartd.*fail|smart.*error|disk.*predict.*fail|drive.*fail",
            "category": "hardware",
            "severity_level": "CRITICAL",
        },
        {
            "name": "Storage Pool Degraded",
            "description": "OneFS storage pool degraded or unavailable",
            "regex_pattern": r"pool.*degraded|storage.*pool.*fail|flexpool.*error|diskpool.*unavail",
            "category": "storage",
            "severity_level": "HIGH",
        },
        {
            "name": "File System Capacity",
            "description": "OneFS file system capacity or quota issues",
            "regex_pattern": r"filesystem.*full|quota.*exceed|capacity.*critical|space.*low",
            "category": "filesystem",
            "severity_level": "HIGH",
        },
        {
            "name": "Network Interface Down",
            "description": "Network interface failure or IP address change",
            "regex_pattern": r"interface.*down|iface.*fail|ip.*change|link.*down",
            "category": "network",
            "severity_level": "HIGH",
        },
        {
            "name": "NFS Timeout Error",
            "description": "NFS service timeout or client connection issues",
            "regex_pattern": r"nfs.*timeout|nfs.*error|nfs.*fail|rpc.*timeout",
            "category": "network",
            "severity_level": "MEDIUM",
        },
        {
            "name": "SMB/CIFS Error",
            "description": "SMB or CIFS service errors and connectivity issues",
            "regex_pattern": r"smb.*error|cifs.*fail|samba.*error|winbind.*fail",
            "category": "network",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Kerberos Authentication Failure",
            "description": "Kerberos authentication or ticket issues",
            "regex_pattern": r"kerberos.*fail|krb5.*error|ticket.*expire|auth.*krb",
            "category": "security",
            "severity_level": "MEDIUM",
        },
        {
            "name": "LDAP/AD Connectivity",
            "description": "LDAP or Active Directory connection problems",
            "regex_pattern": r"ldap.*timeout|ad.*connect|domain.*controller.*fail|sssd.*error",
            "category": "security",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Security Audit Deny",
            "description": "Security audit denial or permission issues",
            "regex_pattern": r"audit.*deny|permission.*denied|access.*denied|security.*violation",
            "category": "security",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Hardware Temperature Alert",
            "description": "Hardware temperature or environmental monitoring alerts",
            "regex_pattern": r"temp.*critical|temperature.*high|thermal.*alert|fan.*fail",
            "category": "hardware",
            "severity_level": "HIGH",
        },
        {
            "name": "Power Supply Failure",
            "description": "Power supply or UPS failure alerts",
            "regex_pattern": r"power.*supply.*fail|ups.*fail|psu.*error|power.*loss",
            "category": "hardware",
            "severity_level": "CRITICAL",
        },
        {
            "name": "OneFS Upgrade Event",
            "description": "OneFS software upgrade or patch events",
            "regex_pattern": r"upgrade.*start|upgrade.*complete|patch.*install|isi.*upgrade",
            "category": "system",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Snapshot Delete Error",
            "description": "OneFS snapshot creation or deletion errors",
            "regex_pattern": r"snapshot.*fail|snap.*error|isi.*snapshot.*error",
            "category": "filesystem",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Job Engine Failure",
            "description": "OneFS job engine or backup job failures",
            "regex_pattern": r"job.*engine.*fail|backup.*error|replication.*fail|isi.*job.*error",
            "category": "system",
            "severity_level": "MEDIUM",
        },
    ]

    for pattern_data in default_patterns:
        existing_pattern = (
            db.query(Pattern).filter(Pattern.name == pattern_data["name"]).first()
        )

        if not existing_pattern:
            pattern = Pattern(**pattern_data)
            db.add(pattern)

    db.commit()
