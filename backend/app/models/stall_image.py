"""One submitted stall photo belonging to a hygiene check."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.db.types import JSONType


class StallImage(Base):
    """A single view photo.

    Unique on (hygiene_check_id, view_category): a retake replaces the image
    for that view rather than accumulating rows. Without this, "retake the
    storage photo" would leave the old, worse image in the set and the score
    would depend on submission order.
    """

    __tablename__ = "stall_images"
    __table_args__ = (
        UniqueConstraint(
            "hygiene_check_id", "view_category", name="uq_stall_image_view"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    hygiene_check_id = Column(
        Integer, ForeignKey("hygiene_checks.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized so the reviewer's "all photos for this stall" query does
    # not have to join through hygiene_checks.
    stall_id = Column(Integer, ForeignKey("stalls.id"), nullable=False, index=True)

    view_category = Column(String(30), nullable=False)

    image_path = Column(String(500), nullable=False)
    # Output of the image-quality gate (blur, exposure, glare), same shape as
    # the product-scan gate.
    quality = Column(JSONType, nullable=True)
    # Raw detections from cv_client, kept so a disputed finding can be traced
    # back to what the provider actually saw. JSONB rather than a table
    # because these are written once and only read alongside their image.
    detections = Column(JSONType, nullable=True)

    # 64-bit difference hash, hex. Used to reject the same photo being
    # submitted for a second view; see services/hygiene/duplicate.py.
    phash = Column(String(32), nullable=True, index=True)
    duplicate_of_id = Column(
        Integer, ForeignKey("stall_images.id"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hygiene_check = relationship("HygieneCheck", back_populates="images")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<StallImage check={self.hygiene_check_id} view={self.view_category}>"
