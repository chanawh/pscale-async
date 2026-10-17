from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.database import Base


class ActionType(PyEnum):
    START_WORK = "START_WORK"
    ESCALATE = "ESCALATE"
    RESOLVE = "RESOLVE"
    COMMENT = "COMMENT"
    ASSIGN = "ASSIGN"


class IncidentActivity(Base):
    __tablename__ = "incident_activities"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(
        Integer, ForeignKey("incidents.id"), nullable=False, index=True
    )
    user_id = Column(String(255), nullable=True, index=True)  # Will link to users later
    action_type = Column(
        Enum(ActionType, name="actiontype"), nullable=False, index=True
    )
    description = Column(Text)
    details = Column(Text)  # JSON field for additional details
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    incident = relationship("Incident", back_populates="activities")
    # user relationship will be added when user model exists

    def __repr__(self):
        return f"<IncidentActivity(id={self.id}, incident_id={self.incident_id}, action={self.action_type})>"
