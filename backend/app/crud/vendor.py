from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.schemas.vendor import VendorBase


def get_vendor(db: Session, vendor_id: int) -> Optional[Vendor]:
    return db.query(Vendor).filter(Vendor.id == vendor_id).first()


def get_vendor_by_user_id(db: Session, user_id: int) -> Optional[Vendor]:
    return db.query(Vendor).filter(Vendor.user_id == user_id).first()


def list_vendors(db: Session, skip: int = 0, limit: int = 200) -> List[Vendor]:
    return (
        db.query(Vendor)
        .order_by(Vendor.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_vendor(db: Session, *, user_id: int, data: VendorBase) -> Vendor:
    vendor = Vendor(
        user_id=user_id,
        phone_number=data.phone_number,
        preferred_language=data.preferred_language,
    )
    db.add(vendor)
    db.flush()  # assign PK without committing; caller owns the transaction
    return vendor


def update_vendor(db: Session, *, vendor: Vendor, data: VendorBase) -> Vendor:
    vendor.phone_number = data.phone_number
    vendor.preferred_language = data.preferred_language
    db.flush()
    return vendor
