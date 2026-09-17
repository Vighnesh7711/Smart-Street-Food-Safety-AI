"""Computed hygiene score, versioned per formula."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.db.types import JSONType

#: Bumped whenever the scoring formula changes in a way that would produce a
#: different number for identical inputs. Scores are never rewritten in
#: place, so this is what lets a reviewer tell "the stall got worse" apart
#: from "we changed how we score".
#:
#: v1: 0.70 * visual + 0.30 * checklist
CURRENT_FORMULA_VERSION = "v1"


class HygieneScore(Base):
    """The scored result of one hygiene check.

    Kept separate from `hygiene_checks` so a formula change can be recomputed
    and *compared* rather than overwriting history. This is also the table
    the deferred adaptive-monitoring and feedback-weighting phases extend --
    they add inputs and a formula version, not a new score store.
    """

    __tablename__ = "hygiene_scores"

    id = Column(Integer, primary_key=True, index=True)
    hygiene_check_id = Column(
        Integer,
        ForeignKey("hygiene_checks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    visual_score = Column(Float, nullable=False)
    checklist_score = Column(Float, nullable=True)
    """Null when the vendor skipped the checklist. `final_score` then falls
    back to the visual score alone rather than inventing answers."""

    final_score = Column(Float, nullable=False, index=True)

    # Per-indicator and per-view working, so a score can be explained line by
    # line rather than asserted.
    breakdown = Column(JSONType, nullable=False, default=dict)
    weights = Column(JSONType, nullable=False, default=dict)

    formula_version = Column(String(16), nullable=False, default=CURRENT_FORMULA_VERSION)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    hygiene_check = relationship("HygieneCheck", back_populates="score")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<HygieneScore check={self.hygiene_check_id} "
            f"{self.final_score:.1f} ({self.formula_version})>"
        )
