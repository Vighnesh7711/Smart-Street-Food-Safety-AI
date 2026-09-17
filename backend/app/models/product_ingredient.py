"""Join table: which ingredients were found in a scanned product, and how."""

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class ProductIngredient(Base):
    """One matched ingredient on one scanned label.

    Stores the *evidence* for the match, not just the outcome: `matched_text`
    is the raw OCR substring and `matched_alias` the knowledge-base form it
    resolved to. Without these, a vendor disputing a "Potential concern"
    verdict leaves a reviewer with nothing to inspect.
    """

    __tablename__ = "product_ingredients"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "ingredient_id", name="uq_product_ingredient"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id = Column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )

    # Raw substring from the OCR output that produced this match.
    matched_text = Column(String(300), nullable=True)
    # The synonym/canonical form that actually hit.
    matched_alias = Column(String(200), nullable=True)
    match_confidence = Column(Float, nullable=False, default=0.0)
    # One of app.models.enums.MatchMethod values.
    match_method = Column(String(20), nullable=False, default="exact")
    # Character offset into the extracted ingredient section, so the UI can
    # highlight the match in context.
    position_in_text = Column(Integer, nullable=True)
    # Percentage parsed from the label next to this ingredient, if any.
    # Threshold rules compare against this.
    parsed_percent = Column(Float, nullable=True)

    product = relationship("Product", back_populates="ingredient_matches")
    ingredient = relationship("Ingredient")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<ProductIngredient product={self.product_id} "
            f"ingredient={self.ingredient_id} {self.match_method}>"
        )
