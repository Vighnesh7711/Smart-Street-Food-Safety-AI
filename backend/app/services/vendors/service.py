"""Vendor onboarding: profile + first stall, atomically.

Phase 1 left `POST /vendors/onboard` as a stub that returned success without
writing anything, which meant no stall ever existed and therefore nothing
could be scanned. This module is the real implementation.
"""

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import stall as crud_stall
from app.crud import vendor as crud_vendor
from app.models.stall import Stall
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.vendor import VendorBase, VendorOnboardRequest
from app.services.qr import service as qr_service


@dataclass
class OnboardResult:
    vendor: Vendor
    stall: Stall
    created: bool
    """True if records were created; False if an existing vendor/stall pair
    was updated. Both paths are success -- this only drives the client's
    wording."""


def onboard_vendor(
    db: Session, *, user: User, payload: VendorOnboardRequest
) -> OnboardResult:
    """Create or update a vendor profile and their stall.

    Idempotent by design. A vendor tapping "Register Stall" twice, or
    retrying after a flaky connection, must not end up with two stalls --
    so an existing (vendor, stall name) pair is updated in place.

    Everything commits together. A partial write here would leave a vendor
    who cannot scan (no stall) or an orphan stall (no owner), so the whole
    operation is one transaction and rolls back on any failure.
    """
    try:
        vendor = crud_vendor.get_vendor_by_user_id(db, user_id=user.id)
        created = vendor is None

        profile = VendorBase(
            phone_number=payload.phone_number,
            preferred_language=payload.preferred_language,
        )

        if vendor is None:
            vendor = crud_vendor.create_vendor(db, user_id=user.id, data=profile)
        else:
            vendor = crud_vendor.update_vendor(db, vendor=vendor, data=profile)

        existing = crud_stall.get_stall_by_vendor_and_name(
            db, vendor_id=vendor.id, name=payload.stall.name
        )
        if existing is None:
            stall = crud_stall.create_stall(
                db, vendor_id=vendor.id, data=payload.stall
            )
            # Issue the public code in the same transaction as the stall. A
            # stall without a code has no QR sticker and no public page, so
            # the two must not be able to diverge.
            qr_service.issue_for_stall(db, stall)
            created = True
        else:
            stall = crud_stall.update_stall(db, stall=existing, data=payload.stall)

        if payload.food_items:
            crud_stall.replace_food_items(
                db, stall_id=stall.id, names=payload.food_items
            )

        db.commit()
    except IntegrityError:
        # Two concurrent onboard requests for the same user can both pass the
        # "vendor is None" check; vendors.user_id is UNIQUE, so the loser
        # lands here. Rolling back and retrying once is safe because the
        # operation is idempotent.
        db.rollback()
        vendor = crud_vendor.get_vendor_by_user_id(db, user_id=user.id)
        if vendor is None:
            raise
        existing = crud_stall.get_stall_by_vendor_and_name(
            db, vendor_id=vendor.id, name=payload.stall.name
        )
        if existing is None:
            raise
        stall = crud_stall.update_stall(db, stall=existing, data=payload.stall)
        db.commit()
        created = False
    except Exception:
        db.rollback()
        raise

    db.refresh(vendor)
    db.refresh(stall)
    return OnboardResult(vendor=vendor, stall=stall, created=created)
