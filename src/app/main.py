import uuid
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.api.routers.admin import router as admin_router
from src.api.routers.auth import router as auth_router
from src.api.routers.cluster import router as cluster_router
from src.api.routers.incidents import router as incidents_router
from src.api.routers.ingest import router as ingest_router
from src.api.routers.jobs import router as jobs_router
from src.api.routers.nodes import router as nodes_router
from src.api.routers.patterns import router as patterns_router
from src.api.routers.auth import get_current_user
from src.core.celery import celery_app
from src.core.config import settings
from src.db.database import get_db
from src.models import Job, JobStatus

# Create FastAPI app
app = FastAPI(
    title="Async Log Intelligence API",
    description="REST API service for OneFS log processing with async job queues",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        # Add production URLs when deployed
        "https://your-domain.com",
        "https://www.your-domain.com"
    ],  
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(cluster_router, prefix="/api/v1/cluster", tags=["cluster"])
app.include_router(ingest_router, prefix="/api/v1", tags=["ingestion"])
app.include_router(incidents_router, prefix="/api/v1", tags=["incidents"])
app.include_router(jobs_router, prefix="/api/v1", tags=["jobs"])
app.include_router(patterns_router, prefix="/api/v1", tags=["patterns"])
app.include_router(nodes_router, prefix="/api/v1", tags=["nodes"])
app.include_router(admin_router, prefix="/api/v1", tags=["database-admin"])


@app.get("/", tags=["health"])
def root():
    """Root endpoint"""
    return {
        "message": "Async Log Intelligence API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.on_event("startup")
def startup_event():
    """Initialize database tables and default data on startup"""
    from src.db.database import SessionLocal, create_tables
    from src.workers.log_processor import create_default_patterns

    # Create tables
    create_tables()
    print("Database tables created/verified")

    # Create default patterns if none exist
    db = SessionLocal()
    try:
        create_default_patterns(db)
        print("Default patterns created/verified")
    except Exception as e:
        print(f"Warning: Could not create default patterns: {e}")
    finally:
        db.close()


# gRPC streaming server (typed alternative to SSE, same event bus).
# Runs on its own port in gRPC's thread pool; started/stopped with the app.
_grpc_server = None


@app.on_event("startup")
def start_grpc_server():
    """Start the gRPC JobService alongside FastAPI (unless disabled)."""
    global _grpc_server
    if not settings.grpc_enabled:
        print("gRPC streaming disabled (GRPC_ENABLED=false)")
        return
    try:
        from src.grpc.server import create_server

        _grpc_server = create_server(settings.grpc_port)
        _grpc_server.start()
        print(f"gRPC JobService listening on port {settings.grpc_port}")
    except Exception as e:  # pragma: no cover - startup path, logged loudly
        print(f"Warning: could not start gRPC server: {e}")


@app.on_event("shutdown")
def stop_grpc_server():
    """Stop the gRPC server gracefully on app shutdown."""
    global _grpc_server
    if _grpc_server is not None:
        _grpc_server.stop(grace=5)
        _grpc_server = None
        print("gRPC JobService stopped")


@app.get("/health", tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint - returns degraded status instead of 503 for partial failures"""
    health_status = {"status": "healthy", "database": "unknown", "celery": "unknown"}

    # Test database connection
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Test Celery connection (optional - don't fail if Celery is down)
    try:
        celery_app.control.inspect().stats()
        health_status["celery"] = "connected"
    except Exception:
        health_status["celery"] = "disconnected"
        # Don't mark as degraded just for Celery

    # Only return 503 if database is completely unavailable
    if health_status["database"] == "unknown" or "error" in health_status["database"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {health_status['database']}",
        )

    return health_status


@app.get("/api/v1/summary", tags=["analytics"])
def get_summary(
    window_hours: int = 24,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get summary of incidents over time window"""
    from datetime import datetime, timedelta

    from sqlalchemy import and_, func

    from src.models import Incident

    # Calculate time window
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=window_hours)

    # Build query
    query = db.query(
        Incident.severity, Incident.status, func.count(Incident.id).label("count")
    ).filter(Incident.created_at >= start_time, Incident.created_at <= end_time)

    if severity:
        query = query.filter(Incident.severity == severity.upper())

    results = query.group_by(Incident.severity, Incident.status).all()

    # Format results
    summary = {}
    total_incidents = 0
    by_severity = {}
    by_status = {}

    for severity_level, status, count in results:
        total_incidents += count
        # Build summary by severity and status
        if severity_level not in summary:
            summary[severity_level] = {}
        summary[severity_level][status] = count
        # Build by_severity counts
        if severity_level not in by_severity:
            by_severity[severity_level] = 0
        by_severity[severity_level] += count
        # Build by_status counts
        if status not in by_status:
            by_status[status] = 0
        by_status[status] += count

    return {
        "window_hours": window_hours,
        "start_time": start_time,
        "end_time": end_time,
        "summary": summary,
        "total_incidents": total_incidents,
        "by_severity": by_severity,
        "by_status": by_status,
    }


@app.get("/api/v1/escalations", tags=["analytics"])
def get_escalations(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    """Get unresolved high-priority incidents"""
    from src.models import Incident, Severity, Status

    escalations = (
        db.query(Incident)
        .filter(
            Incident.severity.in_([Severity.HIGH, Severity.CRITICAL]),
            Incident.status.in_([Status.OPEN, Status.IN_PROGRESS]),
        )
        .order_by(Incident.created_at.desc())
        .all()
    )

    return {
        "total": len(escalations),
        "escalations": [
            {
                "id": incident.id,
                "title": incident.title,
                "severity": incident.severity.value,
                "status": incident.status.value,
                "created_at": incident.created_at,
                "node": incident.node.hostname if incident.node else None,
            }
            for incident in escalations
        ]
    }
