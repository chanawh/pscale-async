from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.database import Base


class Pattern(Base):
    __tablename__ = "patterns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    regex_pattern = Column(Text, nullable=False)
    category = Column(
        String(100), index=True
    )  # e.g., "security", "performance", "hardware"
    severity_level = Column(
        String(20), index=True
    )  # e.g., "LOW", "MEDIUM", "HIGH", "CRITICAL"
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    incidents = relationship("Incident", back_populates="pattern")

    def __repr__(self):
        return (
            f"<Pattern(id={self.id}, name='{self.name}', category='{self.category}')>"
        )
