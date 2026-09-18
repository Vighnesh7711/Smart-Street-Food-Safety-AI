from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

__all__ = ["AuditLog"]


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True, nullable=False)
    
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_type = Column(String, nullable=False, index=True)
    target_id = Column(Integer, nullable=False, index=True)
    
    # Store arbitrary metadata (e.g., resolution note, flag reason, old/new states)
    # Using JSON to support sqlite during dev and pg in prod if configured,
    # actually SQLAlchemy JSON type handles both. Let's use sqlalchemy.JSON.
    from sqlalchemy.types import JSON
    details = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    actor = relationship("User")
