import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.core.celery import celery_app
from src.core.events import emit_job_cancelled, get_event_bus, job_channel
from src.db.database import SessionLocal, get_db
from src.api.routers.auth import get_current_user
from src.models import Job, JobStatus

router = APIRouter(dependencies=[Depends(get_current_user)])

# Terminal states: cancelling one is a no-op error (409), never silent
# success. CANCELLED joins COMPLETED/FAILED here.
TERMINAL_JOB_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


@router.get("/jobs", summary="Get all jobs")
def get_jobs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    status: Optional[str] = Query(None, description="Filter by job status"),
    cluster: Optional[str] = Query(
        None, description="Filter by cluster name (multi-cluster deployments)"
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve all jobs with optional filtering and pagination.

    - **status**: Filter by job status (PENDING, PROCESSING, COMPLETED, FAILED)
    - **cluster**: Filter by cluster name. Jobs without a cluster (uploads,
      streams, pre-multi-cluster jobs) are treated as the default cluster
      and match only when no cluster filter is given.
    """

    query = db.query(Job)

    if status:
        try:
            status_enum = JobStatus(status.upper())
            query = query.filter(Job.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {[s.value for s in JobStatus]}",
            )

    if cluster:
        query = query.filter(Job.cluster_name == cluster)

    total = query.count()
    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "jobs": [
            {
                "id": job.id,
                "filename": job.filename,
                "file_size": job.file_size,
                "status": job.status.value,
                "progress": job.progress,
                "cluster_name": job.cluster_name,
                "result_summary": job.result_summary,
                "error_message": job.error_message,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
            }
            for job in jobs
        ],
    }


@router.get("/jobs/{job_id}", summary="Get job by ID")
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Retrieve a specific job by ID"""

    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get Celery task info if available
    task_info = None
    try:
        task_result = celery_app.AsyncResult(job_id)
        task_info = {
            "celery_task_id": task_result.id,
            "celery_status": task_result.status,
            "celery_result": task_result.result if task_result.ready() else None,
            "celery_traceback": task_result.traceback if task_result.failed() else None,
        }
    except Exception:
        pass

    return {
        "id": job.id,
        "filename": job.filename,
        "file_size": job.file_size,
        "status": job.status.value,
        "progress": job.progress,
        "cluster_name": job.cluster_name,
        "result_summary": job.result_summary,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "celery_task": task_info,
    }


@router.delete("/jobs/{job_id}", summary="Delete job")
def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete a job and its associated incidents"""

    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only allow deletion of terminal jobs (completed, failed, cancelled)
    if job.status not in TERMINAL_JOB_STATUSES:
        raise HTTPException(
            status_code=400, detail="Can only delete completed, failed or cancelled jobs"
        )

    # Delete associated incidents
    from src.models import Incident

    db.query(Incident).filter(Incident.job_id == job_id).delete()

    # Delete job
    db.delete(job)
    db.commit()

    return {"message": f"Job {job_id} and associated incidents deleted successfully"}


@router.post("/jobs/{job_id}/cancel", summary="Cancel a running job")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a PENDING or PROCESSING job.

    Revokes every Celery task id recorded on the job (entrypoint task
    from the ingest handlers, plus the fan-out/chunk/chord ids the
    pipeline appends) with ``terminate=True`` -- plain ``revoke()``
    only stops *pending* tasks, while terminate also SIGTERMs *running*
    ones, which is the point of cancelling a 10k-lines-per-chunk job.
    The job row moves to CANCELLED (commit-then-publish, like every
    other terminal transition) and a ``job.cancelled`` domain event goes
    out on the job's channel.

    Worker safety is layered, not trusted to the revoke alone:

    * ``finalize_job`` (the chord callback) early-returns on a CANCELLED
      job -- a chord that fires after cancellation can never resurrect
      the job as COMPLETED/FAILED.
    * ``fanout_process_log`` refuses to fan out a CANCELLED job.
    * ``process_chunk`` and the legacy loop check the row and stop.

    - 404: no such job.
    - 409: job already terminal (COMPLETED/FAILED/CANCELLED).
    - 422: job has no tracked Celery task ids (created before task
      tracking) -- nothing to revoke, said honestly instead of faked.
    - 503: the revoke itself failed (broker unreachable) -- the job
      keeps its state and the client can retry.
    """

    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in TERMINAL_JOB_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job is already {job.status.value.lower()}; "
                "cancelling a terminal job is a no-op"
            ),
        )

    task_ids = list(job.celery_task_ids or [])
    if not task_ids:
        raise HTTPException(
            status_code=422,
            detail=(
                "Job has no tracked Celery task IDs "
                "(created before task tracking was added); "
                "there is nothing to revoke"
            ),
        )

    # Revoke BEFORE the state change: if the broker is unreachable the
    # job keeps its current state and the client can retry. Only a
    # successful revoke commits CANCELLED.
    try:
        celery_app.control.revoke(task_ids, terminate=True)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Task queue unreachable; job not cancelled: {e}",
        )

    job.status = JobStatus.CANCELLED
    job.error_message = "Cancelled by user"
    job.completed_at = datetime.utcnow()
    db.commit()

    emit_job_cancelled(job_id=job_id, cluster_name=job.cluster_name)

    return {
        "id": job.id,
        "status": job.status.value,
        "revoked_task_ids": task_ids,
        "message": "Job cancelled; Celery tasks revoked",
    }


