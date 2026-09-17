"""A scanned product label and the verdict the pipeline produced."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.db.types import JSONType


class Product(Base):
    """One label scan.

    Phase 1 created this table with just the verdict columns. Phase 2 adds
    the per-stage confidences and the translation fields.

    The three stage confidences are stored separately from the blended
    `confidence_score` on purpose: when a verdict is disputed, "OCR read it
    badly" and "we matched it badly" call for completely different fixes,
    and a single blended number cannot tell them apart.
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    stall_id = Column(Integer, ForeignKey("stalls.id"), nullable=False, index=True)
    name = Column(String(200), index=True, nullable=True)
    ingredients_text = Column(Text, nullable=True)

    # --- Verdict ---
    # One of app.models.enums.ScanStatus values. Stored as a string rather
    # than a PG enum so adding a sixth status later is a code-only change.
    status = Column(String(40), nullable=True, index=True)
    # Canonical English explanation. Always populated, even when translation
    # succeeded, so the reviewer dashboard and the "show original English"
    # toggle have a single source of truth.
    explanation = Column(Text, nullable=True)

    # --- Translation ---
    explanation_translated = Column(Text, nullable=True)
    language_code = Column(String(8), nullable=True)
    # True when the translation provider failed and we fell back to English.
    # Drives the "showing English" banner rather than failing the scan.
    translation_failed = Column(Boolean, nullable=False, default=False)

    # --- Pipeline evidence ---
    scan_image_path = Column(String(500), nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    match_confidence = Column(Float, nullable=True)
    rule_strength = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True, index=True)
    # Metrics and issue list from the image-quality gate.
    image_quality = Column(JSONType, nullable=True)
    # True only for "Needs review" outcomes, where retaking can help.
    retake_required = Column(Boolean, nullable=False, default=False)

    scanned_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    stall = relationship("Stall", back_populates="products")
    ingredient_matches = relationship(
        "ProductIngredient",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Product {self.id} stall={self.stall_id} status={self.status!r}>"
