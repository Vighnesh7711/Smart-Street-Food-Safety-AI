"""Vendor endpoints: stall onboarding and vendor directory."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, require_roles
from app.crud import vendor as crud_vendor
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.vendor import VendorOnboardRequest, VendorOnboardResponse, VendorRead
from app.services.vendors import service as vendor_service

router = APIRouter()


def _to_read(vendor, user: User | None = None) -> VendorRead:
    """Flatten a Vendor row (and optionally its User) into the API shape."""
    return VendorRead(
        id=vendor.id,
        user_id=vendor.user_id,
        phone_number=vendor.phone_number,
        preferred_language=vendor.preferred_language,
        created_at=vendor.created_at,
        full_name=user.full_name if user else None,
        email=user.email if user else None,
    )


@router.post(
    "/onboard",
    response_model=VendorOnboardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a vendor profile and their stall",
)
def onboard_vendor(
    payload: VendorOnboardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> VendorOnboardResponse:
    """Create the caller's vendor profile and stall in one transaction.

    Idempotent: re-submitting the same stall name updates the existing
    records and returns `created: false`, so a double-tap or a retry after a
    dropped connection cannot produce duplicate stalls.
    """
    result = vendor_service.onboard_vendor(db, user=current_user, payload=payload)
    return VendorOnboardResponse(
        vendor=_to_read(result.vendor, current_user),
        stall=result.stall,
        created=result.created,
    )


@router.get(
    "/me",
    response_model=VendorRead,
    summary="The caller's own vendor profile",
)
def read_my_vendor(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> VendorRead:
    vendor = crud_vendor.get_vendor_by_user_id(db, user_id=current_user.id)
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No vendor profile yet. Complete stall onboarding first.",
        )
    return _to_read(vendor, current_user)


@router.get(
    "/",
    response_model=List[VendorRead],
    summary="List all vendors (reviewer/admin only)",
)
def list_vendors(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 200,
    _: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMIN)),
) -> List[VendorRead]:
    """Directory for the reviewer dashboard.

    Role enforcement moved into `require_roles`, so the check is part of the
    route signature (and the OpenAPI schema) rather than an inline branch
    that a future edit could forget.
    """
    vendors = crud_vendor.list_vendors(db, skip=skip, limit=limit)
    return [_to_read(v, v.user) for v in vendors]
