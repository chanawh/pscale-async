from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.database import Base


class JobStatus(PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(255), primary_key=True, index=True)  # UUID
    filename = Column(String(255), nullable=False)
    description = Column(Text)  # Job description
    file_size = Column(Integer)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, index=True)
    progress = Column(Integer, default=0)  # 0-100
    result_summary = Column(Text)  # JSON summary of results
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Object-storage handoff: the Celery worker receives this content
    # reference (backend + bucket + key) — never a local filesystem path.
    # NULL for stream/cluster jobs, which pass log lines directly.
    storage_backend = Column(String(32), nullable=True)
    storage_bucket = Column(String(255), nullable=True)
    storage_key = Column(String(1024), nullable=True)

    # Chunked pipeline progress: fan-out/fan-in bookkeeping. Each chunk
    # task atomically increments chunks_completed
    # (UPDATE ... SET chunks_completed = chunks_completed + 1, safe under
    # concurrency) and job.progress tracks completed/total chunks.
    # NULL for legacy monolithic jobs.
    total_chunks = Column(Integer, nullable=True, default=0)
    chunks_completed = Column(Integer, nullable=True, default=0)

    # Multi-cluster: which configured OneFS target this job belongs to
    # (matches a "name" from ONEFS_TARGETS / ONEFS_TARGETS_FILE).
    # NULL for upload/stream jobs (not cluster-scoped) and for jobs
    # created before multi-cluster support -- both are treated as the
    # default cluster.
    cluster_name = Column(String(255), nullable=True, index=True)

    # Relationships
    incidents = relationship("Incident", back_populates="job")

    def __repr__(self):
        return f"<Job(id={self.id}, status={self.status}, progress={self.progress})>"
