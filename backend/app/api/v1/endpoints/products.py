"""Product label scanning."""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, require_roles
from app.api.v1.endpoints.stalls import get_stall_for_reader
from app.crud import product as crud_product
from app.crud import stall as crud_stall
from app.crud import vendor as crud_vendor
from app.db.session import get_db
from app.models.enums import ScanStatus, UserRole
from app.models.product import Product
from app.models.stall import Stall
from app.models.user import User
from app.schemas.product import (
    ImageQualityRead,
    MatchedIngredientRead,
    ScanResultRead,
)
from app.services.products import scan_service

router = APIRouter()

# Mirrors SCAN_MAX_UPLOAD_MB; enforced again in the service so the limit
# holds even if this endpoint is called from elsewhere.
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def _to_read(product: Product, recommendations: Optional[List[str]] = None) -> ScanResultRead:
    """Serialize a Product row (plus its matches) into the result card."""
    quality = None
    if product.image_quality:
        quality = ImageQualityRead(**product.image_quality)

    return ScanResultRead(
        id=product.id,
        stall_id=product.stall_id,
        product_name=product.name,
        status=product.status,
        explanation=product.explanation or "",
        # Older rows predate translation; falling back to the English keeps
        # the client from having to handle a null in the primary field.
        explanation_translated=product.explanation_translated
        or product.explanation
        or "",
        language_code=product.language_code or "en",
        translation_failed=bool(product.translation_failed),
        recommendations=recommendations or [],
        matched_ingredients=[
            MatchedIngredientRead(
                ingredient_id=m.ingredient_id,
                canonical_name=m.ingredient.canonical_name if m.ingredient else "Unknown",
                category=m.ingredient.category if m.ingredient else "Other",
                risk_level=m.ingredient.default_risk_level if m.ingredient else "low",
                matched_text=m.matched_text,
                matched_alias=m.matched_alias,
                match_confidence=m.match_confidence,
                match_method=m.match_method,
                parsed_percent=m.parsed_percent,
            )
            for m in product.ingredient_matches
        ],
        ocr_confidence=product.ocr_confidence,
        match_confidence=product.match_confidence,
        rule_strength=product.rule_strength,
        confidence_score=product.confidence_score,
        retake_required=bool(product.retake_required),
        image_quality=quality,
        ingredient_text=product.ingredients_text,
        scan_image_url=product.scan_image_path,
        created_at=product.created_at,
    )


def _resolve_scan_stall(db: Session, stall_id: int, user: User) -> Stall:
    """Load the stall a scan belongs to, enforcing ownership for vendors.

    Delegates to the same helper the stall endpoints use, so "may I see this
    stall" and "may I scan against this stall" cannot drift apart.
    """
    return get_stall_for_reader(db, stall_id, user)


def _vendor_stall_ids(db: Session, user: User) -> Optional[List[int]]:
    """Stall ids the caller may see, or None for unrestricted roles."""
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role in (UserRole.REVIEWER.value, UserRole.ADMIN.value):
        return None
    if role == UserRole.VENDOR.value:
        vendor = crud_vendor.get_vendor_by_user_id(db, user_id=user.id)
        if vendor is None:
            return []
        return [s.id for s in crud_stall.list_stalls_by_vendor(db, vendor_id=vendor.id)]
    return []


@router.post(
    "/scan",
    response_model=ScanResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Scan a product label photo",
)
def scan_product_label(
    stall_id: int = Form(..., description="The stall this product belongs to"),
    file: UploadFile = File(..., description="Photo of the ingredient panel"),
    language: Optional[str] = Form(
        None, description="Override the vendor's preferred language"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.VENDOR)),
) -> ScanResultRead:
    """Run the full pipeline and return the result card.

    Synchronous: the response is the finished assessment, so the mobile UI
    holds a loading state for the duration. See scan_service for the stages
    and workers/README.md for the asynchronous upgrade path.
    """
    stall = _resolve_scan_stall(db, stall_id, current_user)

    image_bytes = file.file.read(_MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="That image is too large. Please retake at a smaller size.",
        )

    try:
        outcome = scan_service.scan_label(
            db,
            stall=stall,
            user=current_user,
            image_bytes=image_bytes,
            target_language=language,
        )
    except scan_service.ScanError as exc:
        # 503 rather than 500: this is "the service could not do its job
        # right now", and `retryable` tells the client whether retrying is
        # worth it. The vendor sees `user_message`, never the raw error.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": exc.user_message, "retryable": exc.retryable},
        ) from exc

    return _to_read(outcome.product, outcome.recommendations)


@router.get(
    "/scans",
    response_model=List[ScanResultRead],
    summary="Scan history (vendor: own stalls; reviewer: all)",
)
def list_scans(
    db: Session = Depends(get_db),
    stall_id: Optional[int] = Query(None),
    scan_status: Optional[ScanStatus] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
) -> List[ScanResultRead]:
    """Reverse-chronological scan history, scoped by role."""
    stall_ids = _vendor_stall_ids(db, current_user)

    if stall_id is not None:
        # A specific stall was requested: confirm the caller may see it
        # rather than trusting the filter alone.
        _resolve_scan_stall(db, stall_id, current_user)
        stall_ids = [stall_id]

    scans = crud_product.list_scans(
        db,
        stall_ids=stall_ids,
        status=scan_status.value if scan_status else None,
        skip=skip,
        limit=limit,
    )
    return [_to_read(scan) for scan in scans]


@router.get(
    "/scans/{scan_id}",
    response_model=ScanResultRead,
    summary="Detail for a single scan",
)
def read_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ScanResultRead:
    product = crud_product.get_product(db, scan_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found"
        )

    stall_ids = _vendor_stall_ids(db, current_user)
    if stall_ids is not None and product.stall_id not in stall_ids:
        # 404, not 403: confirming that a scan id exists but belongs to
        # someone else leaks information.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found"
        )

    return _to_read(product)
