from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app.models.product import Product
from app.models.product_ingredient import ProductIngredient


def get_product(db: Session, product_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == product_id).first()


def _with_matches(query):
    """Eager-load matches and their ingredients.

    Without this, serializing N scans issues N+1 queries for the ingredient
    rows -- the reviewer dashboard lists many scans at once.
    """
    return query.options(
        selectinload(Product.ingredient_matches).selectinload(
            ProductIngredient.ingredient
        )
    )


def list_scans(
    db: Session,
    *,
    stall_ids: Optional[List[int]] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Product]:
    """Most recent scans first, optionally scoped to stalls and/or status.

    `stall_ids=None` means unscoped (reviewer view); an empty list means
    "no stalls", which correctly returns nothing rather than everything --
    important, because a vendor with no stalls must not see the whole table.
    """
    query = _with_matches(db.query(Product))
    if stall_ids is not None:
        if not stall_ids:
            return []
        query = query.filter(Product.stall_id.in_(stall_ids))
    if status:
        query = query.filter(Product.status == status)
    return (
        query.order_by(Product.created_at.desc(), Product.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_scans(db: Session, *, stall_ids: Optional[List[int]] = None) -> int:
    query = db.query(Product)
    if stall_ids is not None:
        if not stall_ids:
            return 0
        query = query.filter(Product.stall_id.in_(stall_ids))
    return query.count()
