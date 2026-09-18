from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class ConsumerReport(Base):
    """A report submitted by a consumer from the public profile."""
    __tablename__ = "consumer_reports"

    id = Column(Integer, primary_key=True, index=True)
    stall_id = Column(Integer, ForeignKey("stalls.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Categories: hygiene, info, location, other
    category = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stall = relationship("Stall")
