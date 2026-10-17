from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.database import Base


class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(45))
    node_type = Column(String(100))  # e.g., "storage", "compute", "gateway"
    version = Column(String(50))  # OneFS version
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    incidents = relationship("Incident", back_populates="node")

    def __repr__(self):
        return f"<Node(id={self.id}, hostname='{self.hostname}')>"
