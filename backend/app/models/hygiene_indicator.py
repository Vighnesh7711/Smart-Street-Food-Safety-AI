"""Catalog of visible hygiene indicators the CV layer can report."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.db.types import JSONType


class HygieneIndicator(Base):
    """One detectable indicator, with per-view penalties.

    Catalog data (seeded), not per-check data -- a hygiene check references
    these by `code` inside its findings JSON.

    `view_penalties` is the load-bearing column. The same physical fact means
    different things in different views: waste inside the waste area is a
    functioning bin, whereas waste in the preparation area is a contamination
    hazard. Scoring an indicator identically everywhere would penalise a
    vendor for owning a bin, which is the fastest way to lose their trust in
    the score.

        {"prep_area": 18, "storage_area": 12, "overall": 8, "waste_area": 0}

    A view absent from the map means the indicator does not apply there, and
    an explicit 0 means "applies, but carries no penalty in this view" --
    the distinction matters when explaining a result to a vendor.
    """

    __tablename__ = "hygiene_indicators"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(60), unique=True, index=True, nullable=False)
    display_name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    default_severity = Column(String(20), nullable=False, default="moderate")
    view_penalties = Column(JSONType, nullable=False, default=dict)
    # Raw labels a provider may emit for this indicator. For the placeholder
    # COCO mapping these are COCO class names ("bottle", "bowl"); for a
    # purpose-trained model they would be its class names. Keeping them as
    # data means swapping the model does not require editing cv_client's
    # mapping table.
    cv_labels = Column(JSONType, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<HygieneIndicator {self.code!r} ({self.default_severity})>"
