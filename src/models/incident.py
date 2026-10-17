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

    # Relationships
    node = relationship("Node", back_populates="incidents")
    pattern = relationship("Pattern", back_populates="incidents")
    job = relationship("Job", back_populates="incidents")
    activities = relationship("IncidentActivity", back_populates="incident")

    def __repr__(self):
        return (
            f"<Incident(id={self.id}, title='{self.title}', severity={self.severity})>"
        )
