"""Nodes management API router."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.api.routers.auth import get_current_user
from src.models import Incident, Node

router = APIRouter(dependencies=[Depends(get_current_user)])


class NodeResponse(BaseModel):
    id: int
    hostname: str
    ip_address: Optional[str]
    node_type: Optional[str]
    version: Optional[str]
    description: Optional[str]
    created_at: str
    updated_at: Optional[str]
    incident_count: int = 0

    class Config:
        from_attributes = True


class NodeCreate(BaseModel):
    hostname: str
    ip_address: Optional[str] = None
    node_type: Optional[str] = "unknown"
    version: Optional[str] = None
    description: Optional[str] = None


class NodeUpdate(BaseModel):
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    node_type: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None


@router.get("/nodes")
def get_nodes(
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get all nodes from the database with optional filtering."""
    query = db.query(Node)

    if node_type:
        query = query.filter(Node.node_type == node_type)

    # Get incident counts for each node
    incident_counts = (
        db.query(Incident.node_id, func.count(Incident.id).label("count"))
        .group_by(Incident.node_id)
        .all()
    )
    count_map = {n_id: cnt for n_id, cnt in incident_counts}

    nodes = query.order_by(Node.created_at.desc()).offset(skip).limit(limit).all()
    total = query.count()

    result = []
    for n in nodes:
        n_dict = {
            "id": n.id,
            "hostname": n.hostname,
            "ip_address": n.ip_address,
            "node_type": n.node_type,
            "version": n.version,
            "description": n.description,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
            "incident_count": count_map.get(n.id, 0),
        }
        result.append(n_dict)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "nodes": result
    }


@router.get("/nodes/{node_id}", response_model=NodeResponse)
def get_node(node_id: int, db: Session = Depends(get_db)):
    """Get a specific node by ID."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    incident_count = db.query(Incident).filter(Incident.node_id == node_id).count()

    return {
        "id": node.id,
        "hostname": node.hostname,
        "ip_address": node.ip_address,
        "node_type": node.node_type,
        "version": node.version,
        "description": node.description,
        "created_at": node.created_at.isoformat() if node.created_at else None,
        "updated_at": node.updated_at.isoformat() if node.updated_at else None,
        "incident_count": incident_count,
    }


@router.get("/nodes/{node_id}/incidents")
def get_node_incidents(
    node_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get all incidents for a specific node."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    query = db.query(Incident).filter(Incident.node_id == node_id)

    if status:
        from src.models import Status

        try:
            status_enum = Status(status.upper())
            query = query.filter(Incident.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {[s.value for s in Status]}",
            )

    if severity:
        from src.models import Severity

        try:
            severity_enum = Severity(severity.upper())
            query = query.filter(Incident.severity == severity_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity. Must be one of: {[s.value for s in Severity]}",
            )

    total = query.count()
    incidents = (
        query.order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "node": {
            "id": node.id,
            "hostname": node.hostname,
            "ip_address": node.ip_address,
        },
        "incidents": [
            {
                "id": incident.id,
                "title": incident.title,
                "description": incident.description,
                "severity": incident.severity.value,
                "status": incident.status.value,
                "created_at": incident.created_at,
                "pattern": incident.pattern.name if incident.pattern else None,
            }
            for incident in incidents
        ],
    }


@router.post("/nodes", response_model=NodeResponse)
def create_node(node_data: NodeCreate, db: Session = Depends(get_db)):
    """Create a new node (manual entry)."""
    # Check for duplicate hostname
    existing = db.query(Node).filter(Node.hostname == node_data.hostname).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Node with hostname '{node_data.hostname}' already exists",
        )

    node = Node(
        hostname=node_data.hostname,
        ip_address=node_data.ip_address,
        node_type=node_data.node_type,
        version=node_data.version,
        description=node_data.description,
    )
    db.add(node)
    db.commit()
    db.refresh(node)

    return {
        "id": node.id,
        "hostname": node.hostname,
        "ip_address": node.ip_address,
        "node_type": node.node_type,
        "version": node.version,
        "description": node.description,
        "created_at": node.created_at.isoformat() if node.created_at else None,
        "updated_at": node.updated_at.isoformat() if node.updated_at else None,
        "incident_count": 0,
    }


@router.put("/nodes/{node_id}", response_model=NodeResponse)
def update_node(
    node_id: int, node_data: NodeUpdate, db: Session = Depends(get_db)
):
    """Update an existing node."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Check name uniqueness if updating hostname
    if node_data.hostname and node_data.hostname != node.hostname:
        existing = db.query(Node).filter(Node.hostname == node_data.hostname).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Node with hostname '{node_data.hostname}' already exists",
            )

    # Update fields
    for field, value in node_data.model_dump(exclude_unset=True).items():
        setattr(node, field, value)

    db.commit()
    db.refresh(node)

    incident_count = db.query(Incident).filter(Incident.node_id == node_id).count()

    return {
        "id": node.id,
        "hostname": node.hostname,
        "ip_address": node.ip_address,
        "node_type": node.node_type,
        "version": node.version,
        "description": node.description,
        "created_at": node.created_at.isoformat() if node.created_at else None,
        "updated_at": node.updated_at.isoformat() if node.updated_at else None,
        "incident_count": incident_count,
    }


@router.delete("/nodes/{node_id}")
def delete_node(node_id: int, db: Session = Depends(get_db)):
    """Delete a node (only if no incidents are linked)."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Check for linked incidents
    incident_count = db.query(Incident).filter(Incident.node_id == node_id).count()
    if incident_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete node with {incident_count} linked incidents.",
        )

    db.delete(node)
    db.commit()

    return {"message": "Node deleted successfully"}


@router.get("/nodes/types/list")
def get_node_types(db: Session = Depends(get_db)):
    """Get all unique node types."""
    types = db.query(Node.node_type).distinct().all()
    return [t[0] for t in types if t[0]]
