"""Stall endpoints.

Phase 2 uses these to resolve the stall a scan belongs to. QR rendering and
the public consumer profile are a later phase.
"""

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, require_roles
from app.core.config import settings
from app.crud import stall as crud_stall
from app.crud import vendor as crud_vendor
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.stall import Stall
from app.models.user import User
from app.schemas.stall import StallQrRead, StallRead
from app.services.qr import service as qr_service

router = APIRouter()


def get_stall_for_reader(db: Session, stall_id: int, user: User) -> Stall:
    """Load a stall, enforcing that the caller may see it.

    Vendors see only their own stalls; reviewers and admins see all. Returns
    404 rather than 403 for someone else's stall so the endpoint does not
    confirm that an arbitrary stall id exists.
    """
    stall = crud_stall.get_stall(db, stall_id)
    if stall is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stall not found"
        )

    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role in (UserRole.REVIEWER.value, UserRole.ADMIN.value):
        return stall

    if role == UserRole.VENDOR.value:
        vendor = crud_vendor.get_vendor_by_user_id(db, user_id=user.id)
        if vendor is not None and stall.vendor_id == vendor.id:
            return stall

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Stall not found"
    )


@router.get(
    "/mine",
    response_model=List[StallRead],
    summary="The caller's own stalls",
)
def list_my_stalls(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> List[Stall]:
    vendor = crud_vendor.get_vendor_by_user_id(db, user_id=current_user.id)
    if vendor is None:
        return []
    return crud_stall.list_stalls_by_vendor(db, vendor_id=vendor.id)


@router.get(
    "/{stall_id}",
    response_model=StallRead,
    summary="Stall detail (owner vendor, or any reviewer)",
)
def read_stall(
    stall_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Stall:
    return get_stall_for_reader(db, stall_id, current_user)


# ---------------------------------------------------------------------------
# QR code
# ---------------------------------------------------------------------------
#
# Both endpoints go through `get_stall_for_reader`, the same helper the other
# stall routes use, so "may I see this stall" and "may I fetch its QR code"
# cannot drift apart.
#
# The QR *image* is authenticated even though it encodes public data. The
# vendor screen that displays it is authenticated anyway, and leaving it open
# would make the API a convenient lookup service for enumerating stalls.


def _resolve_qr_code(db: Session, stall: Stall):
    """The stall's active QR code, or 404.

    A stall whose only code was revoked has no active one. That should not
    happen in normal operation -- onboarding issues one and nothing revokes
    it yet -- but returning a clear 404 beats serving an image encoding
    `None`.
    """
    qr_code = stall.active_qr_code
    if qr_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This stall has no active QR code.",
        )
    return qr_code


@router.get(
    "/{stall_id}/qr",
    response_model=StallQrRead,
    summary="QR code details for a stall (owner vendor, or any reviewer)",
)
def read_stall_qr(
    stall_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StallQrRead:
    stall = get_stall_for_reader(db, stall_id, current_user)
    qr_code = _resolve_qr_code(db, stall)

    return StallQrRead(
        stall_id=stall.id,
        code=qr_code.code,
        public_url=qr_service.build_public_url(
            qr_code.code, settings.PUBLIC_APP_URL
        ),
        image_url=f"{settings.API_V1_STR}/stalls/{stall.id}/qr.png",
    )


@router.get(
    "/{stall_id}/qr.png",
    summary="QR code image (owner vendor, or any reviewer)",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def read_stall_qr_png(
    stall_id: int,
    size: Optional[int] = Query(
        None,
        description=(
            "Pixels per QR module. Defaults to a print-quality size. "
            "Clamped to a safe range."
        ),
    ),
    download: bool = Query(
        False, description="Send as an attachment instead of inline."
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """Render the stall's QR code as a PNG.

    The image encodes a full public URL rather than a bare code, so a
    consumer can point their ordinary camera app at a printed sticker and
    have it open -- no app install, and no in-app scanner required.
    """
    stall = get_stall_for_reader(db, stall_id, current_user)
    qr_code = _resolve_qr_code(db, stall)

    payload = qr_service.build_public_url(qr_code.code, settings.PUBLIC_APP_URL)
    png = qr_service.render_png(payload, box_size=size)

    headers = {
        # The code only changes on revocation, which is rare, but a short
        # cache keeps a printed sticker's image from being re-rendered on
        # every page view.
        "Cache-Control": "private, max-age=300",
    }
    if download:
        headers["Content-Disposition"] = (
            f'attachment; filename="stall-{qr_code.code}.png"'
        )

    return Response(content=png, media_type="image/png", headers=headers)
