from sqlalchemy import Column, Date, Float, Integer

from app.db.base_class import Base

__all__ = ["AnalyticsAggregate"]


class AnalyticsAggregate(Base):
    """
    Daily snapshot of system-wide analytics for reviewer dashboards.
    A background job or cron could populate this, or it can be updated on-demand.
    """
    __tablename__ = "analytics_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True, nullable=False)
    
    total_stalls = Column(Integer, nullable=False, default=0)
    assessed_stalls = Column(Integer, nullable=False, default=0)
    flagged_stalls = Column(Integer, nullable=False, default=0)
    average_score = Column(Float, nullable=True)
    
    # Activity metrics for the day
    scans_performed = Column(Integer, nullable=False, default=0)
    flags_created = Column(Integer, nullable=False, default=0)
    flags_resolved = Column(Integer, nullable=False, default=0)
    checks_performed = Column(Integer, nullable=False, default=0)
