from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.food_item import FoodItem
from app.models.stall import Stall
from app.schemas.stall import StallCreate, StallUpdate


def get_stall(db: Session, stall_id: int) -> Optional[Stall]:
    return db.query(Stall).filter(Stall.id == stall_id).first()


def list_stalls_by_vendor(db: Session, vendor_id: int) -> List[Stall]:
    return (
        db.query(Stall)
        .filter(Stall.vendor_id == vendor_id)
        .order_by(Stall.id)
        .all()
    )


def get_stall_by_vendor_and_name(
    db: Session, *, vendor_id: int, name: str
) -> Optional[Stall]:
    """Used to make onboarding idempotent: re-submitting the same stall name
    updates the existing row instead of creating a duplicate."""
    return (
        db.query(Stall)
        .filter(Stall.vendor_id == vendor_id, Stall.name == name)
        .first()
    )


def create_stall(db: Session, *, vendor_id: int, data: StallCreate) -> Stall:
    """Create a stall.

    Note there is no `qr_code_id` parameter. The QR code is a separate row in
    `qr_codes`, issued by the caller via services/qr/service.py -- see that
    module for why the code is not a column on this table.
    """
    stall = Stall(
        vendor_id=vendor_id,
        name=data.name,
        food_category=data.food_category,
        address=data.address,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(stall)
    db.flush()
    return stall


def update_stall(db: Session, *, stall: Stall, data: StallCreate | StallUpdate) -> Stall:
    # exclude_unset so a partial update never nulls a field the client did
    # not send.
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(stall, field, value)
    db.flush()
    return stall


def replace_food_items(db: Session, *, stall_id: int, names: List[str]) -> List[FoodItem]:
    """Replace a stall's descriptive food-item list.

    Only meaningful at onboarding, where the list arrives as a whole. Label
    scans are the authoritative product record and never touch this.
    """
    db.query(FoodItem).filter(FoodItem.stall_id == stall_id).delete(
        synchronize_session=False
    )
    items = [FoodItem(stall_id=stall_id, name=name) for name in names]
    db.add_all(items)
    db.flush()
    return items
