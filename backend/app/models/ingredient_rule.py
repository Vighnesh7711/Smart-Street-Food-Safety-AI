"""Ingredient rules and the recommendations attached to them."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.db.types import JSONType


class IngredientRule(Base):
    """A single evaluable statement about an ingredient.

    Each rule produces at most one status. The status is stored on the rule
    (`status_on_match`) rather than derived from severity, because the
    mapping is not one-to-one: a category-restricted colour and a
    high-trans-fat oil can carry the same severity but must yield
    "Application mismatch" and "Potential concern" respectively.

    `conditions` is JSON whose shape depends on `rule_type`:
        presence              -> {} (any occurrence triggers)
        threshold             -> {"max_pct": 2.0}
        category_restriction  -> {"allowed_categories": ["Beverages", ...]}
    """

    __tablename__ = "ingredient_rules"

    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    rule_type = Column(String(40), nullable=False)
    conditions = Column(JSONType, nullable=False, default=dict)
    severity = Column(String(20), nullable=False, default="low")
    # One of app.models.enums.ScanStatus values. Stored as a string (not a
    # PG enum) so adding a status stays a code-only change.
    status_on_match = Column(String(40), nullable=False)
    # English template with named placeholders, e.g.
    # "{ingredient} is a synthetic colour permitted only in {allowed}."
    explanation_template = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ingredient = relationship("Ingredient", back_populates="rules")
    recommendations = relationship(
        "Recommendation",
        back_populates="rule",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<IngredientRule {self.rule_type} -> {self.status_on_match}>"


class Recommendation(Base):
    """Actionable advice shown alongside an explanation.

    English only. The scan pipeline translates explanations and
    recommendations together, so the canonical English text stays the single
    source of truth for the reviewer dashboard and the "show original
    English" toggle.
    """

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(
        Integer, ForeignKey("ingredient_rules.id", ondelete="CASCADE"), nullable=True
    )
    ingredient_id = Column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=True
    )
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    # Lower sorts first; lets urgent advice outrank generic hygiene notes.
    priority = Column(Integer, nullable=False, default=100)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rule = relationship("IngredientRule", back_populates="recommendations")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Recommendation {self.title!r}>"
