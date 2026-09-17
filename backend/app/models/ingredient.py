"""Ingredient knowledge base: canonical ingredients and their aliases."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class Ingredient(Base):
    """A canonical ingredient the matcher can resolve OCR text to.

    `canonical_name` is the single source of truth used in explanations and
    on the reviewer dashboard. Everything else that appears on a label --
    trade names, FSSAI synonyms, INS/E numbers, common OCR misreads -- lives
    in IngredientSynonym so matching never has to special-case strings.
    """

    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(200), unique=True, index=True, nullable=False)
    category = Column(String(80), nullable=False, index=True)
    default_risk_level = Column(String(20), nullable=False, default="low")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    synonyms = relationship(
        "IngredientSynonym",
        back_populates="ingredient",
        cascade="all, delete-orphan",
    )
    rules = relationship(
        "IngredientRule",
        back_populates="ingredient",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Ingredient {self.canonical_name!r} ({self.category})>"


class IngredientSynonym(Base):
    """An alternative surface form for an ingredient.

    Split out from Ingredient rather than stored as a JSON column because
    matching is the hot path: one indexed equality lookup per parsed label
    token. A unique index on `normalized_alias` makes stage-1 matching a
    single index probe, and INS/E numbers are naturally rows, not nested
    JSON. Extending the synonym set stays a data change.
    """

    __tablename__ = "ingredient_synonyms"
    __table_args__ = (
        UniqueConstraint("normalized_alias", name="uq_ingredient_synonym_alias"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    alias = Column(String(200), nullable=False)
    # Lowercased/whitespace-stripped form of `alias`. Precomputed so the
    # matcher never normalizes the whole knowledge base per request. No
    # separate index=True: the UNIQUE constraint below already creates the
    # index that matching probes.
    normalized_alias = Column(String(200), nullable=False)
    alias_type = Column(String(30), nullable=False, default="common_name")

    ingredient = relationship("Ingredient", back_populates="synonyms")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<IngredientSynonym {self.alias!r} -> {self.ingredient_id}>"
