"""Read access to the ingredient knowledge base.

Not needed by the vendor scan flow -- the pipeline reads the tables directly.
This exists so a reviewer can see *why* a verdict was reached, and so the
seeded data can be inspected without a database client.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.ingredient import Ingredient
from app.models.user import User
from app.schemas.ingredient import IngredientRead

router = APIRouter()


@router.get(
    "/",
    response_model=List[IngredientRead],
    summary="List the ingredient knowledge base (reviewer/admin only)",
)
def list_ingredients(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
    _: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMIN)),
) -> List[Ingredient]:
    query = db.query(Ingredient).options(
        selectinload(Ingredient.synonyms), selectinload(Ingredient.rules)
    )
    if not include_inactive:
        query = query.filter(Ingredient.is_active.is_(True))
    if category:
        query = query.filter(Ingredient.category == category)
    return query.order_by(Ingredient.canonical_name).limit(limit).all()
