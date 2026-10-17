import asyncio
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.core.celery import celery_app
from src.db.database import get_db
from src.api.routers.auth import get_current_user
from src.models import Job, JobStatus

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/jobs", summary="Get all jobs")
async def get_jobs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    status: Optional[str] = Query(None, description="Filter by job status"),
    db: Session = Depends(get_db),
):
    """
    Retrieve all jobs with optional filtering and pagination.

    - **status**: Filter by job status (PENDING, PROCESSING, COMPLETED, FAILED)
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
async def get_job(job_id: str, db: Session = Depends(get_db)):
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
        "result_summary": job.result_summary,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "celery_task": task_info,
    }


@router.delete("/jobs/{job_id}", summary="Delete job")
async def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete a job and its associated incidents"""

    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only allow deletion of completed or failed jobs
    if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise HTTPException(
            status_code=400, detail="Can only delete completed or failed jobs"
        )

    # Delete associated incidents
    from src.models import Incident

    db.query(Incident).filter(Incident.job_id == job_id).delete()

    # Delete job
    db.delete(job)
    db.commit()

    return {"message": f"Job {job_id} and associated incidents deleted successfully"}


@router.post("/jobs/{job_id}/cancel", summary="Cancel job")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running job"""

    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
        raise HTTPException(
            status_code=400, detail="Can only cancel pending or processing jobs"
        )

    try:
        # Cancel Celery task
        celery_app.control.revoke(job_id, terminate=True)

        # Update job status
        job.status = JobStatus.FAILED
        job.error_message = "Job cancelled by user"
        job.completed_at = None
        db.commit()

        return {
            "id": job.id,
            "status": job.status.value,
            "message": "Job cancelled successfully",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.get("/api/v1/jobs/{job_id}/events", summary="Get job progress events (SSE)")
async def job_events(job_id: str, db: Session = Depends(get_db)):
    """
    Server-Sent Events endpoint for real-time job progress updates.

    Streams job status and progress every 1 second until job completes or fails.
    """

    async def event_generator():
        while True:
            # Get fresh job data
            job = db.query(Job).filter(Job.id == job_id).first()

            if not job:
                yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            # Build event data
            event_data = {
                "id": job.id,
                "status": job.status.value,
                "progress": job.progress,
                "result_summary": job.result_summary,
                "error_message": job.error_message,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": (
                    job.completed_at.isoformat() if job.completed_at else None
                ),
            }

            # Add Celery task info if available
            try:
                task_result = celery_app.AsyncResult(job_id)
                event_data["celery_status"] = task_result.status
            except Exception:
                pass

            # Send event
            yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

            # Stop if job is done
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"
                break

            # Wait before next update
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
