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

    # Relationships
    incidents = relationship("Incident", back_populates="job")

    def __repr__(self):
        return f"<Job(id={self.id}, status={self.status}, progress={self.progress})>"
