"""Pattern management API router."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.api.routers.auth import get_current_user
from src.models import Incident, Pattern

router = APIRouter(dependencies=[Depends(get_current_user)])


class PatternResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    regex_pattern: str
    category: Optional[str]
    severity_level: str
    is_active: bool
    created_at: str
    updated_at: Optional[str]
    incident_count: int = 0

    class Config:
        from_attributes = True


class PatternCreate(BaseModel):
    name: str
    description: Optional[str] = None
    regex_pattern: str
    category: Optional[str] = None
    severity_level: str = "MEDIUM"


class PatternUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    regex_pattern: Optional[str] = None
    category: Optional[str] = None
    severity_level: Optional[str] = None
    is_active: Optional[bool] = None


class PatternToggle(BaseModel):
    is_active: bool


class PatternTestRequest(BaseModel):
    regex_pattern: str
    test_line: str


class PatternTestResponse(BaseModel):
    matches: bool
    matched_text: Optional[str] = None
    groups: List[str] = []


@router.get("/patterns")
async def get_patterns(
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get all patterns with optional filtering."""
    query = db.query(Pattern)

    if category:
        query = query.filter(Pattern.category == category)
    if severity:
        query = query.filter(Pattern.severity_level == severity.upper())
    if is_active is not None:
        query = query.filter(Pattern.is_active == is_active)

    # Get incident counts for each pattern
    incident_counts = (
        db.query(Incident.pattern_id, func.count(Incident.id).label("count"))
        .group_by(Incident.pattern_id)
        .all()
    )
    count_map = {p_id: cnt for p_id, cnt in incident_counts}

    patterns = query.order_by(Pattern.created_at.desc()).offset(skip).limit(limit).all()
    total = query.count()

    result = []
    for p in patterns:
        p_dict = {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "regex_pattern": p.regex_pattern,
            "category": p.category,
            "severity_level": p.severity_level,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "incident_count": count_map.get(p.id, 0),
        }
        result.append(p_dict)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "patterns": result
    }


@router.get("/patterns/categories")
async def get_pattern_categories(db: Session = Depends(get_db)):
    """Get all unique pattern categories."""
    categories = db.query(Pattern.category).distinct().all()
    return [c[0] for c in categories if c[0]]


@router.get("/patterns/{pattern_id}", response_model=PatternResponse)
async def get_pattern(pattern_id: int, db: Session = Depends(get_db)):
    """Get a specific pattern by ID."""
    pattern = db.query(Pattern).filter(Pattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    # Get incident count
    incident_count = (
        db.query(Incident).filter(Incident.pattern_id == pattern_id).count()
    )

    return {
        "id": pattern.id,
        "name": pattern.name,
        "description": pattern.description,
        "regex_pattern": pattern.regex_pattern,
        "category": pattern.category,
        "severity_level": pattern.severity_level,
        "is_active": pattern.is_active,
        "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
        "updated_at": pattern.updated_at.isoformat() if pattern.updated_at else None,
        "incident_count": incident_count,
    }


@router.post("/patterns", response_model=PatternResponse)
async def create_pattern(pattern_data: PatternCreate, db: Session = Depends(get_db)):
    """Create a new pattern."""
    # Check for duplicate name
    existing = db.query(Pattern).filter(Pattern.name == pattern_data.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Pattern with name '{pattern_data.name}' already exists",
        )

    # Validate regex
    import re

    try:
        re.compile(pattern_data.regex_pattern)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {str(e)}")

    pattern = Pattern(
        name=pattern_data.name,
        description=pattern_data.description,
        regex_pattern=pattern_data.regex_pattern,
        category=pattern_data.category,
        severity_level=pattern_data.severity_level.upper(),
        is_active=True,
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)

    return {
        "id": pattern.id,
        "name": pattern.name,
        "description": pattern.description,
        "regex_pattern": pattern.regex_pattern,
        "category": pattern.category,
        "severity_level": pattern.severity_level,
        "is_active": pattern.is_active,
        "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
        "updated_at": pattern.updated_at.isoformat() if pattern.updated_at else None,
        "incident_count": 0,
    }


@router.put("/patterns/{pattern_id}", response_model=PatternResponse)
async def update_pattern(
    pattern_id: int, pattern_data: PatternUpdate, db: Session = Depends(get_db)
):
    """Update an existing pattern."""
    pattern = db.query(Pattern).filter(Pattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    # Check name uniqueness if updating name
    if pattern_data.name and pattern_data.name != pattern.name:
        existing = db.query(Pattern).filter(Pattern.name == pattern_data.name).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Pattern with name '{pattern_data.name}' already exists",
            )

    # Validate regex if updating
    if pattern_data.regex_pattern:
        import re

        try:
            re.compile(pattern_data.regex_pattern)
        except re.error as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid regex pattern: {str(e)}"
            )

    # Update fields
    for field, value in pattern_data.model_dump(exclude_unset=True).items():
        setattr(pattern, field, value)

    db.commit()
    db.refresh(pattern)

    # Get incident count
    incident_count = (
        db.query(Incident).filter(Incident.pattern_id == pattern_id).count()
    )

    return {
        "id": pattern.id,
        "name": pattern.name,
        "description": pattern.description,
        "regex_pattern": pattern.regex_pattern,
        "category": pattern.category,
        "severity_level": pattern.severity_level,
        "is_active": pattern.is_active,
        "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
        "updated_at": pattern.updated_at.isoformat() if pattern.updated_at else None,
        "incident_count": incident_count,
    }


@router.put("/patterns/{pattern_id}/toggle", response_model=PatternResponse)
async def toggle_pattern(
    pattern_id: int, toggle_data: PatternToggle, db: Session = Depends(get_db)
):
    """Toggle pattern active status."""
    pattern = db.query(Pattern).filter(Pattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    pattern.is_active = toggle_data.is_active
    db.commit()
    db.refresh(pattern)

    incident_count = (
        db.query(Incident).filter(Incident.pattern_id == pattern_id).count()
    )

    return {
        "id": pattern.id,
        "name": pattern.name,
        "description": pattern.description,
        "regex_pattern": pattern.regex_pattern,
        "category": pattern.category,
        "severity_level": pattern.severity_level,
        "is_active": pattern.is_active,
        "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
        "updated_at": pattern.updated_at.isoformat() if pattern.updated_at else None,
        "incident_count": incident_count,
    }


@router.delete("/patterns/{pattern_id}")
async def delete_pattern(pattern_id: int, db: Session = Depends(get_db)):
    """Delete a pattern (only if no incidents are linked)."""
    pattern = db.query(Pattern).filter(Pattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    # Check for linked incidents
    incident_count = (
        db.query(Incident).filter(Incident.pattern_id == pattern_id).count()
    )
    if incident_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete pattern with {incident_count} linked incidents. Disable it instead.",
        )

    db.delete(pattern)
    db.commit()

    return {"message": "Pattern deleted successfully"}


@router.post("/patterns/test", response_model=PatternTestResponse)
async def test_pattern(test_data: PatternTestRequest):
    """Test a regex pattern against a log line."""
    import re

    try:
        pattern = re.compile(test_data.regex_pattern, re.IGNORECASE)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {str(e)}")

    match = pattern.search(test_data.test_line)

    if match:
        return {
            "matches": True,
            "matched_text": match.group(0),
            "groups": list(match.groups()) if match.groups() else [],
        }
    else:
        return {"matches": False, "matched_text": None, "groups": []}
