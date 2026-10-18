from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.api.routers.auth import get_current_user
from src.models import ActionType, Incident, IncidentActivity, Job, Severity, Status

router = APIRouter(dependencies=[Depends(get_current_user)])


class WorkDetails(BaseModel):
    work_description: Optional[str] = None
    estimated_hours: Optional[float] = None
    work_type: Optional[str] = None
    tools_used: Optional[List[str]] = []


class EscalationDetails(BaseModel):
    escalation_reason: str
    target_level: Optional[str] = None
    urgency: Optional[str] = None
    assigned_team: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    new_status: str
    work_details: Optional[WorkDetails] = None
    escalation_details: Optional[EscalationDetails] = None
    comment: Optional[str] = None


@router.get("/incidents", summary="Get incidents with filtering")
def get_incidents(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    severity: Optional[str] = Query(
        None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"
    ),
    status: Optional[str] = Query(
        None, description="Filter by status (OPEN, IN_PROGRESS, RESOLVED, ESCALATED)"
    ),
    node_id: Optional[int] = Query(None, description="Filter by node ID"),
    pattern_id: Optional[int] = Query(None, description="Filter by pattern ID"),
    start_date: Optional[datetime] = Query(
        None, description="Filter incidents from this date"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter incidents until this date"
    ),
    cluster: Optional[str] = Query(
        None, description="Filter by cluster name (via the parent job)"
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieve incidents with optional filtering and pagination.

    Supports filtering by:
    - **severity**: Incident severity level
    - **status**: Incident status
    - **node_id**: Source node ID
    - **pattern_id**: Pattern ID that matched
    - **start_date**: Start date for filtering
    - **end_date**: End date for filtering
    - **cluster**: Cluster name of the parent job
    """

    query = db.query(Incident)

    if cluster:
        query = query.join(Job, Incident.job_id == Job.id).filter(
            Job.cluster_name == cluster
        )

    # Apply filters
    if severity:
        try:
            severity_enum = Severity(severity.upper())
            query = query.filter(Incident.severity == severity_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity. Must be one of: {[s.value for s in Severity]}",
            )

    if status:
        try:
            status_enum = Status(status.upper())
            query = query.filter(Incident.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {[s.value for s in Status]}",
            )

    if node_id:
        query = query.filter(Incident.node_id == node_id)

    if pattern_id:
        query = query.filter(Incident.pattern_id == pattern_id)

    if start_date:
        query = query.filter(Incident.created_at >= start_date)

    if end_date:
        query = query.filter(Incident.created_at <= end_date)

    # Get total count
    total = query.count()

    # Apply pagination
    incidents = (
        query.order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "incidents": [
            {
                "id": incident.id,
                "title": incident.title,
                "description": incident.description,
                "severity": incident.severity.value,
                "status": incident.status.value,
                "raw_log": incident.raw_log,
                "created_at": incident.created_at,
                "updated_at": incident.updated_at,
                "processed_at": incident.processed_at,
                "node": (
                    {
                        "id": incident.node.id,
                        "hostname": incident.node.hostname,
                        "ip_address": incident.node.ip_address,
                    }
                    if incident.node
                    else None
                ),
                "pattern": (
                    {
                        "id": incident.pattern.id,
                        "name": incident.pattern.name,
                        "category": incident.pattern.category,
                        "severity_level": incident.pattern.severity_level,
                    }
                    if incident.pattern
                    else None
                ),
            }
            for incident in incidents
        ],
    }


@router.get("/incidents/{incident_id}", summary="Get incident by ID")
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Retrieve a specific incident by ID"""

    incident = db.query(Incident).filter(Incident.id == incident_id).first()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return {
        "id": incident.id,
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity.value,
        "status": incident.status.value,
        "raw_log": incident.raw_log,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "processed_at": incident.processed_at,
        "node": (
            {
                "id": incident.node.id,
                "hostname": incident.node.hostname,
                "ip_address": incident.node.ip_address,
                "node_type": incident.node.node_type,
                "version": incident.node.version,
            }
            if incident.node
            else None
        ),
        "pattern": (
            {
                "id": incident.pattern.id,
                "name": incident.pattern.name,
                "description": incident.pattern.description,
                "category": incident.pattern.category,
                "severity_level": incident.pattern.severity_level,
                "regex_pattern": incident.pattern.regex_pattern,
            }
            if incident.pattern
            else None
        ),
    }


@router.put("/incidents/{incident_id}/status", summary="Update incident status")
def update_incident_status(
    incident_id: int, request: StatusUpdateRequest, db: Session = Depends(get_db)
):
    """Update the status of an incident with optional work details"""

    incident = db.query(Incident).filter(Incident.id == incident_id).first()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        status_enum = Status(request.new_status.upper())
        old_status = incident.status
        incident.status = status_enum
        incident.updated_at = datetime.utcnow()
        db.commit()

        # Create activity record
        action_type = None
        details = {}

        if request.new_status.upper() == "IN_PROGRESS" and request.work_details:
            action_type = ActionType.START_WORK
            details = {
                "work_description": request.work_details.work_description,
                "estimated_hours": request.work_details.estimated_hours,
                "work_type": request.work_details.work_type,
                "tools_used": request.work_details.tools_used,
            }
        elif request.new_status.upper() == "ESCALATED" and request.escalation_details:
            action_type = ActionType.ESCALATE
            details = {
                "escalation_reason": request.escalation_details.escalation_reason,
                "target_level": request.escalation_details.target_level,
                "urgency": request.escalation_details.urgency,
                "assigned_team": request.escalation_details.assigned_team,
            }
        else:
            action_type = (
                ActionType.RESOLVE
                if request.new_status.upper() == "RESOLVED"
                else ActionType.COMMENT
            )
            details = {"comment": request.comment} if request.comment else {}

        if action_type:
            activity = IncidentActivity(
                incident_id=incident_id,
                user_id="current_user",  # Will be updated with real user auth
                action_type=action_type,
                description=request.comment
                or f"Status changed from {old_status.value} to {request.new_status.upper()}",
                details=str(details),
            )
            db.add(activity)
            db.commit()

        return {
            "id": incident.id,
            "status": incident.status.value,
            "message": f"Incident status updated to {request.new_status.upper()}",
            "old_status": old_status.value,
            "new_status": request.new_status.upper(),
            "activity_created": True if action_type else False,
        }

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {[s.value for s in Status]}",
        )


@router.get(
    "/incidents/{incident_id}/activity", summary="Get incident activity history"
)
def get_incident_activity(
    incident_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get activity history for a specific incident."""

    # Check if incident exists
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Get activities
    activities = (
        db.query(IncidentActivity)
        .filter(IncidentActivity.incident_id == incident_id)
        .order_by(IncidentActivity.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    total = (
        db.query(IncidentActivity)
        .filter(IncidentActivity.incident_id == incident_id)
        .count()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "incident_id": incident_id,
        "activities": [
            {
                "id": activity.id,
                "action_type": activity.action_type.value,
                "description": activity.description,
                "details": activity.details,
                "user_id": activity.user_id,
                "created_at": (
                    activity.created_at.isoformat() if activity.created_at else None
                ),
            }
            for activity in activities
        ],
    }
