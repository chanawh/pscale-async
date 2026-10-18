from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.database import Base


class Severity(PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Status(PyEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    severity = Column(Enum(Severity), nullable=False, index=True)
    status = Column(Enum(Status), default=Status.OPEN, index=True)
    raw_log = Column(Text)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign keys
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False, index=True)
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=False, index=True)
    job_id = Column(String(255), ForeignKey("jobs.id"), nullable=False, index=True)

    # Chunked pipeline: which fan-out slice wrote this incident. Used for
    # retry safety — a retried chunk deletes its previous output via
    # (job_id, chunk_index) before reprocessing, so a redelivery after a
    # successful commit cannot duplicate incidents. NULL means the incident
    # came from the legacy monolithic path; the delete predicate never
    # matches NULL, so legacy incidents are never touched by chunk retries.
    chunk_index = Column(Integer, nullable=True, index=True)

    # Content fingerprint: sha256(pattern_id, node_id, stripped log line),
    # 64 hex chars — see src/workers/fingerprint.py for the composition and
    # the scope rationale. UNIQUE across the table: the effective dedup
    # scope is (pattern, node, line), global across jobs, so re-ingesting
    # the same file as a new job inserts zero new incidents while the same
    # line on a different node still creates a distinct incident. NULL for
    # rows written before this column existed; NULLs never participate in
    # dedup (NULL != NULL under unique indexes on PostgreSQL and SQLite).
    # New code always sets it.
    fingerprint = Column(String(64), nullable=True, unique=True)

    # Relationships
    node = relationship("Node", back_populates="incidents")
    pattern = relationship("Pattern", back_populates="incidents")
    job = relationship("Job", back_populates="incidents")
    activities = relationship("IncidentActivity", back_populates="incident")

    def __repr__(self):
        return (
            f"<Incident(id={self.id}, title='{self.title}', severity={self.severity})>"
        )