# NOTE: this router is mounted with prefix "/api/v1" (see src/app/main.py),
# so the path below must NOT repeat the prefix — the old "/api/v1/..." here
# produced the double-prefixed "/api/v1/api/v1/jobs/{id}/events" that 404'd
# the frontend. The old polling endpoint never worked, so replacing it is
# safe; see the commit message.
@router.get("/jobs/{job_id}/events", summary="Job progress events (SSE)")
def job_events(job_id: str, db: Session = Depends(get_db)):
    """
    Server-Sent Events over the Redis pub/sub domain event bus.

    Subscribes to the job's channel (``job:{job_id}``, or
    ``job:{cluster}:{job_id}`` for cluster-scoped jobs) instead of polling
    the database every second per client. Emits the current snapshot first,
    then live ``progress`` / ``incident`` events, then a terminal
    ``complete`` event. A ``: ping`` heartbeat comment is sent every 20s so
    idle connections are not killed by proxies during long jobs.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    snapshot = {
        "id": job.id,
        "status": job.status.value,
        "progress": job.progress or 0,
    }
    terminal = job.status in TERMINAL_JOB_STATUSES
    # Capture before db.close(): the generator below runs on a detached
    # instance, and only already-loaded attributes are safe to touch.
    job_cluster = job.cluster_name
    db.close()

    def _full_snapshot() -> dict:
        """One fresh DB read for the terminal state (not per-second)."""
        session = SessionLocal()
        try:
            j = session.query(Job).filter(Job.id == job_id).first()
            if not j:
                return {"id": job_id, "error": "Job not found"}
            return {
                "id": j.id,
                "status": j.status.value,
                "progress": j.progress or 0,
                "result_summary": j.result_summary,
                "error_message": j.error_message,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": (
                    j.completed_at.isoformat() if j.completed_at else None
                ),
            }
        finally:
            session.close()

    def event_generator():
        # Already terminal: one snapshot + complete, no subscription needed.
        if terminal:
            yield f"event: progress\ndata: {json.dumps(snapshot)}\n\n"
            yield f"event: complete\ndata: {json.dumps(_full_snapshot())}\n\n"
            return

        # Cluster-scoped channel: a subscriber to one cluster's job
        # never sees another cluster's events. Unclustered jobs keep the
        # bare job:{job_id} channel (backwards compatible).
        channel = job_channel(job_id, job_cluster)
        try:
            sub = get_event_bus().subscribe([channel])
        except Exception as e:
            yield (
                "event: error\n"
                f"data: {json.dumps({'error': f'event bus unavailable: {e}'})}\n\n"
            )
            return

        try:
            yield f"event: progress\ndata: {json.dumps(snapshot)}\n\n"
            while True:
                # Sync generator (StreamingResponse runs these in a
                # threadpool), so the blocking get() with its 20s timeout is
                # fine directly; None means the heartbeat window elapsed.
                msg = sub.get(20.0)
                if msg is None:
                    yield ": ping\n\n"
                    continue
                _channel, event = msg
                etype = event.get("type")
                if etype == "job.progress":
                    # A job emitting progress is processing by definition.
                    yield (
                        "event: progress\n"
                        f"data: {json.dumps({'id': job_id, 'status': 'PROCESSING', 'progress': event.get('progress', 0)})}\n\n"
                    )
                elif etype == "incident.created":
                    yield f"event: incident\ndata: {json.dumps(event)}\n\n"
                elif etype in ("job.completed", "job.failed", "job.cancelled"):
                    yield f"event: complete\ndata: {json.dumps(_full_snapshot())}\n\n"
                    break
                # Unknown event types are ignored (forward-compatible).
        finally:
            sub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
