"""A hygiene check: one submission of up to four stall views."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.db.types import JSONType
from app.models.enums import CheckStatus


class HygieneCheck(Base):
    """A vendor's hygiene submission.

    Created as a draft when the vendor opens the guided capture flow, and
    scored only once all four required views are present. Partial checks
    persist deliberately: a vendor who photographs two views and loses
    signal should not have to start over.
    """

    __tablename__ = "hygiene_checks"

    id = Column(Integer, primary_key=True, index=True)
    stall_id = Column(Integer, ForeignKey("stalls.id"), nullable=False, index=True)
    submitted_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )

    # See CheckStatus. Stored as a string so adding a state is a code-only change.
    status = Column(
        String(30), nullable=False, default=CheckStatus.DRAFT.value, index=True
    )

    # Which of the four required views have not been uploaded yet. Denormalized
    # from `images` so the "what should I photograph next" query is a single
    # row read rather than a join plus a set difference.
    missing_views = Column(JSONType, nullable=False, default=list)
    coverage_ok = Column(Boolean, nullable=False, default=False)

    # Summarised findings: [{"code": ..., "view": ..., "confidence": ...}, ...]
    # Indexed with GIN so the reviewer dashboard can filter "stalls with
    # visible_waste" without scanning every detection blob.
    indicators_found = Column(JSONType, nullable=False, default=list)

    # Vendor's self-declared checklist answers: {item_code: bool}
    checklist = Column(JSONType, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    scored_at = Column(DateTime(timezone=True), nullable=True)

    stall = relationship("Stall", backref="hygiene_checks")
    images = relationship(
        "StallImage",
        back_populates="hygiene_check",
        cascade="all, delete-orphan",
        order_by="StallImage.id",
    )
    score = relationship(
        "HygieneScore",
        back_populates="hygiene_check",
        # uselist=False: one current score per check. History across checks
        # lives in the hygiene_scores table itself, keyed by check.
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<HygieneCheck {self.id} stall={self.stall_id} {self.status!r}>"
